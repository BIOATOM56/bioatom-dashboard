import json
import time
import os
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

PORT = int(os.environ.get("PORT", 5000))
DB_FILE = "accounts_db.json"
ONLINE_THRESHOLD = 45  # วินาที: หากสคริปต์ส่งข้อมูลเข้ามาภายใน 45 วิจะนับว่ากำลังออนไลน์

# โหลดฐานข้อมูลประวัติไอดีเก่าขึ้นมาทำงาน
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

# ลิงก์รูปภาพทั้งหมด 21 ผลจาก GitHub ของคุณ
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
            --card-active: #27272a;
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

        .accounts-table-card { background-color: var(--card-bg); border: 1px solid var(--card-border); border-radius: 10px; overflow-x: auto; }
        table { width: 100%; border-collapse: collapse; text-align: left; }
        th { background-color: #040405; padding: 12px 16px; font-size: 13px; color: var(--text-muted); border-bottom: 1px solid var(--card-border); }
        td { padding: 12px 16px; font-size: 14px; border-bottom: 1px solid var(--card-border); }
        .user-tag { font-family: 'JetBrains Mono', monospace; font-weight: 600; color: #e4e4e7; }
        .status-badge { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 500; padding: 3px 8px; border-radius: 6px; }
        .status-online { color: var(--accent-green); background: rgba(16, 185, 129, 0.1); }
        .status-offline { color: var(--text-muted); background: #18181b; }
        .fruit-pill { display: inline-block; background: #121215; padding: 2px 8px; border-radius: 4px; font-size: 12px; margin: 2px; border: 1px solid #27272a; }
        
        .btn-del {
            background: transparent;
            border: 1px solid #3f3f46;
            color: #a1a1aa;
            padding: 5px 10px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 12px;
            transition: all 0.2s;
        }
        .btn-del:hover { background: var(--accent-red); border-color: var(--accent-red); color: #fff; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Bioatom Overview</h1>
        <div class="pulse-badge"><div class="pulse-dot"></div> Pure Cloud Monitor</div>
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
    <div class="accounts-table-card">
        <table>
            <thead>
                <tr>
                    <th>Account Name</th>
                    <th>Status / Last Active</th>
                    <th>Total Count</th>
                    <th>Storage Details</th>
                    <th style="text-align: right;">Action</th>
                </tr>
            </thead>
            <tbody id="account-body">
                <tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 24px;">กำลังโหลดฐานข้อมูล...</td></tr>
            </tbody>
        </table>
    </div>

    <script>
        function formatTime(lastSeenSec, isOnline) {
            if (isOnline) return '<span class="status-badge status-online">● ออนไลน์</span>';
            const diff = Math.floor((Date.now() / 1000) - lastSeenSec);
            if (diff < 60) return `<span class="status-badge status-offline">${diff} วิที่แล้ว</span>`;
            if (diff < 3600) return `<span class="status-badge status-offline">${Math.floor(diff/60)} นาทีที่แล้ว</span>`;
            if (diff < 86400) return `<span class="status-badge status-offline">${Math.floor(diff/3600)} ชม. ที่แล้ว</span>`;
            return `<span class="status-badge status-offline">${Math.floor(diff/86400)} วันที่แล้ว</span>`;
        }

        async function deleteAccount(username) {
            if (!confirm(`ยืนยันการลบประวัติไอดี "${username}" ออกจากระบบ?`)) return;
            try {
                await fetch('/api/delete', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username: username })
                });
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

                const tbody = document.getElementById('account-body');
                if (data.accounts.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 24px;">ไม่มีประวัติข้อมูลไอดีในระบบ</td></tr>';
                } else {
                    tbody.innerHTML = data.accounts.map(acc => `
                        <tr>
                            <td class="user-tag">${acc.username}</td>
                            <td>${formatTime(acc.last_seen, acc.is_online)}</td>
                            <td><strong>${acc.fruits.length}</strong> ผล</td>
                            <td>${acc.fruits.length ? acc.fruits.map(f => `<span class="fruit-pill">${f}</span>`).join('') : '<span style="color:var(--text-muted)">- คลังว่าง -</span>'}</td>
                            <td style="text-align: right;">
                                <button class="btn-del" onclick="deleteAccount('${acc.username}')">🗑️ ลบข้อมูล</button>
                            </td>
                        </tr>
                    `).join('');
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

            # เรียงไอดี: คนที่ออนไลน์อยู่ขึ้นก่อน ตามด้วยคนที่เพิ่งออฟไลน์
            all_accounts.sort(key=lambda x: (not x["is_online"], -x["last_seen"]))

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
                user = data.get("username")
                if user and user in ACCOUNTS:
                    del ACCOUNTS[user]
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
