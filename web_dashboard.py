import json
import time
import os
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

PORT = int(os.environ.get("PORT", 5000))
DB_FILE = "accounts_db.json"
ONLINE_THRESHOLD = 25  # วินาที: หากส่งข้อมูลภายใน 25 วิ ถือว่าออนไลน์

ACCOUNTS = {}
if os.path.exists(DB_FILE):
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            ACCOUNTS = json.load(f)
    except Exception:
        ACCOUNTS = {}

def save_db():
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(ACCOUNTS, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

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
        }
        .fruit-card.active { border-color: rgba(16, 185, 129, 0.4); background: rgba(16, 185, 129, 0.03); }
        .fruit-icon { width: 42px; height: 42px; object-fit: contain; background: #000000; border-radius: 6px; padding: 2px; }
        .fruit-info { display: flex; flex-direction: column; }
        .fruit-name { font-size: 13px; font-weight: 500; }
        .fruit-count { font-size: 17px; font-weight: 700; font-family: 'JetBrains Mono', monospace; color: var(--accent-red); }
        .fruit-count.has-stock { color: var(--accent-green); }

        /* แถบเครื่องมือจัดการ */
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
        .left-controls { display: flex; align-items: center; gap: 18px; font-size: 14px; }
        .toggle-sort { display: flex; align-items: center; gap: 8px; cursor: pointer; user-select: none; color: #d4d4d8; font-weight: 400; }
        .toggle-sort input { accent-color: var(--accent-blue); width: 16px; height: 16px; cursor: pointer; }
        .select-group { display: flex; align-items: center; gap: 8px; }
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
    <div class="grid-container" id="fruit-grid"></div>

    <div class="section-title">👤 Account Storage Details & History</div>
    
    <div class="table-toolbar">
        <div class="left-controls">
            <div class="select-group">
                <input type="checkbox" id="check-all" class="acc-checkbox" onchange="toggleSelectAll(this)">
                <label for="check-all" style="cursor:pointer;">เลือกทั้งหมด</label>
                <span id="selected-badge" style="color: var(--text-muted); font-size: 13px;">(เลือก 0)</span>
            </div>
            <label class="toggle-sort">
                <input type="checkbox" id="sort-online-toggle" onchange="fetchDashboard()">
                <span>📌 เอาไอดีออนไลน์ขึ้นด้านบน</span>
            </label>
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
                <tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 24px;">กำลังรอการเชื่อมต่อ...</td></tr>
            </tbody>
        </table>
    </div>

    <script>
        const selectedUsers = new Set();

        function formatTime(lastSeenSec, isOnline) {
            if (isOnline) return '<span class="status-badge status-online">● ออนไลน์</span>';
            const diff = Math.floor((Date.now() / 1000) - lastSeenSec);
            if (diff < 60) return `<span class="status-badge status-offline">${diff} วิที่แล้ว</span>`;
            if (diff < 3600) return `<span class="status-badge status-offline">${Math.floor(diff/60)} นาทีที่แล้ว</span>`;
            if (diff < 86400) return `<span class="status-badge status-offline">${Math.floor(diff/3600)} ชม. ที่แล้ว</span>`;
            return `<span class="status-badge status-offline">${Math.floor(diff/86400)} วันที่แล้ว</span>`;
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
            if (!confirm("⚠️ คำเตือน: คุณต้องการล้างประวัติข้อมูลทุกไอดีทิ้งทั้งหมดใช่หรือไม่?")) return;

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

        async function fetchDashboard() {
            try {
                const res = await fetch('/api/data');
                const data = await res.json();
                
                document.getElementById('online-val').innerText = data.online_count;
                document.getElementById('total-acc-val').innerText = data.accounts.length;
                document.getElementById('fruits-val').innerText = data.total_fruits;

                const grid = document.getElementById('fruit-grid');
                grid.innerHTML = data.fruits.map(f => `
                    <div class="fruit-card ${f.count > 0 ? 'active' : ''}">
                        <img class="fruit-icon" 
                             src="${f.icon}" 
                             onerror="this.onerror=null; this.src='data:image/svg+xml;utf8,<svg xmlns=\\'http://www.w3.org/2000/svg\\' width=\\'42\\' height=\\'42\\' viewBox=\\'0 0 24 24\\' fill=\\'none\\' stroke=\\'%23525f73\\' stroke-width=\\'2\\'><rect width=\\'18\\' height=\\'18\\' x=\\'3\\' y=\\'3\\' rx=\\'2\\'/><circle cx=\\'8.5\\' cy=\\'8.5\\' r=\\'1.5\\'/><path d=\\'m21 15-5-5L5 21\\'/></svg>';">
                        <div class="fruit-info">
                            <span class="fruit-name">${f.name}</span>
                            <span class="fruit-count ${f.count > 0 ? 'has-stock' : ''}">${f.count}</span>
                        </div>
                    </div>
                `).join('');

                // การจัดเรียง: หากติ๊กเลือก ให้เอาออนไลน์ขึ้นบน หากไม่ติ๊ก ให้เรียงชื่อตามตัวอักษรคงที่ (ไม่เด้งสลับ)
                const sortOnlineFirst = document.getElementById('sort-online-toggle').checked;
                const accountsList = [...data.accounts];
                if (sortOnlineFirst) {
                    accountsList.sort((a, b) => {
                        if (a.is_online !== b.is_online) return a.is_online ? -1 : 1;
                        return a.username.localeCompare(b.username);
                    });
                } else {
                    accountsList.sort((a, b) => a.username.localeCompare(b.username));
                }

                const tbody = document.getElementById('account-body');
                if (accountsList.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 24px;">ไม่มีประวัติข้อมูลไอดีในระบบ</td></tr>';
                } else {
                    tbody.innerHTML = accountsList.map(acc => {
                        const isChecked = selectedUsers.has(acc.username) ? 'checked' : '';
                        return `
                            <tr>
                                <td style="text-align: center;">
                                    <input type="checkbox" class="acc-checkbox" value="${acc.username}" ${isChecked} onchange="toggleAccount('${acc.username}', this)">
                                </td>
                                <td class="user-tag">${acc.username}</td>
                                <td>${formatTime(acc.last_seen, acc.is_online)}</td>
                                <td><strong>${acc.fruits.length}</strong> ผล</td>
                                <td>${acc.fruits.length ? acc.fruits.map(f => `<span class="fruit-pill">${f}</span>`).join('') : '<span style="color:var(--text-muted)">- คลังว่าง -</span>'}</td>
                            </tr>
                        `;
                    }).join('');
                }
            } catch (err) {}
        }

        setInterval(fetchDashboard, 2000);
        fetchDashboard();
    </script>
</body>
</html>
"""

class DashboardServer(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode("utf-8"))
        elif self.path == "/api/data":
            now = time.time()
            all_accounts = []
            fruit_counts = {f["name"]: 0 for f in MONITOR_FRUITS}
            total_fruits = 0
            online_count = 0

            for user, data in list(ACCOUNTS.items()):
                last_seen = data.get("last_seen", 0)
                is_online = (now - last_seen) <= ONLINE_THRESHOLD
                if is_online:
                    online_count += 1

                fruits = data.get("fruits", [])
                total_fruits += len(fruits)
                for fr in fruits:
                    if fr in fruit_counts:
                        fruit_counts[fr] += 1

                all_accounts.append({
                    "username": user,
                    "fruits": fruits,
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

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(response_data).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/report":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len)
            try:
                data = json.loads(body.decode("utf-8"))
                user = data.get("username")
                fruits = data.get("fruits", [])
                if user:
                    ACCOUNTS[user] = {"fruits": fruits, "last_seen": time.time()}
                    save_db()
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"status":"ok"}')
            except Exception:
                self.send_response(400)
                self.end_headers()
        elif self.path == "/api/delete":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len)
            try:
                data = json.loads(body.decode("utf-8"))
                if data.get("all") is True:
                    ACCOUNTS.clear()
                    save_db()
                elif "usernames" in data and isinstance(data["usernames"], list):
                    for u in data["usernames"]:
                        if u in ACCOUNTS:
                            del ACCOUNTS[u]
                    save_db()
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"status":"deleted"}')
            except Exception:
                self.send_response(400)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        return

if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", PORT), DashboardServer)
    server.serve_forever()
