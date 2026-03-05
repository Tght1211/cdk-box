import os
import sqlite3
from datetime import datetime
from functools import wraps

from flask import (
    Flask, g, flash, redirect, render_template, request, session, url_for,
)
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "please-change-me")

# ── Embed / iframe 支持 ──────────────────────────────────────────────────────
# EMBED_ORIGINS: 允许嵌入的来源，* 表示任意网站，也可指定如 https://example.com
EMBED_ORIGINS = os.getenv("EMBED_ORIGINS", "")

if EMBED_ORIGINS:
    # 跨域 iframe 中 session cookie 需要 SameSite=None
    app.config["SESSION_COOKIE_SAMESITE"] = "None"
    app.config["SESSION_COOKIE_SECURE"] = True


@app.after_request
def set_embed_headers(response):
    if not EMBED_ORIGINS:
        return response
    # 允许 iframe 嵌入
    origins = EMBED_ORIGINS.strip()
    if origins == "*":
        response.headers["X-Frame-Options"] = "ALLOWALL"
        response.headers["Content-Security-Policy"] = "frame-ancestors *"
    else:
        # 指定来源，如 https://example.com https://other.com
        response.headers.pop("X-Frame-Options", None)
        response.headers["Content-Security-Policy"] = f"frame-ancestors {origins}"
    return response

DATABASE = os.path.join(os.path.dirname(__file__), "data.db")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")


# ── Database ────────────────────────────────────────────────────────────────

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db:
        db.close()


def init_db():
    db = sqlite3.connect(DATABASE)
    db.executescript("""
        CREATE TABLE IF NOT EXISTS activities (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            description TEXT DEFAULT '',
            created_at  TEXT DEFAULT (datetime('now','localtime')),
            is_active   INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS cdks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_id INTEGER NOT NULL REFERENCES activities(id),
            code        TEXT NOT NULL,
            claimed_by  TEXT,
            claimed_at  TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_cdks_activity ON cdks(activity_id);
        CREATE INDEX IF NOT EXISTS idx_cdks_claimed  ON cdks(claimed_by);
    """)
    db.commit()
    db.close()


# ── Template filter ─────────────────────────────────────────────────────────

@app.template_filter("dt")
def format_datetime(value):
    if not value:
        return "-"
    try:
        dt = datetime.fromisoformat(value)
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return value


# ── Decorators ──────────────────────────────────────────────────────────────

def user_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "username" not in session:
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return wrapper


# ── User routes ─────────────────────────────────────────────────────────────

@app.route("/")
def index():
    if "username" in session:
        return redirect(url_for("dashboard"))
    return render_template("index.html")


@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username", "").strip()
    if not username:
        flash("请输入用户名", "error")
        return redirect(url_for("index"))
    session["username"] = username
    return redirect(url_for("dashboard"))


@app.route("/dashboard")
@user_required
def dashboard():
    db = get_db()
    username = session["username"]

    activities = db.execute("""
        SELECT a.*,
               COUNT(c.id) AS total,
               SUM(CASE WHEN c.claimed_by IS NOT NULL THEN 1 ELSE 0 END) AS claimed,
               SUM(CASE WHEN c.claimed_by IS NULL THEN 1 ELSE 0 END) AS remaining
        FROM activities a
        LEFT JOIN cdks c ON a.id = c.activity_id
        WHERE a.is_active = 1
        GROUP BY a.id
        ORDER BY a.created_at DESC
    """).fetchall()

    claimed_ids = {
        row["activity_id"]
        for row in db.execute(
            "SELECT activity_id FROM cdks WHERE claimed_by = ?", (username,)
        ).fetchall()
    }

    history = db.execute("""
        SELECT c.code, c.claimed_at, a.name AS activity_name
        FROM cdks c JOIN activities a ON c.activity_id = a.id
        WHERE c.claimed_by = ?
        ORDER BY c.claimed_at DESC
    """, (username,)).fetchall()

    return render_template(
        "dashboard.html",
        activities=activities,
        claimed_ids=claimed_ids,
        history=history,
        username=username,
    )


@app.route("/claim/<int:activity_id>", methods=["POST"])
@user_required
def claim(activity_id):
    db = get_db()
    username = session["username"]

    # Check activity is active
    activity = db.execute(
        "SELECT id FROM activities WHERE id = ? AND is_active = 1", (activity_id,)
    ).fetchone()
    if not activity:
        flash("活动不存在或已结束", "error")
        return redirect(url_for("dashboard"))

    # Already claimed?
    if db.execute(
        "SELECT id FROM cdks WHERE activity_id = ? AND claimed_by = ?",
        (activity_id, username),
    ).fetchone():
        flash("你已经领取过了", "error")
        return redirect(url_for("dashboard"))

    # Grab first unclaimed CDK
    cdk = db.execute(
        "SELECT id, code FROM cdks WHERE activity_id = ? AND claimed_by IS NULL LIMIT 1",
        (activity_id,),
    ).fetchone()
    if not cdk:
        flash("兑换码已被领完", "error")
        return redirect(url_for("dashboard"))

    # Atomic update with optimistic lock
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor = db.execute(
        "UPDATE cdks SET claimed_by = ?, claimed_at = ? WHERE id = ? AND claimed_by IS NULL",
        (username, now, cdk["id"]),
    )
    db.commit()

    if cursor.rowcount:
        flash(f'领取成功！兑换码: {cdk["code"]}', "success")
    else:
        flash("手慢了，请重试", "error")

    return redirect(url_for("dashboard"))


@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect(url_for("index"))


# ── Admin routes ────────────────────────────────────────────────────────────

@app.route("/admin")
def admin_login():
    if session.get("is_admin"):
        return redirect(url_for("admin_dashboard"))
    return render_template("admin_login.html")


@app.route("/admin/login", methods=["POST"])
def admin_do_login():
    if (
        request.form.get("username") == ADMIN_USERNAME
        and request.form.get("password") == ADMIN_PASSWORD
    ):
        session["is_admin"] = True
        return redirect(url_for("admin_dashboard"))
    flash("用户名或密码错误", "error")
    return redirect(url_for("admin_login"))


@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    db = get_db()
    activities = db.execute("""
        SELECT a.*,
               COUNT(c.id) AS total,
               SUM(CASE WHEN c.claimed_by IS NOT NULL THEN 1 ELSE 0 END) AS claimed,
               SUM(CASE WHEN c.claimed_by IS NULL THEN 1 ELSE 0 END) AS remaining
        FROM activities a
        LEFT JOIN cdks c ON a.id = c.activity_id
        GROUP BY a.id
        ORDER BY a.created_at DESC
    """).fetchall()
    return render_template("admin.html", activities=activities)


@app.route("/admin/activity", methods=["POST"])
@admin_required
def create_activity():
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    codes_text = request.form.get("codes", "").strip()

    if not name or not codes_text:
        flash("活动名称和兑换码不能为空", "error")
        return redirect(url_for("admin_dashboard"))

    codes = [c.strip() for c in codes_text.splitlines() if c.strip()]
    if not codes:
        flash("请输入至少一个兑换码", "error")
        return redirect(url_for("admin_dashboard"))

    db = get_db()
    cur = db.execute(
        "INSERT INTO activities (name, description) VALUES (?, ?)", (name, description)
    )
    aid = cur.lastrowid
    db.executemany(
        "INSERT INTO cdks (activity_id, code) VALUES (?, ?)",
        [(aid, c) for c in codes],
    )
    db.commit()
    flash(f'活动「{name}」创建成功，共 {len(codes)} 个兑换码', "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/restock/<int:activity_id>", methods=["POST"])
@admin_required
def restock(activity_id):
    codes_text = request.form.get("codes", "").strip()
    codes = [c.strip() for c in codes_text.splitlines() if c.strip()]
    if not codes:
        flash("请输入至少一个兑换码", "error")
        return redirect(url_for("admin_dashboard"))

    db = get_db()
    db.executemany(
        "INSERT INTO cdks (activity_id, code) VALUES (?, ?)",
        [(activity_id, c) for c in codes],
    )
    db.commit()
    flash(f"补货成功，新增 {len(codes)} 个兑换码", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/toggle/<int:activity_id>", methods=["POST"])
@admin_required
def toggle_activity(activity_id):
    db = get_db()
    db.execute(
        "UPDATE activities SET is_active = 1 - is_active WHERE id = ?", (activity_id,)
    )
    db.commit()
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/activity/<int:activity_id>")
@admin_required
def admin_activity_detail(activity_id):
    db = get_db()
    activity = db.execute(
        "SELECT * FROM activities WHERE id = ?", (activity_id,)
    ).fetchone()
    if not activity:
        flash("活动不存在", "error")
        return redirect(url_for("admin_dashboard"))
    cdks = db.execute("""
        SELECT * FROM cdks WHERE activity_id = ?
        ORDER BY CASE WHEN claimed_at IS NULL THEN 1 ELSE 0 END, claimed_at DESC, id
    """, (activity_id,)).fetchall()
    return render_template("admin_detail.html", activity=activity, cdks=cdks)


@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("admin_login"))


# ── Main ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    port = int(os.getenv("PORT", 8099))
    debug = os.getenv("DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
