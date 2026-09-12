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
PERSIST_INTERVAL = 3.0
SAVE_RETRIES = 3
SAVE_RETRY_DELAY = 0.25
LOG_FILE = "system_trace.log"
MAX_BODY_BYTES = 1024 * 1024

# Synchronization & Memory Core
db_lock = threading.RLock()
save_lock = threading.Lock()
ACCOUNTS = {}
DB_SOURCE = "NEW"

# 2-Tier Revision Engine
DATA_REVISION = 0    # ขยับเฉพาะตอน Inventory เปลี่ยนแปลง หรือลบ/เพิ่มไอดี
SAVED_REVISION = 0   # Revision ล่าสุดที่เขียนลงดิสก์สำเร็จ
IS_DIRTY = False
DIRTY_SINCE = 0.0
APP_RUNNING = True

# Observability Engine
METRICS = {
    "server_start": time.time(),
    "total_reports": 0,
    "total_scans": 0,
    "total_heartbeats": 0,
    "total_saves": 0,
    "total_save_failures": 0,
    "consecutive_save_failures": 0,
    "last_save_time": 0,
    "last_save_duration_ms": 0,
    "last_save_error": None
}

def log_event(level, context, message, exc=None):
    """บันทึกเหตุการณ์สำคัญลง system_trace.log โดยไม่ทำให้ request หลักล้ม"""
    try:
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{stamp}] [{level}] [{context}] {message}"
        if exc is not None:
            line += f" | {type(exc).__name__}: {exc}"
        line += "\n"
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass

def _atomic_replace_with_retry(src, dst):
    last_exc = None
    for attempt in range(1, SAVE_RETRIES + 1):
        try:
            os.replace(src, dst)
            return True
        except PermissionError as exc:
            last_exc = exc
            if attempt < SAVE_RETRIES:
                time.sleep(SAVE_RETRY_DELAY * attempt)
    if last_exc:
        raise last_exc
    return False

def load_db():
    global ACCOUNTS, DB_SOURCE, DATA_REVISION, SAVED_REVISION, IS_DIRTY, DIRTY_SINCE
    with db_lock:
        for file_path, source_label in [(DB_FILE, "PRIMARY"), (DB_BAK_FILE, "BACKUP")]:
            if os.path.exists(file_path):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, dict):
                            normalized = {}
                            now = time.time()
                            for u, acc in data.items():
                                if not isinstance(acc, dict):
                                    continue
                                l_seen = acc.get("last_seen", now)
                                normalized[u] = {
                                    "fruits": acc.get("fruits", []) if isinstance(acc.get("fruits"), list) else [],
                                    "last_seen": l_seen,
                                    "last_heartbeat": acc.get("last_heartbeat", l_seen),
                                    "last_scan": acc.get("last_scan", l_seen if acc.get("fruits") else 0),
                                    "inventory_updated_at": acc.get("inventory_updated_at", l_seen if acc.get("fruits") else 0)
                                }
                            ACCOUNTS = normalized
                            DB_SOURCE = source_label
                            DATA_REVISION = 1
                            SAVED_REVISION = 1
                            print(f"📦 [DB Core] โหลดฐานข้อมูลสำเร็จจาก: {source_label} ({len(ACCOUNTS)} ไอดี)")
                            return
                except Exception as e:
                    print(f"⚠️ [DB Warning] อ่าน {file_path} ไม่สำเร็จ: {e}")
        ACCOUNTS = {}
        DB_SOURCE = "EMPTY_NEW"

load_db()

def flush_db_to_disk(force=False):
    """Snapshot persistence: lock เฉพาะตอนคัดลอก state แล้วเขียน disk นอก lock"""
    global IS_DIRTY, SAVED_REVISION, DIRTY_SINCE
    with save_lock:
        with db_lock:
            if not IS_DIRTY and not force:
                return True

            snapshot = {}
            for u, d in ACCOUNTS.items():
                snapshot[u] = {
                    "fruits": list(d.get("fruits", [])),
                    "last_scan": d.get("last_scan", 0),
                    "inventory_updated_at": d.get("inventory_updated_at", 0)
                }
            target_rev = DATA_REVISION

        t0 = time.time()
        temp_file = DB_FILE + ".tmp"
        backup_temp = DB_BAK_FILE + ".tmp"
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(snapshot, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())

            _atomic_replace_with_retry(temp_file, DB_FILE)

            # Backup เป็น second-stage protection; primary ที่เขียนสำเร็จไม่ควรถูกมองว่า fail
            try:
                shutil.copy2(DB_FILE, backup_temp)
                _atomic_replace_with_retry(backup_temp, DB_BAK_FILE)
            except Exception as backup_exc:
                log_event("WARN", "persistence.backup", "สำรอง .bak ไม่สำเร็จ แต่ primary save สำเร็จ", backup_exc)
                if os.path.exists(backup_temp):
                    try:
                        os.remove(backup_temp)
                    except Exception:
                        pass

            duration_ms = int((time.time() - t0) * 1000)
            with db_lock:
                SAVED_REVISION = max(SAVED_REVISION, target_rev)
                if DATA_REVISION == target_rev:
                    IS_DIRTY = False
                    DIRTY_SINCE = 0.0

            METRICS["total_saves"] += 1
            METRICS["consecutive_save_failures"] = 0
            METRICS["last_save_time"] = time.time()
            METRICS["last_save_duration_ms"] = duration_ms
            METRICS["last_save_error"] = None
            return True

        except Exception as exc:
            METRICS["total_save_failures"] += 1
            METRICS["consecutive_save_failures"] += 1
            METRICS["last_save_error"] = str(exc)
            log_event("ERROR", "persistence.primary", "เขียนฐานข้อมูลไม่สำเร็จ", exc)
            print(f"❌ [DB Flush Error] ล้มเหลว: {exc}")
            with db_lock:
                IS_DIRTY = True
                if DIRTY_SINCE <= 0:
                    DIRTY_SINCE = time.time()
            for tmp in (temp_file, backup_temp):
                if os.path.exists(tmp):
                    try:
                        os.remove(tmp)
                    except Exception:
                        pass
            return False

def persistence_worker():
    while APP_RUNNING:
        time.sleep(PERSIST_INTERVAL)
        if IS_DIRTY:
            flush_db_to_disk()

threading.Thread(target=persistence_worker, daemon=True).start()

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
            --accent-yellow: #f59e0b;
            --accent-blue: #3b82f6;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Kanit', sans-serif; }
        body { background-color: var(--bg-color); color: var(--text-main); padding: 25px; min-height: 100vh; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px; flex-wrap: wrap; gap: 10px; }
        .header h1 { font-size: 24px; font-weight: 600; letter-spacing: 0.5px; }
        
        .header-badges { display: flex; gap: 10px; align-items: center; }
        .pulse-badge { display: inline-flex; align-items: center; gap: 8px; font-size: 13px; padding: 6px 14px; border-radius: 20px; transition: all 0.3s ease; }
        .status-connected { color: var(--accent-green); background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.2); }
        .status-reconnecting { color: var(--accent-yellow); background: rgba(245, 158, 11, 0.08); border: 1px solid rgba(245, 158, 11, 0.2); }
        .status-disconnected { color: var(--accent-red); background: rgba(239, 68, 68, 0.08); border: 1px solid rgba(239, 68, 68, 0.2); }
        .backup-warning-badge { color: var(--accent-yellow); background: rgba(245, 158, 11, 0.12); border: 1px solid rgba(245, 158, 11, 0.4); padding: 6px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; display: none; }
        
        .pulse-dot { width: 8px; height: 8px; border-radius: 50%; }
        .dot-green { background-color: var(--accent-green); box-shadow: 0 0 10px var(--accent-green); }
        .dot-yellow { background-color: var(--accent-yellow); box-shadow: 0 0 10px var(--accent-yellow); }
        .dot-red { background-color: var(--accent-red); box-shadow: 0 0 10px var(--accent-red); }
        .last-update-text { font-size: 11px; color: var(--text-muted); font-family: 'JetBrains Mono', monospace; }

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
        .scan-subtext { display: block; font-size: 11px; color: #71717a; margin-top: 3px; font-family: 'JetBrains Mono', monospace; }
        .fruit-pill { display: inline-block; background: #121215; padding: 2px 8px; border-radius: 4px; font-size: 12px; margin: 2px; border: 1px solid #27272a; }

        input[type="checkbox"].acc-checkbox { width: 16px; height: 16px; accent-color: var(--accent-green); cursor: pointer; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Bioatom Overview</h1>
        <div class="header-badges">
            <div id="backup-badge" class="backup-warning-badge">⚠️ RUNNING FROM BACKUP (.BAK)</div>
            <span class="last-update-text" id="last-update-label">อัปเดตล่าสุด: กำลังเชื่อมต่อ...</span>
            <div class="pulse-badge status-connected" id="connection-status-badge">
                <div class="pulse-dot dot-green" id="connection-dot"></div>
                <span id="connection-status-text">🟢 LIVE</span>
            </div>
        </div>
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
        let lastSuccessFetch = Date.now();
        let consecutiveErrors = 0;
        let clientRevision = 0;

        function setConnectionState(state) {
            const badge = document.getElementById('connection-status-badge');
            const dot = document.getElementById('connection-dot');
            const text = document.getElementById('connection-status-text');
            
            badge.className = 'pulse-badge';
            dot.className = 'pulse-dot';

            if (state === 'online') {
                badge.classList.add('status-connected');
                dot.classList.add('dot-green');
                text.innerText = '🟢 LIVE';
            } else if (state === 'reconnecting') {
                badge.classList.add('status-reconnecting');
                dot.classList.add('dot-yellow');
                text.innerText = '🟡 RECONNECTING...';
            } else {
                badge.classList.add('status-disconnected');
                dot.classList.add('dot-red');
                text.innerText = '🔴 BACKEND OFFLINE';
            }
        }

        function formatRelativeTime(epochSec) {
            if (!epochSec || epochSec <= 0) return "ไม่เคยสแกน";
            const diff = Math.floor((Date.now() / 1000) - epochSec);
            if (diff < 60) return `${diff} วิที่แล้ว`;
            if (diff < 3600) return `${Math.floor(diff/60)} นาทีที่แล้ว`;
            if (diff < 86400) return `${Math.floor(diff/3600)} ชม. ที่แล้ว`;
            return `${Math.floor(diff/86400)} วันที่แล้ว`;
        }

        function formatTime(lastSeenSec, isOnline, lastScanSec) {
            const timeObj = new Date(lastSeenSec * 1000);
            const timeStr = timeObj.toLocaleTimeString('th-TH', { hour12: false });
            const scanRel = formatRelativeTime(lastScanSec);
            
            let statusHtml = "";
            if (isOnline) {
                statusHtml = `<span class="status-badge status-online">● ออนไลน์</span> <span class="time-detail">(${timeStr})</span>`;
            } else {
                const diff = Math.floor((Date.now() / 1000) - lastSeenSec);
                let relStr = diff < 60 ? `${diff} วิที่แล้ว` : (diff < 3600 ? `${Math.floor(diff/60)} นาทีที่แล้ว` : `${Math.floor(diff/3600)} ชม. ที่แล้ว`);
                statusHtml = `<span class="status-badge status-offline">${relStr}</span> <span class="time-detail">(${timeStr})</span>`;
            }

            const scanSub = `<span class="scan-subtext">🔍 สแกนคลัง: ${scanRel}</span>`;
            return statusHtml + scanSub;
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
                clientRevision = 0; // บังคับดึงข้อมูลใหม่ทันที
                fetchDashboard();
            } catch(e) {
                alert(e.message || 'ลบข้อมูลไม่สำเร็จ');
            }
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
                clientRevision = 0;
                fetchDashboard();
            } catch(e) {
                alert(e.message || 'ล้างข้อมูลไม่สำเร็จ');
            }
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

            const currentHash = JSON.stringify(accountsList.map(a => [a.username, a.is_online, a.last_seen, a.last_scan, (a.fruits || []).join(',')]));
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
                            <td>${formatTime(acc.last_seen, acc.is_online, acc.last_scan)}</td>
                            <td><strong>${fruits.length}</strong> ผล</td>
                            <td>${fruits.length ? fruits.map(f => `<span class="fruit-pill">${f}</span>`).join('') : '<span style="color:var(--text-muted)">- คลังว่าง -</span>'}</td>
                        </tr>
                    `;
                }).join('');
            }
        }

        async function fetchData(force = false) {
            try {
                const headers = {};
                if (!force && clientETag) headers['If-None-Match'] = clientETag;

                const res = await fetch('/api/data', { headers, cache: 'no-store' });
                if (res.status === 304) return true;
                if (!res.ok) throw new Error(`HTTP ${res.status}`);

                const newETag = res.headers.get('ETag');
                if (newETag) clientETag = newETag;
                const data = await res.json();
                cachedData = data;

                const backupBadge = document.getElementById('backup-badge');
                backupBadge.style.display = data.db_source === 'BACKUP' ? 'inline-flex' : 'none';

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
                return true;
            } catch (err) {
                return false;
            }
        }

        async function fetchPresence() {
            try {
                const res = await fetch('/api/presence', { cache: 'no-store' });
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                const presence = await res.json();

                // ถ้า persistent data เปลี่ยนหรือจำนวนบัญชีเปลี่ยน ให้ refresh /api/data
                const cachedNames = new Set((cachedData.accounts || []).map(a => a.username));
                const presenceNames = new Set((presence.accounts || []).map(a => a.username));
                const structureChanged = cachedData.revision !== presence.data_revision ||
                    cachedNames.size !== presenceNames.size ||
                    [...presenceNames].some(name => !cachedNames.has(name));

                if (structureChanged) {
                    await fetchData(true);
                }

                const presenceMap = new Map(presence.accounts.map(a => [a.username, a]));
                cachedData.accounts = (cachedData.accounts || []).map(acc => {
                    const p = presenceMap.get(acc.username);
                    if (!p) return { ...acc, is_online: false, last_seen: 0, last_heartbeat: 0 };
                    return { ...acc, is_online: p.is_online, last_seen: p.last_seen, last_heartbeat: p.last_heartbeat };
                });
                cachedData.online_count = presence.online_count;

                document.getElementById('online-val').innerText = presence.online_count;
                applyFilterAndRender();
                return true;
            } catch (err) {
                return false;
            }
        }

        async function refreshDashboard() {
            const [presenceOk] = await Promise.all([fetchPresence()]);
            if (!presenceOk) throw new Error('Presence request failed');
            lastSuccessFetch = Date.now();
            consecutiveErrors = 0;
            setConnectionState('online');
        }

        async function scheduledRefresh() {
            try {
                await refreshDashboard();
            } catch (err) {
                consecutiveErrors++;
                setConnectionState(consecutiveErrors < 3 ? 'reconnecting' : 'disconnected');
            }
        }

        setInterval(() => {
            const sec = Math.floor((Date.now() - lastSuccessFetch) / 1000);
            const label = document.getElementById('last-update-label');
            if (consecutiveErrors > 2) {
                label.innerText = `ขาดการติดต่อไป ${sec} วินาทีแล้ว`;
                label.style.color = "var(--accent-red)";
            } else {
                label.innerText = `อัปเดตล่าสุด: ${sec} วิที่แล้ว`;
                label.style.color = "var(--text-muted)";
            }
        }, 1000);

        setInterval(scheduledRefresh, 2500);
        (async () => {
            const ok = await fetchData(true);
            if (!ok) {
                consecutiveErrors = 3;
                setConnectionState('disconnected');
                return;
            }
            await scheduledRefresh();
        })();
    </script>
</body>
</html>
"""

class DashboardServer(BaseHTTPRequestHandler):
    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, If-None-Match")

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
            query = self.path.split("?")[1] if "?" in self.path else ""
            if "json=1" in query or "application/json" in self.headers.get("Accept", ""):
                now = time.time()
                # Self-healing status: ประเมินจากความผิดพลาดสะสมล่าสุด (consecutive) ไม่ยึดอดีต
                with db_lock:
                    dirty_age = (now - DIRTY_SINCE) if IS_DIRTY and DIRTY_SINCE > 0 else 0
                    data_revision = DATA_REVISION
                    saved_revision = SAVED_REVISION
                    is_dirty = IS_DIRTY
                    account_count = len(ACCOUNTS)
                is_healthy = METRICS["consecutive_save_failures"] == 0
                health_info = {
                    "status": "healthy" if is_healthy else "degraded",
                    "uptime_seconds": int(now - METRICS["server_start"]),
                    "db_source": DB_SOURCE,
                    "data_revision": data_revision,
                    "saved_revision": saved_revision,
                    "is_dirty": is_dirty,
                    "unsaved_age_seconds": round(dirty_age, 2),
                    "metrics": METRICS,
                    "accounts_in_memory": account_count
                }
                res_bytes = json.dumps(health_info, ensure_ascii=False, indent=2).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(res_bytes)))
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(res_bytes)
            else:
                response_bytes = b"OK - Bioatom Dashboard Active"
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(response_bytes)))
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(response_bytes)

        elif clean_path == "/api/data":
            # ETag ใช้เฉพาะ Persistent Data เพราะ presence ถูกแยกไป /api/presence
            with db_lock:
                current_rev = DATA_REVISION
                current_accounts = {u: dict(d) for u, d in ACCOUNTS.items()}

            client_etag = self.headers.get("If-None-Match", "").strip()
            server_etag = f'"{current_rev}"'
            if client_etag and client_etag == server_etag:
                self.send_response(304)
                self._send_cors_headers()
                self.send_header("ETag", server_etag)
                self.end_headers()
                return

            fruit_counts = {f["name"]: 0 for f in MONITOR_FRUITS}
            total_fruits = 0
            all_accounts = []

            for user, data in current_accounts.items():
                fruits = data.get("fruits", [])
                if isinstance(fruits, list):
                    total_fruits += len(fruits)
                    for fr in fruits:
                        if fr in fruit_counts:
                            fruit_counts[fr] += 1

                all_accounts.append({
                    "username": user,
                    "fruits": fruits if isinstance(fruits, list) else [],
                    "last_seen": data.get("last_seen", 0),
                    "last_heartbeat": data.get("last_heartbeat", 0),
                    "last_scan": data.get("last_scan", 0),
                    "inventory_updated_at": data.get("inventory_updated_at", 0),
                    "is_online": False
                })

            fruits_list = [{"name": item["name"], "icon": item["icon"], "count": fruit_counts[item["name"]]} for item in MONITOR_FRUITS]
            response_data = {
                "revision": current_rev,
                "db_source": DB_SOURCE,
                "total_fruits": total_fruits,
                "fruits": fruits_list,
                "accounts": all_accounts
            }

            response_bytes = json.dumps(response_data, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("ETag", server_etag)
            self.send_header("Content-Length", str(len(response_bytes)))
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(response_bytes)

        elif clean_path == "/api/presence":
            # Presence เป็น Runtime State จึงไม่ผูกกับ DATA_REVISION/ETag
            now = time.time()
            with db_lock:
                current_accounts = list(ACCOUNTS.items())
                current_rev = DATA_REVISION

            presence_accounts = []
            online_count = 0
            for user, data in current_accounts:
                last_seen = data.get("last_seen", 0)
                is_online = last_seen > 0 and (now - last_seen) <= ONLINE_THRESHOLD
                if is_online:
                    online_count += 1
                presence_accounts.append({
                    "username": user,
                    "last_seen": last_seen,
                    "last_heartbeat": data.get("last_heartbeat", 0),
                    "is_online": is_online
                })

            response_data = {
                "data_revision": current_rev,
                "online_count": online_count,
                "accounts": presence_accounts,
                "server_time": now
            }
            response_bytes = json.dumps(response_data, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(response_bytes)))
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(response_bytes)

        else:
            self.send_response(404)
            self._send_cors_headers()
            self.end_headers()

    def do_POST(self):
        global DATA_REVISION, IS_DIRTY, DIRTY_SINCE
        clean_path = self.path.split("?")[0].rstrip("/")
        
        if clean_path == "/report":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len)
            now = time.time()
            try:
                raw_text = body.decode("utf-8", errors="replace")
                data = json.loads(raw_text)

                if not isinstance(data, dict):
                    raise ValueError("Payload must be a JSON object")

                user = str(data.get("username", "")).strip()
                if not user or len(user) > 60:
                    raise ValueError("Invalid username")

                is_actual_scan = data.get("is_scan") is True
                raw_fruits = data.get("fruits")

                # Strict Validation: ห้ามให้ fruits: null หรือ format เสียมาล้างคลังผลไม้
                if is_actual_scan and not isinstance(raw_fruits, list):
                    raise ValueError("is_scan is true but 'fruits' is not a valid list")

                with db_lock:
                    is_new_account = user not in ACCOUNTS
                    old_data = ACCOUNTS.get(user, {})
                    old_fruits = old_data.get("fruits", [])
                    last_scan = old_data.get("last_scan", 0)
                    inv_updated = old_data.get("inventory_updated_at", 0)

                    inventory_changed = False

                    if is_actual_scan:
                        new_fruits = [str(f).strip() for f in raw_fruits if str(f).strip()]
                        last_scan = now
                        inv_updated = now
                        METRICS["total_scans"] += 1
                        if new_fruits != old_fruits:
                            inventory_changed = True
                    elif isinstance(raw_fruits, list) and len(raw_fruits) > 0:
                        new_fruits = [str(f).strip() for f in raw_fruits if str(f).strip()]
                        last_scan = now
                        inv_updated = now
                        METRICS["total_scans"] += 1
                        if new_fruits != old_fruits:
                            inventory_changed = True
                    else:
                        new_fruits = old_fruits
                        METRICS["total_heartbeats"] += 1

                    ACCOUNTS[user] = {
                        "fruits": new_fruits,
                        "last_seen": now,
                        "last_heartbeat": now,
                        "last_scan": last_scan,
                        "inventory_updated_at": inv_updated
                    }

                    # ขยับ revision เมื่อเป็นบัญชีใหม่หรือ persistent inventory เปลี่ยนจริง
                    if inventory_changed or is_new_account:
                        DATA_REVISION += 1
                        IS_DIRTY = True
                        if DIRTY_SINCE <= 0:
                            DIRTY_SINCE = now

                    METRICS["total_reports"] += 1

                response_bytes = b'{"status":"ok"}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(response_bytes)))
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(response_bytes)

            except Exception as e:
                print(f"❌ [POST /report Rejected] {e}")
                err_msg = json.dumps({"status": "bad_request", "reason": str(e)}).encode("utf-8")
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(err_msg)))
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(err_msg)

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
                    DATA_REVISION += 1
                    IS_DIRTY = True
                    DIRTY_SINCE = time.time()

                persisted = flush_db_to_disk(force=True)

                if persisted:
                    response_bytes = b'{"status":"deleted","persisted":true}'
                    status_code = 200
                else:
                    response_bytes = b'{"status":"deleted_in_memory","persisted":false}'
                    status_code = 503
                self.send_response(status_code)
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
    print(f"🚀 [Bioatom Dashboard Ready] พอร์ต: {PORT}")
    print(f"🔗 หน้าเว็บ: http://127.0.0.1:{PORT}")
    print(f"🩺 เช็กสถานะสุขภาพ: http://127.0.0.1:{PORT}/health?json=1")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 กำลังปิดเซิร์ฟเวอร์...")
        APP_RUNNING = False
        flush_db_to_disk(force=True)
        print("💾 บันทึกฐานข้อมูลก่อนปิดสำเร็จ")
