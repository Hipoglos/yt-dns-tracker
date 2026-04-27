import os
import json
import time
import base64
import logging
import re
import threading
import requests
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from apscheduler.schedulers.background import BackgroundScheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

app = Flask(__name__)
CONFIG_FILE = "/data/config.json"
DOMAINS_FILE = "/data/youtube_domains.txt"
LOG_FILE = "/data/run.log"

# ── YouTube domain patterns ──────────────────────────────────────────────────
YT_PATTERNS = [
    r"(^|\.)youtube\.com$",
    r"(^|\.)youtu\.be$",
    r"(^|\.)ytimg\.com$",
    r"(^|\.)yt3\.ggpht\.com$",
    r"(^|\.)googlevideo\.com$",
    r"(^|\.)youtubei\.googleapis\.com$",
    r"(^|\.)ggpht\.com$",
    r"(^|\.)gvt1\.com$",
    r"(^|\.)gvt2\.com$",
    r"(^|\.)c\.youtube\.com$",
    r"(^|\.)s\.youtube\.com$",
    r"(^|\.)wide-youtube\.l\.google\.com$",
    r"(^|\.)youtubekids\.com$",
    r"(^|\.)youtubeeducation\.com$",
    r"(^|\.)youtubegaming\.com$",
    r"(^|\.)youtubemobile\.com$",
    r"(^|\.)r[0-9]+\.sn-[a-z0-9-]+\.googlevideo\.com$",
    r"(^|\.)rr[0-9]---sn-[a-z0-9-]+\.googlevideo\.com$",
]
YT_COMPILED = [re.compile(p) for p in YT_PATTERNS]

# ── Config helpers ────────────────────────────────────────────────────────────
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {
        "adguard_url": "",
        "adguard_user": "",
        "adguard_pass": "",
        "github_token": "",
        "github_repo": "",
        "github_file_path": "youtube_domains.txt",
        "poll_interval_minutes": 30,
        "last_run": None,
        "last_status": "Never run",
        "domain_count": 0,
    }

def save_config(cfg):
    os.makedirs("/data", exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

def append_log(msg):
    os.makedirs("/data", exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}\n"
    with open(LOG_FILE, "a") as f:
        f.write(line)
    log.info(msg)

def is_youtube_domain(domain: str) -> bool:
    d = domain.lower().rstrip(".")
    return any(p.search(d) for p in YT_COMPILED)

# ── AdGuard query ─────────────────────────────────────────────────────────────
def fetch_adguard_domains(cfg) -> set:
    base = cfg["adguard_url"].rstrip("/")
    auth = (cfg["adguard_user"], cfg["adguard_pass"]) if cfg["adguard_user"] else None
    domains = set()
    limit = 1000
    offset = 0

    while True:
        try:
            resp = requests.get(
                f"{base}/control/querylog",
                params={"limit": limit, "offset": offset, "response_status": "all"},
                auth=auth,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            entries = data.get("data", [])
            if not entries:
                break
            for entry in entries:
                q = entry.get("question", {})
                domain = q.get("name", "").rstrip(".")
                if domain and is_youtube_domain(domain):
                    domains.add(domain)
            if len(entries) < limit:
                break
            offset += limit
        except Exception as e:
            append_log(f"AdGuard fetch error at offset {offset}: {e}")
            break

    return domains

# ── GitHub push ───────────────────────────────────────────────────────────────
def push_to_github(cfg, domains: set) -> bool:
    token = cfg["github_token"]
    repo = cfg["github_repo"]          # owner/repo
    path = cfg["github_file_path"]

    sorted_domains = sorted(domains)
    content = "\n".join(sorted_domains) + "\n"
    encoded = base64.b64encode(content.encode()).decode()

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    api_url = f"https://api.github.com/repos/{repo}/contents/{path}"

    # Check if file exists to get SHA
    sha = None
    try:
        r = requests.get(api_url, headers=headers, timeout=10)
        if r.status_code == 200:
            sha = r.json().get("sha")
    except Exception as e:
        append_log(f"GitHub GET error: {e}")

    payload = {
        "message": f"Update YouTube domains – {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} ({len(sorted_domains)} domains)",
        "content": encoded,
    }
    if sha:
        payload["sha"] = sha

    try:
        r = requests.put(api_url, headers=headers, json=payload, timeout=15)
        r.raise_for_status()
        return True
    except Exception as e:
        append_log(f"GitHub PUT error: {e} – {getattr(r, 'text', '')}")
        return False

# ── Main sync job ─────────────────────────────────────────────────────────────
def sync_job():
    cfg = load_config()
    if not cfg.get("adguard_url") or not cfg.get("github_token"):
        append_log("Skipping sync – configuration incomplete.")
        return

    append_log("Starting YouTube domain sync…")
    try:
        domains = fetch_adguard_domains(cfg)
        append_log(f"Found {len(domains)} YouTube domain(s) in AdGuard query log.")

        # Merge with existing cached domains
        existing = set()
        if os.path.exists(DOMAINS_FILE):
            with open(DOMAINS_FILE) as f:
                existing = {l.strip() for l in f if l.strip()}
        merged = existing | domains
        append_log(f"Merged total: {len(merged)} domain(s) (new: {len(merged - existing)}).")

        with open(DOMAINS_FILE, "w") as f:
            f.write("\n".join(sorted(merged)) + "\n")

        ok = push_to_github(cfg, merged)
        status = "OK" if ok else "GitHub push failed"
        cfg["last_run"] = datetime.now().isoformat()
        cfg["last_status"] = status
        cfg["domain_count"] = len(merged)
        save_config(cfg)
        append_log(f"Sync complete – status: {status}")
    except Exception as e:
        append_log(f"Sync error: {e}")
        cfg["last_status"] = f"Error: {e}"
        save_config(cfg)

# ── Scheduler ─────────────────────────────────────────────────────────────────
scheduler = BackgroundScheduler()
scheduler_job = None

def reschedule(interval_minutes: int):
    global scheduler_job
    if scheduler_job:
        try:
            scheduler_job.remove()
        except Exception:
            pass
    scheduler_job = scheduler.add_job(
        sync_job, "interval", minutes=interval_minutes, id="sync", replace_existing=True
    )
    log.info(f"Scheduler set to every {interval_minutes} minute(s).")

# ── Flask routes ──────────────────────────────────────────────────────────────
@app.route("/")
def index():
    cfg = load_config()
    logs = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE) as f:
            logs = f.readlines()[-80:]
    return render_template("index.html", cfg=cfg, logs=logs)

@app.route("/api/config", methods=["GET"])
def api_config_get():
    cfg = load_config()
    safe = {k: v for k, v in cfg.items() if k != "adguard_pass" and k != "github_token"}
    return jsonify(safe)

@app.route("/api/config", methods=["POST"])
def api_config_save():
    cfg = load_config()
    data = request.json
    fields = ["adguard_url","adguard_user","adguard_pass","github_token",
              "github_repo","github_file_path","poll_interval_minutes"]
    for f in fields:
        if f in data and data[f] != "":
            cfg[f] = data[f]
    save_config(cfg)
    reschedule(int(cfg.get("poll_interval_minutes", 30)))
    return jsonify({"ok": True})

@app.route("/api/sync", methods=["POST"])
def api_sync():
    threading.Thread(target=sync_job, daemon=True).start()
    return jsonify({"ok": True, "message": "Sync started in background."})

@app.route("/api/domains", methods=["GET"])
def api_domains():
    if os.path.exists(DOMAINS_FILE):
        with open(DOMAINS_FILE) as f:
            domains = [l.strip() for l in f if l.strip()]
    else:
        domains = []
    return jsonify({"domains": domains, "count": len(domains)})

@app.route("/api/logs", methods=["GET"])
def api_logs():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE) as f:
            lines = f.readlines()[-100:]
    else:
        lines = []
    return jsonify({"lines": lines})

@app.route("/api/clear_domains", methods=["POST"])
def api_clear():
    if os.path.exists(DOMAINS_FILE):
        os.remove(DOMAINS_FILE)
    cfg = load_config()
    cfg["domain_count"] = 0
    save_config(cfg)
    append_log("Domain cache cleared by user.")
    return jsonify({"ok": True})

if __name__ == "__main__":
    os.makedirs("/data", exist_ok=True)
    scheduler.start()
    cfg = load_config()
    reschedule(int(cfg.get("poll_interval_minutes", 30)))
    app.run(host="0.0.0.0", port=8080, debug=False)
