import json
import time
import os
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

PORT = int(os.environ.get("PORT", 5000))
OFFLINE_TIMEOUT = 15

ACCOUNTS = {}

# ลิงก์ตรงดึงไฟล์จาก GitHub คลังของคุณ
GITHUB_RAW = "https://raw.githubusercontent.com/BIOATOM56/bioatom-dashboard/main/"

# รายการผลไม้พร้อมชี้ตรงไปยังไฟล์ .webp ที่อัปโหลดไว้
FRUITS_CONFIG = [
    {"name": "Kitsune", "file": "Kitsune_Fruit.webp"},
    {"name": "Dragon", "file": "Dragon_Fruit.webp"},
    {"name": "Yeti", "file": "Yeti_Fruit.webp"},
    {"name": "Tiger", "file": "Tiger_Fruit.webp"},      # หากตั้งชื่อเป็น Leopard ระบบจะสลับให้ออโต้
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

MONITOR_FRUITS = [
    {
        "name": item["name"],
        "icon": f"{GITHUB_RAW}{item['file']}"
    }
    for item in FRUITS_CONFIG
]

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <title>Bioatom Inventory Dashboard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link href="https://fonts.googleapis.com/css2?family=Kanit:wght@300;400;600&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #0b0e14;
            --card-bg: #151922;
            --card-border: #232936;
            --text-main: #f0f3f8;
            --text-muted: #7e8b9b;
            --accent-green: #00e676;
            --accent-red: #ff3366;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Kanit', sans-serif; }
        body { background-color: var(--bg-color); color: var(--text-main); padding: 25px; min-height: 100vh; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px; }
        .header h1 { font-size: 24px; font-weight: 600; letter-spacing: 0.5px; }
        .pulse-badge { display: inline-flex; align-items: center; gap: 8px; font-size: 13px; color: var(--accent-green); background: rgba(0, 230, 118, 0.1); padding: 6px 14px; border-radius: 20px; border: 1px solid rgba(0, 230, 118, 0.2); }
        .pulse-dot { width: 8px; height: 8px; background-color: var(--accent-green); border-radius: 50%; box-shadow: 0 0 10px var(--accent-green); }

        .overview-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 25px; }
        .stat-card { background-color: var(--card-bg); border: 1px solid var(--card-border); border-radius: 12px; padding: 18px; }
        .stat-title { font-size: 13px; color: var(--text-muted); margin-bottom: 6px; }
        .stat-value { font-size: 26px; font-weight: 700; font-family: 'JetBrains Mono', monospace; }

        .section-title { font-size: 18px; font-weight: 600; margin-bottom: 15px; }
        .grid-container { display: grid; grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); gap: 12px; margin-bottom: 30px; }
        
        .fruit-card {
            background-color: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 12px;
            padding: 12px 14px;
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .fruit-card.active { border-color: rgba(0, 230, 118, 0.4); background: rgba(0, 230, 118, 0.05); }
        .fruit-icon { width: 44px; height: 44px; object-fit: contain; background: #1a1f2c; border-radius: 8px; padding: 2px; }
        .fruit-info { display: flex; flex-direction: column; }
        .fruit-name { font-size: 14px; font-weight: 500; }
        .fruit-count { font-size: 18px; font-weight: 700; font-family: 'JetBrains Mono', monospace; color: var(--accent-red); }
        .fruit-count.has-stock { color: var(--accent-green); }

        .accounts-table-card { background-color: var(--card-bg); border: 1px solid var(--card-border); border-radius: 12px; overflow: hidden; }
        table { width: 100%; border-collapse: collapse; text-align: left; }
        th { background-color: rgba(255, 255, 255, 0.02); padding: 14px 18px; font-size: 13px; color: var(--text-muted); border-bottom: 1px solid var(--card-border); }
        td { padding: 14px 18px; font-size: 14px; border-bottom: 1px solid rgba(255, 255, 255, 0.03); }
        .user-tag { font-family: 'JetBrains Mono', monospace; font-weight: 600; color: #64b5f6; }
        .fruit-pill { display: inline-block; background: #232936; padding: 3px 8px; border-radius: 6px; font-size: 12px; margin: 2px; border: 1px solid #313848; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Bioatom Overview</h1>
        <div class="pulse-badge"><div class="pulse-dot"></div> Live Sync Active</div>
    </div>

    <div class="overview-cards">
        <div class="stat-card">
            <div class="stat-title">Online Accounts</div>
            <div class="stat-value" id="online-val" style="color: var(--accent-green);">0</div>
        </div>
        <div class="stat-card">
            <div class="stat-title">Total Fruits Found</div>
            <div class="stat-value" id="fruits-val">0</div>
        </div>
        <div class="stat-card">
            <div class="stat-title">Tracked Types</div>
            <div class="stat-value" id="types-val">21</div>
        </div>
    </div>

    <div class="section-title">📦 Item Monitor</div>
    <div class="grid-container" id="fruit-grid"></div>

    <div class="section-title">👤 Account Storage Details</div>
    <div class="accounts-table-card">
        <table>
            <thead>
                <tr>
                    <th>Account Name</th>
                    <th>Fruits Count</th>
                    <th>Storage Content</th>
                    <th>Last Active</th>
                </tr>
            </thead>
            <tbody id="account-body">
                <tr><td colspan="4" style="text-align: center; color: var(--text-muted);">กำลังรอการเชื่อมต่อจากเกม...</td></tr>
            </tbody>
        </table>
    </div>

    <script>
        function handleImgError(img, fruitName) {
            if (fruitName === 'Tiger' && !img.dataset.tried) {
                img.dataset.tried = 'true';
                img.src = 'https://raw.githubusercontent.com/BIOATOM56/bioatom-dashboard/main/Leopard_Fruit.webp';
                return;
            }
            img.onerror = null;
            img.src = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='44' height='44' viewBox='0 0 24 24' fill='none' stroke='%23525f73' stroke-width='2'><rect width='18' height='18' x='3' y='3' rx='2'/><circle cx='8.5' cy='8.5' r='1.5'/><path d='m21 15-5-5L5 21'/></svg>";
        }

        async function fetchDashboard() {
            try {
                const res = await fetch('/api/data');
                const data = await res.json();
                
                document.getElementById('online-val').innerText = data.online_count;
                document.getElementById('fruits-val').innerText = data.total_fruits;

                const grid = document.getElementById('fruit-grid');
                grid.innerHTML = data.fruits.map(f => `
                    <div class="fruit-card ${f.count > 0 ? 'active' : ''}">
                        <img class="fruit-icon" 
                             src="${f.icon}" 
                             onerror="handleImgError(this, '${f.name}')">
                        <div class="fruit-info">
                            <span class="fruit-name">${f.name}</span>
                            <span class="fruit-count ${f.count > 0 ? 'has-stock' : ''}">${f.count}</span>
                        </div>
                    </div>
                `).join('');

                const tbody = document.getElementById('account-body');
                if (data.accounts.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: var(--text-muted);">ไม่มีไอดีออนไลน์ในขณะนี้</td></tr>';
                } else {
                    tbody.innerHTML = data.accounts.map(acc => `
                        <tr>
                            <td class="user-tag">🟢 ${acc.username}</td>
                            <td><strong>${acc.fruits.length}</strong> ผล</td>
                            <td>${acc.fruits.length ? acc.fruits.map(f => `<span class="fruit-pill">${f}</span>`).join('') : '<span style="color:var(--text-muted)">- คลังว่าง -</span>'}</td>
                            <td style="color: var(--text-muted); font-size: 13px;">${acc.time_ago}s ago</td>
                        </tr>
                    `).join('');
                }
            } catch (err) {}
        }

        setInterval(fetchDashboard, 1000);
        fetchDashboard();
    </script>
</body>
</html>
"""

class DashboardServer(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode("utf-8"))
        elif self.path == "/api/data":
            now = time.time()
            online_accounts = []
            fruit_counts = {f["name"]: {"count": 0, "users": []} for f in MONITOR_FRUITS}
            total_fruits = 0

            for user, data in list(ACCOUNTS.items()):
                time_diff = int(now - data["last_seen"])
                if time_diff <= OFFLINE_TIMEOUT:
                    online_accounts.append({
                        "username": user,
                        "fruits": data["fruits"],
                        "time_ago": time_diff
                    })
                    for fruit in data["fruits"]:
                        total_fruits += 1
                        if fruit in fruit_counts:
                            fruit_counts[fruit]["count"] += 1
                            if user not in fruit_counts[fruit]["users"]:
                                fruit_counts[fruit]["users"].append(user)
                else:
                    del ACCOUNTS[user]

            fruits_list = []
            for item in MONITOR_FRUITS:
                f_name = item["name"]
                fruits_list.append({
                    "name": f_name,
                    "icon": item["icon"],
                    "count": fruit_counts[f_name]["count"],
                    "users": fruit_counts[f_name]["users"]
                })

            response_data = {
                "online_count": len(online_accounts),
                "total_fruits": total_fruits,
                "fruits": fruits_list,
                "accounts": online_accounts
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
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"status":"ok"}')
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
