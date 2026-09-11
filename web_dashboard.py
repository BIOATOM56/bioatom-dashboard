import json
import time
import os
import shutil
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

PORT = int(os.environ.get("PORT", 5000))
DB_FILE = "accounts_db.json"
DB_BAK_FILE = "accounts_db.json.bak"
ONLINE_THRESHOLD = 35

db_lock = threading.RLock()
ACCOUNTS = {}

def load_db():
    global ACCOUNTS
    with db_lock:
        for file_path in [DB_FILE, DB_BAK_FILE]:
            if os.path.exists(file_path):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, dict):
                            ACCOUNTS = data
                            print(f"📦 [DB] โหลดข้อมูลสำเร็จจาก {file_path} ({len(ACCOUNTS)} ไอดี)")
                            return
                except Exception as e:
                    print(f"⚠️ [DB Warning] อ่าน {file_path} ไม่สำเร็จ: {e}")
        ACCOUNTS = {}

load_db()

def save_db():
    with db_lock:
        try:
            temp_file = DB_FILE + ".tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(ACCOUNTS, f, ensure_ascii=False, indent=2)
            os.replace(temp_file, DB_FILE)
            shutil.copy(DB_FILE, DB_BAK_FILE)
        except Exception as e:
            print(f"❌ [DB Error] บันทึกไฟล์ล้มเหลว: {e}")

GITHUB_RAW = "https://raw.githubusercontent.com/BIOATOM56/bioatom-dashboard/main/"
FRUITS_CONFIG = [
    {"name": "Kitsune", "file": "Kitsune_Fruit.webp"},
    {"name": "Dragon", "file": "Dragon_Fruit.webp"},
    {"name": "Yeti", "file": "Yeti_Fruit.webp"},
    {"name": "Tiger", "file": "Tiger_Fruit.webp"},
    {"name": "Spirit", "file": "Spirit_Fruit.webp"},
    {"name": "Control", "file": "Control_Fruit.webp"},
    {"name": "Gas", "file": "Gas_Fruit.webp"},
    {"name": "Venom", "file": "Venom_Fruit.webp"},
    {"name": "Shadow", "file": "Shadow_Fruit.webp"},
    {"name": "Dough", "file": "Dough_Fruit.webp"},
    {"name": "T-Rex", "file": "T-Rex_Fruit.webp"},
    {"name": "Mammoth", "file": "Mammoth_Fruit.webp"},
    {"name": "Gravity", "file": "Gravity_Fruit.webp"},
    {"name": "Pain", "file": "Pain_Fruit.webp"},
    {"name": "Portal", "file": "Portal_Fruit.webp"},
    {"name": "Buddha", "file": "Buddha_Fruit.webp"},
    {"name": "Blizzard", "file": "Blizzard_Fruit.webp"},
    {"name": "Sound", "file": "Sound_Fruit.webp"},
    {"name": "Phoenix", "file": "Phoenix_Fruit.webp"},
    {"name": "Magnet", "file": "Magnet_Fruit.webp"},
    {"name": "Lightning", "file": "Lightning_Fruit.webp"}
]

MONITOR_FRUITS = [{"name": item["name"], "icon": f"{GITHUB_RAW}{item['file']}"} for item in FRUITS_CONFIG]

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <title>Bioatom Inventory Master</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link href="https://fonts.googleapis.com/css2?family=Kanit:wght@300;400;600&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #000000;
            --card-bg: #09090b;
            --card-border: #18181b;
            --text-main: #f4f4f5;
            --text-muted: #71717a;
            --accent-green: #10b981;
            --accent-red: #ef4444;
            --accent-blue: #3b82f6;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Kanit', sans-serif; }
        body { background-color: var(--bg-color); color: var(--text-main); padding: 25px; min-height: 100vh; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px; }
        .header h1 { font-size: 24px; font-weight: 600; letter-spacing: 0.5px; }
        .pulse-badge { display: inline-flex; align-items: center; gap: 8px; font-size: 13px; color: var(--accent-green); background: rgba(16, 185, 129, 0.08); padding: 6px 14px; border-radius: 20px; border: 1px solid rgba(16, 185, 129, 0.2); }
        .pulse-dot { width: 8px; height: 8px; background-color: var(--accent-green); border-radius: 50%; box-shadow: 0 0 10px var(--accent-green); }

        .overview-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 25px; }
        .stat-card { background-color: var(--card-bg); border: 1px solid var(--card-border); border-radius: 10px; padding: 16px; }
        .stat-title { font-size: 12px; color: var(--text-muted); margin-bottom: 4px; }
        .stat-value { font-size: 24px; font-weight: 700; font-family: 'JetBrains Mono', monospace; }

        .section-title { font-size: 17px; font-weight: 600; margin-bottom: 12px; color: #a1a1aa; }
        .grid-container { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 10px; margin-bottom: 30px; }
        
        .fruit-card {
            background-color: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 10px;
            padding: 10px 12px;
            display: flex;
            align-items: center;
            gap: 10px;
            transition: border-color 0.2s;
        }
        .fruit-card.active { border-color: rgba(16, 185, 129, 0.4); background: rgba(16, 185, 129, 0.03); }
        .fruit-icon { width: 42px; height: 42px; object-fit: contain; background: #000000; border-radius: 6px; padding: 2px; }
        .fruit-info { display: flex; flex-direction: column; }
        .fruit-name { font-size: 13px; font-weight: 500; }
        .fruit-count { font-size: 17px; font-weight: 700; font-family: 'JetBrains Mono', monospace; color: var(--accent-red); }
        .fruit-count.has-stock { color: var(--accent-green); }

        .table-toolbar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            background-color: var(--card-bg);
            border: 1px solid var(--card-border);
            border-bottom: none;
            padding: 12px 18px;
            border-radius: 10px 10px 0 0;
            flex-wrap: wrap;
            gap: 12px;
        }
        .left-controls { display: flex; align-items: center; gap: 14px; font-size: 14px; flex-wrap: wrap; }
        .search-box, .select-box {
            background: #18181b;
            border: 1px solid #27272a;
            color: #f4f4f5;
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 13px;
            outline: none;
        }
        .search-box { width: 200px; }
        .search-box:focus, .select-box:focus { border-color: var(--accent-blue); }
        .select-group { display: flex; align-items: center; gap: 8px; }
        .select-label { color: #a1a1aa; font-size: 13px; }
        
        .btn-group { display: flex; gap: 8px; }
        .btn-action {
            background: #18181b;
            border: 1px solid #27272a;
            color: var(--text-main);
            padding: 6px 14px;
            border-radius: 6px;
            font-size: 13px;
            cursor: pointer;
            transition: all 0.2s;
        }
        .btn-action:hover:not(:disabled) { background: #27272a; }
        .btn-action:disabled { opacity: 0.35; cursor: not-allowed; }
        .btn-danger-sel:hover:not(:disabled) { background: #b91c1c; border-color: #ef4444; }
        .btn-danger-all:hover { background: #7f1d1d; border-color: #dc2626; }

        .accounts-table-card { background-color: var(--card-bg); border: 1px solid var(--card-border); border-radius: 0 0 10px 10px; overflow-x: auto; margin-bottom: 40px; }
        table { width: 100%; border-collapse: collapse; text-align: left; }
        th { background-color: #040405; padding: 12px 16px; font-size: 13px; color: var(--text-muted); border-bottom: 1px solid var(--card-border); }
        td { padding: 12px 16px; font-size: 14px; border-bottom: 1px solid var(--card-border); }
        .user-tag { font-family: 'JetBrains Mono', monospace; font-weight: 600; color: #e4e4e7; }
        .status-badge { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 500; padding: 3px 8px; border-radius: 6px; }
        .status-online { color: var(--accent-green); background: rgba(16, 185, 129, 0.1); }
        .status-offline { color: var(--text-muted); background: #18181b; }
        .time-detail { font-size: 11px; color: #52525b; margin-left: 6px; font-family: 'JetBrains Mono', monospace; }
        .fruit-pill { display: inline-block; background: #121215; padding: 2px 8px; border-radius: 4px; font-size: 12px; margin: 2px; border: 1px solid #27272a; }

        input[type="checkbox"].acc-checkbox { width: 16px; height: 16px; accent-color: var(--accent-green); cursor: pointer; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Bioatom Overview</h1>
        <div class="pulse-badge"><div class="pulse-dot"></div> Live Cloud Monitor</div>
    </div>

    <div class="overview-cards">
        <div class="stat-card">
            <div class="stat-title">Active Online</div>
            <div class="stat-value" id="online-val" style="color: var(--accent-green);">0</div>
        </div>
        <div class="stat-card">
            <div class="stat-title">Recorded Accounts</div>
            <div class="stat-value" id="total-acc-val">0</div>
        </div>
        <div class="stat-card">
            <div class="stat-title">Total Fruits Stored</div>
            <div class="stat-value" id="fruits-val">0</div>
        </div>
        <div class="stat-card">
            <div class="stat-title">Fruit Catalog</div>
            <div class="stat-value" id="types-val">21</div>
        </div>
    </div>

    <div class="section-title">📦 Total Inventory Catalog</div>
    <div class="grid-container" id="fruit-grid">
        """ + "".join([f"""
        <div class="fruit-card" id="card-{f['name']}">
            <img class="fruit-icon" src="{f['icon']}" onerror="this.onerror=null; this.src='data:image/svg+xml;utf8,<svg xmlns=\\'http://www.w3.org/2000/svg\\' width=\\'42\\' height=\\'42\\' viewBox=\\'0 0 24 24\\' fill=\\'none\\' stroke=\\'%23525f73\\' stroke-width=\\'2\\'><circle cx=\\'12\\' cy=\\'12\\' r=\\'9\\'/><path d=\\'M12 3v5\\'/></svg>';">
            <div class="fruit-info">
                <span class="fruit-name">{f['name']}</span>
                <span class="fruit-count" id="count-{f['name']}">0</span>
            </div>
        </div>
        """ for f in MONITOR_FRUITS]) + """
    </div>

    <div class="section-title">👤 Account Storage Details & History</div>
    
    <div class="table-toolbar">
        <div class="left-controls">
            <div class="select-group">
                <input type="checkbox" id="check-all" class="acc-checkbox" onchange="toggleSelectAll(this)">
                <label for="check-all" style="cursor:pointer;">เลือกทั้งหมด</label>
                <span id="selected-badge" style="color: var(--text-muted); font-size: 13px;">(เลือก 0)</span>
            </div>
            
            <div class="select-group">
                <span class="select-label">เรียงลำดับ:</span>
                <select id="sort-select" class="select-box" onchange="applyFilterAndRender()">
                    <option value="recent">⏱️ เคลื่อนไหวล่าสุด (Active ล่าสุดขึ้นก่อน)</option>
                    <option value="online_first">🟢 สถานะออนไลน์ขึ้นก่อน</option>
                    <option value="fruits_desc">📦 จำนวนผลไม้ (มากไปน้อย)</option>
                    <option value="name_asc">🔤 ชื่อไอดี (A-Z)</option>
                </select>
            </div>

            <input type="text" id="search-input" class="search-box" placeholder="🔍 ค้นหาไอดี หรือ ผลไม้..." oninput="applyFilterAndRender()">
        </div>
        <div class="btn-group">
            <button id="btn-del-sel" class="btn-action btn-danger-sel" onclick="deleteSelected()" disabled>🗑️ ลบที่เลือก</button>
            <button class="btn-action btn-danger-all" onclick="deleteAll()">⚠️ ลบทิ้งทั้งหมด</button>
        </div>
    </div>

    <div class="accounts-table-card">
        <table>
            <thead>
                <tr>
                    <th style="width: 40px; text-align: center;">#</th>
                    <th>Account Name</th>
                    <th>Status / Last Active</th>
                    <th>Total Count</th>
                    <th>Storage Details</th>
                </tr>
            </thead>
            <tbody id="account-body">
                <tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 24px;">ℹ️ ยังไม่มีข้อมูลไอดีในระบบ</td></tr>
            </tbody>
        </table>
    </div>

    <script>
        const selectedUsers = new Set();
        let cachedData = { online_count: 0, total_fruits: 0, accounts: [] };
        let lastRenderHash = "";

        function formatTime(lastSeenSec, isOnline) {
            const timeObj = new Date(lastSeenSec * 1000);
            const timeStr = timeObj.toLocaleTimeString('th-TH', { hour12: false });
            
            if (isOnline) {
                return `<span class="status-badge status-online">● ออนไลน์</span> <span class="time-detail">(${timeStr})</span>`;
            }
            
            const diff = Math.floor((Date.now() / 1000) - lastSeenSec);
            let relStr = "";
            if (diff < 60) relStr = `${diff} วิที่แล้ว`;
            else if (diff < 3600) relStr = `${Math.floor(diff/60)} นาทีที่แล้ว`;
            else if (diff < 86400) relStr = `${Math.floor(diff/3600)} ชม. ที่แล้ว`;
            else relStr = `${Math.floor(diff/86400)} วันที่แล้ว`;

            return `<span class="status-badge status-offline">${relStr}</span> <span class="time-detail">(${timeStr})</span>`;
        }

        function toggleSelectAll(master) {
            const checkboxes = document.querySelectorAll('.acc-checkbox:not(#check-all)');
            checkboxes.forEach(cb => {
                cb.checked = master.checked;
                if (master.checked) selectedUsers.add(cb.value);
                else selectedUsers.delete(cb.value);
            });
            updateToolbar();
        }

        function toggleAccount(username, cb) {
            if (cb.checked) selectedUsers.add(username);
            else {
                selectedUsers.delete(username);
                document.getElementById('check-all').checked = false;
            }
            updateToolbar();
        }

        function updateToolbar() {
            const count = selectedUsers.size;
            document.getElementById('selected-badge').innerText = `(เลือก ${count})`;
            document.getElementById('btn-del-sel').disabled = count === 0;
        }

        async function deleteSelected() {
            const list = Array.from(selectedUsers);
            if (list.length === 0) return;
            if (!confirm(`ยืนยันการลบ ${list.length} ไอดีที่เลือก?`)) return;

            try {
                await fetch('/api/delete', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ usernames: list })
                });
                selectedUsers.clear();
                updateToolbar();
                document.getElementById('check-all').checked = false;
                fetchDashboard();
            } catch(e) {}
        }

        async function deleteAll() {
            if (!confirm("⚠️ คำเตือน: ต้องการล้างประวัติข้อมูลทุกไอดีทิ้งทั้งหมดใช่หรือไม่?")) return;

            try {
                await fetch('/api/delete', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ all: true })
                });
                selectedUsers.clear();
                updateToolbar();
                document.getElementById('check-all').checked = false;
                fetchDashboard();
            } catch(e) {}
        }

        function applyFilterAndRender() {
            if (!cachedData || !cachedData.accounts) return;

            const searchQuery = document.getElementById('search-input').value.toLowerCase().trim();
            const sortMode = document.getElementById('sort-select').value;
            
            let accountsList = [...cachedData.accounts];

            if (searchQuery) {
                accountsList = accountsList.filter(acc => 
                    acc.username.toLowerCase().includes(searchQuery) ||
                    (acc.fruits && acc.fruits.some(f => f.toLowerCase().includes(searchQuery)))
                );
            }

            // ระบบจัดเรียงตามลำดับที่เลือก
            if (sortMode === 'recent') {
                accountsList.sort((a, b) => (b.last_seen || 0) - (a.last_seen || 0));
            } else if (sortMode === 'online_first') {
                accountsList.sort((a, b) => {
                    if (a.is_online !== b.is_online) return a.is_online ? -1 : 1;
                    return (b.last_seen || 0) - (a.last_seen || 0);
                });
            } else if (sortMode === 'fruits_desc') {
                accountsList.sort((a, b) => ((b.fruits || []).length) - ((a.fruits || []).length));
            } else if (sortMode === 'name_asc') {
                accountsList.sort((a, b) => a.username.localeCompare(b.username));
            }

            const currentHash = JSON.stringify(accountsList.map(a => [a.username, a.is_online, a.last_seen, (a.fruits || []).join(',')]));
            if (currentHash === lastRenderHash) {
                return;
            }
            lastRenderHash = currentHash;

            const tbody = document.getElementById('account-body');
            if (accountsList.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 24px;">ℹ️ ยังไม่มีข้อมูลไอดีในระบบ</td></tr>';
            } else {
                tbody.innerHTML = accountsList.map(acc => {
                    const isChecked = selectedUsers.has(acc.username) ? 'checked' : '';
                    const fruits = acc.fruits || [];
                    return `
                        <tr>
                            <td style="text-align: center;">
                                <input type="checkbox" class="acc-checkbox" value="${acc.username}" ${isChecked} onchange="toggleAccount('${acc.username}', this)">
                            </td>
                            <td class="user-tag">${acc.username}</td>
                            <td>${formatTime(acc.last_seen, acc.is_online)}</td>
                            <td><strong>${fruits.length}</strong> ผล</td>
                            <td>${fruits.length ? fruits.map(f => `<span class="fruit-pill">${f}</span>`).join('') : '<span style="color:var(--text-muted)">- คลังว่าง -</span>'}</td>
                        </tr>
                    `;
                }).join('');
            }
        }

        async function fetchDashboard() {
            try {
                const res = await fetch('/api/data');
                if (!res.ok) return;
                const data = await res.json();
                cachedData = data;

                document.getElementById('online-val').innerText = data.online_count;
                document.getElementById('total-acc-val').innerText = data.accounts.length;
                document.getElementById('fruits-val').innerText = data.total_fruits;

                if (data.fruits) {
                    data.fruits.forEach(f => {
                        const countEl = document.getElementById(`count-${f.name}`);
                        const cardEl = document.getElementById(`card-${f.name}`);
                        if (countEl && countEl.innerText != f.count) {
                            countEl.innerText = f.count;
                            countEl.className = `fruit-count ${f.count > 0 ? 'has-stock' : ''}`;
                        }
                        if (cardEl) {
                            if (f.count > 0) cardEl.classList.add('active');
                            else cardEl.classList.remove('active');
                        }
                    });
                }

                applyFilterAndRender();
            } catch (err) {}
        }

        setInterval(fetchDashboard, 2500);
        fetchDashboard();
    </script>
</body>
</html>
"""

class DashboardServer(BaseHTTPRequestHandler):
    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        clean_path = self.path.split("?")[0].rstrip("/")
        if clean_path in ("", "/index.html"):
            response_bytes = HTML_TEMPLATE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(response_bytes)))
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(response_bytes)
        elif clean_path == "/health":
            response_bytes = b"OK - Bioatom Dashboard Active"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(response_bytes)))
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(response_bytes)
        elif clean_path == "/api/data":
            now = time.time()
            all_accounts = []
            fruit_counts = {f["name"]: 0 for f in MONITOR_FRUITS}
            total_fruits = 0
            online_count = 0

            with db_lock:
                current_accounts = dict(ACCOUNTS)

            for user, data in current_accounts.items():
                if not isinstance(data, dict):
                    continue
                last_seen = data.get("last_seen", 0)
                is_online = (now - last_seen) <= ONLINE_THRESHOLD
                if is_online:
                    online_count += 1

                fruits = data.get("fruits", [])
                if isinstance(fruits, list):
                    total_fruits += len(fruits)
                    for fr in fruits:
                        if fr in fruit_counts:
                            fruit_counts[fr] += 1

                all_accounts.append({
                    "username": user,
                    "fruits": fruits if isinstance(fruits, list) else [],
                    "last_seen": last_seen,
                    "is_online": is_online
                })

            fruits_list = [{"name": item["name"], "icon": item["icon"], "count": fruit_counts[item["name"]]} for item in MONITOR_FRUITS]

            response_data = {
                "online_count": online_count,
                "total_fruits": total_fruits,
                "fruits": fruits_list,
                "accounts": all_accounts
            }

            response_bytes = json.dumps(response_data, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response_bytes)))
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(response_bytes)
        else:
            self.send_response(404)
            self._send_cors_headers()
            self.end_headers()

    def do_POST(self):
        clean_path = self.path.split("?")[0].rstrip("/")
        if clean_path == "/report":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len)
            try:
                raw_text = body.decode("utf-8", errors="replace")
                data = json.loads(raw_text)
                user = str(data.get("username", "")).strip()
                
                if user:
                    with db_lock:
                        old_data = ACCOUNTS.get(user, {})
                        old_fruits = old_data.get("fruits", [])
                        
                        is_actual_scan = data.get("is_scan") is True
                        raw_fruits = data.get("fruits")

                        if is_actual_scan:
                            new_fruits = raw_fruits if isinstance(raw_fruits, list) else []
                        elif isinstance(raw_fruits, list) and len(raw_fruits) > 0:
                            new_fruits = raw_fruits
                        else:
                            new_fruits = old_fruits
                        
                        ACCOUNTS[user] = {
                            "fruits": new_fruits,
                            "last_seen": time.time()
                        }
                    save_db()
                    scan_tag = "📦 SCAN" if is_actual_scan else "💓 HEARTBEAT"
                    print(f"📥 [{scan_tag}] {user} | ผลไม้: {len(new_fruits)} ผล | เวลา: {time.strftime('%H:%M:%S')}")

                response_bytes = b'{"status":"ok"}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(response_bytes)))
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(response_bytes)
            except Exception as e:
                print(f"❌ [POST /report Error] {e} | Body: {body}")
                response_bytes = b'{"status":"bad_request"}'
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(response_bytes)))
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(response_bytes)
        elif clean_path == "/api/delete":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len)
            try:
                raw_text = body.decode("utf-8", errors="replace")
                data = json.loads(raw_text)
                with db_lock:
                    if data.get("all") is True:
                        ACCOUNTS.clear()
                        print("🗑️ [DB] ล้างข้อมูลทุกไอดีเรียบร้อย")
                    elif "usernames" in data and isinstance(data["usernames"], list):
                        for u in data["usernames"]:
                            if u in ACCOUNTS:
                                del ACCOUNTS[u]
                        print(f"🗑️ [DB] ลบ {len(data['usernames'])} ไอดีที่เลือก")
                save_db()

                response_bytes = b'{"status":"deleted"}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(response_bytes)))
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(response_bytes)
            except Exception as e:
                print(f"❌ [POST /api/delete Error] {e}")
                response_bytes = b'{"status":"bad_request"}'
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(response_bytes)))
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(response_bytes)
        else:
            self.send_response(404)
            self._send_cors_headers()
            self.end_headers()

if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", PORT), DashboardServer)
    print(f"🚀 [Bioatom Dashboard Ready] เปิดทำงานที่ Port: {PORT}")
    print(f"🔗 หน้าเว็บ: http://127.0.0.1:{PORT}")
    server.serve_forever()
