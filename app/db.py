import os, sqlite3
from pathlib import Path
from datetime import datetime, timedelta, timezone

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
DB = os.getenv("DATABASE_PATH", "data/quick_trader.db")
_USE_PG = DATABASE_URL.startswith(("postgres://", "postgresql://"))

class _Row(dict):
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)

class _PgResult:
    def __init__(self, cursor): self.cursor = cursor
    def fetchone(self):
        r = self.cursor.fetchone()
        return _Row(r) if r is not None else None
    def fetchall(self): return [_Row(r) for r in self.cursor.fetchall()]

class _PgConnection:
    def __init__(self, conn): self.conn = conn
    def __enter__(self): return self
    def __exit__(self, typ, val, tb):
        if typ: self.conn.rollback()
        else: self.conn.commit()
        self.conn.close()
    def execute(self, sql, params=()):
        sql = sql.replace("?", "%s")
        cur = self.conn.cursor()
        cur.execute(sql, params)
        return _PgResult(cur)

def connect():
    if _USE_PG:
        try: import psycopg
        except ImportError as exc: raise RuntimeError("Для PostgreSQL установите зависимости из requirements.txt") from exc
        from psycopg.rows import dict_row
        return _PgConnection(psycopg.connect(DATABASE_URL, row_factory=dict_row, connect_timeout=10))
    Path(DB).parent.mkdir(parents=True, exist_ok=True)
    c=sqlite3.connect(DB, timeout=20)
    c.row_factory=sqlite3.Row
    return c

def init():
    if _USE_PG:
        with connect() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS users(
              tg_id BIGINT PRIMARY KEY, username TEXT, first_name TEXT, pocket_id TEXT DEFAULT '',
              approved INTEGER DEFAULT 0, blocked INTEGER DEFAULT 0, registration_step TEXT DEFAULT 'subscription',
              trial_started_at TIMESTAMP, vip_until TIMESTAMP, vip_plan TEXT DEFAULT '',
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
            c.execute("""CREATE TABLE IF NOT EXISTS signals(
              id BIGSERIAL PRIMARY KEY, tg_id BIGINT, symbol TEXT, timeframe TEXT, expiry TEXT, side TEXT,
              confidence INTEGER, explanation TEXT, price DOUBLE PRECISION,
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, outcome TEXT DEFAULT 'pending')""")
            c.execute("""CREATE TABLE IF NOT EXISTS events(
              id BIGSERIAL PRIMARY KEY, tg_id BIGINT, event TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        return
    with connect() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS users(
          tg_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, pocket_id TEXT DEFAULT '',
          approved INTEGER DEFAULT 0, blocked INTEGER DEFAULT 0, registration_step TEXT DEFAULT 'subscription',
          trial_started_at TEXT, vip_until TEXT, vip_plan TEXT DEFAULT '',
          created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
        cols={r[1] for r in c.execute("PRAGMA table_info(users)").fetchall()}
        if "registration_step" not in cols: c.execute("ALTER TABLE users ADD COLUMN registration_step TEXT DEFAULT 'subscription'")
        if "trial_started_at" not in cols: c.execute("ALTER TABLE users ADD COLUMN trial_started_at TEXT")
        if "vip_until" not in cols: c.execute("ALTER TABLE users ADD COLUMN vip_until TEXT")
        if "vip_plan" not in cols: c.execute("ALTER TABLE users ADD COLUMN vip_plan TEXT DEFAULT ''")
        c.execute("""CREATE TABLE IF NOT EXISTS signals(
          id INTEGER PRIMARY KEY AUTOINCREMENT, tg_id INTEGER, symbol TEXT, timeframe TEXT,
          expiry TEXT, side TEXT, confidence INTEGER, explanation TEXT, price REAL,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP, outcome TEXT DEFAULT 'pending')""")
        c.execute("""CREATE TABLE IF NOT EXISTS events(
          id INTEGER PRIMARY KEY AUTOINCREMENT, tg_id INTEGER, event TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")

def upsert_user(tg_id, username="", first_name=""):
    with connect() as c:
        c.execute("""INSERT INTO users(tg_id,username,first_name) VALUES(?,?,?)
        ON CONFLICT(tg_id) DO UPDATE SET username=excluded.username, first_name=excluded.first_name,
        updated_at=CURRENT_TIMESTAMP""",(tg_id,username or "",first_name or ""))
def get_user(tg_id):
    with connect() as c: return c.execute("SELECT * FROM users WHERE tg_id=?",(tg_id,)).fetchone()
def set_step(tg_id, step):
    with connect() as c: c.execute("UPDATE users SET registration_step=?, updated_at=CURRENT_TIMESTAMP WHERE tg_id=?",(step,tg_id))
def get_step(tg_id):
    u=get_user(tg_id); return u["registration_step"] if u and "registration_step" in u.keys() else "subscription"
def set_pocket_id(tg_id, pocket_id, auto_approve=True):
    with connect() as c:
        c.execute("UPDATE users SET pocket_id=?, approved=?, updated_at=CURRENT_TIMESTAMP WHERE tg_id=?",(pocket_id,1 if auto_approve else 0,tg_id))
        c.execute("UPDATE users SET registration_step='complete', updated_at=CURRENT_TIMESTAMP WHERE tg_id=?",(tg_id,))
def set_approved(tg_id, approved):
    with connect() as c: c.execute("UPDATE users SET approved=? WHERE tg_id=?",(int(approved),tg_id))
def set_blocked(tg_id, blocked):
    with connect() as c: c.execute("UPDATE users SET blocked=? WHERE tg_id=?",(int(blocked),tg_id))
def add_signal(tg_id, s):
    with connect() as c: c.execute("INSERT INTO signals(tg_id,symbol,timeframe,expiry,side,confidence,explanation,price) VALUES(?,?,?,?,?,?,?,?)",(tg_id,s["symbol"],s["timeframe"],s["expiry"],s["side"],s["confidence"],s["explanation"],s.get("price")))
def history(tg_id, limit=30):
    with connect() as c: return c.execute("SELECT * FROM signals WHERE tg_id=? ORDER BY id DESC LIMIT ?",(tg_id,limit)).fetchall()
def stats():
    with connect() as c:
        return {"users":c.execute("SELECT COUNT(*) FROM users").fetchone()[0], "approved":c.execute("SELECT COUNT(*) FROM users WHERE approved=1 AND blocked=0").fetchone()[0], "signals":c.execute("SELECT COUNT(*) FROM signals").fetchone()[0], "blocked":c.execute("SELECT COUNT(*) FROM users WHERE blocked=1").fetchone()[0], "vip":c.execute("SELECT COUNT(*) FROM users WHERE vip_until IS NOT NULL").fetchone()[0]}
def list_users(limit=20, offset=0):
    with connect() as c: return c.execute("SELECT tg_id,username,first_name,pocket_id,approved,blocked,vip_until,vip_plan,created_at FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?",(limit,offset)).fetchall()
def user_count(): return stats()["users"]
def set_vip_until(tg_id, until, plan="VIP"):
    with connect() as c: c.execute("UPDATE users SET vip_until=?,vip_plan=?,approved=1,blocked=0,updated_at=CURRENT_TIMESTAMP WHERE tg_id=?",(until,plan,tg_id))
def revoke_vip(tg_id):
    with connect() as c: c.execute("UPDATE users SET vip_until=NULL,vip_plan='',updated_at=CURRENT_TIMESTAMP WHERE tg_id=?",(tg_id,))
def log_event(tg_id, event):
    with connect() as c: c.execute("INSERT INTO events(tg_id,event) VALUES(?,?)",(tg_id,event))
def recent_events(limit=20):
    with connect() as c: return c.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?",(limit,)).fetchall()
def activate_trial(tg_id):
    with connect() as c:
        if _USE_PG: c.execute("UPDATE users SET trial_started_at=COALESCE(trial_started_at,CURRENT_TIMESTAMP),updated_at=CURRENT_TIMESTAMP WHERE tg_id=?",(tg_id,))
        else: c.execute("UPDATE users SET trial_started_at=COALESCE(trial_started_at,CURRENT_TIMESTAMP), updated_at=CURRENT_TIMESTAMP WHERE tg_id=?",(tg_id,))
def grant_vip(tg_id, months, plan):
    u=get_user(tg_id)
    if not u: return False
    now=datetime.now(timezone.utc).replace(tzinfo=None)
    current=u["vip_until"]
    if current:
        if isinstance(current,str):
            try: current=datetime.fromisoformat(current.replace("Z","+00:00")).replace(tzinfo=None)
            except ValueError: current=None
        if current and current > now: now=current
    # approximate calendar months without external dependencies
    month=now.month-1+int(months); year=now.year+month//12; month=month%12+1
    import calendar
    day=min(now.day,calendar.monthrange(year,month)[1])
    until=now.replace(year=year,month=month,day=day)
    set_vip_until(tg_id,until.isoformat(sep=" "),plan)
    return True
def access_status(tg_id):
    u=get_user(tg_id)
    if not u or not u["approved"] or u["blocked"]: return {"allowed":False,"plan":"none","remaining_seconds":0}
    now=datetime.now(timezone.utc).replace(tzinfo=None)
    def parse(v):
        if not v: return None
        if isinstance(v,datetime): return v.replace(tzinfo=None)
        try: return datetime.fromisoformat(str(v).replace("Z","+00:00")).replace(tzinfo=None)
        except ValueError: return None
    vip=parse(u["vip_until"])
    if vip and vip>now: return {"allowed":True,"plan":u["vip_plan"] or "VIP","vip_until":str(u["vip_until"]),"remaining_seconds":None}
    trial=parse(u["trial_started_at"])
    if not trial:
        activate_trial(tg_id); u=get_user(tg_id); trial=parse(u["trial_started_at"])
    left=max(0,int(((trial+timedelta(days=3))-now).total_seconds())) if trial else 0
    return {"allowed":left>0,"plan":"FREE","trial_started_at":str(u["trial_started_at"]),"remaining_seconds":left}
