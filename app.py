from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.secret_key = "change-this-secret-in-production"
DB = "iam.db"

def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user',
        active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS ai_platforms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        provider TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Active'
    );
    CREATE TABLE IF NOT EXISTS access_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        platform_id INTEGER NOT NULL,
        reason TEXT,
        status TEXT NOT NULL DEFAULT 'Pending',
        created_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(platform_id) REFERENCES ai_platforms(id)
    );
    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        actor TEXT NOT NULL,
        action TEXT NOT NULL,
        details TEXT,
        created_at TEXT NOT NULL
    );
    """)
    if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        conn.execute("INSERT INTO users(name,email,password,role,created_at) VALUES(?,?,?,?,?)",
                     ("Administrator","admin@example.com",generate_password_hash("admin123"),"admin",datetime.now().isoformat(timespec="seconds")))
        conn.execute("INSERT INTO users(name,email,password,role,created_at) VALUES(?,?,?,?,?)",
                     ("Demo User","user@example.com",generate_password_hash("user123"),"user",datetime.now().isoformat(timespec="seconds")))
    if conn.execute("SELECT COUNT(*) FROM ai_platforms").fetchone()[0] == 0:
        conn.executemany("INSERT INTO ai_platforms(name,provider) VALUES(?,?)", [
            ("OpenAI API","OpenAI"),("Google Gemini","Google"),("Anthropic Claude","Anthropic"),("Azure OpenAI","Microsoft")
        ])
    conn.commit()
    conn.close()

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if session.get("role") != "admin":
            flash("Administrator access required.", "danger")
            return redirect(url_for("dashboard"))
        return fn(*args, **kwargs)
    return wrapper

def audit(action, details=""):
    conn = db()
    conn.execute("INSERT INTO audit_logs(actor,action,details,created_at) VALUES(?,?,?,?)",
                 (session.get("email","system"), action, details, datetime.now().isoformat(timespec="seconds")))
    conn.commit()
    conn.close()

@app.route("/")
def index():
    return redirect(url_for("dashboard") if "user_id" in session else url_for("login"))

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        conn = db()
        user = conn.execute("SELECT * FROM users WHERE email=? AND active=1", (email,)).fetchone()
        conn.close()
        if user and check_password_hash(user["password"], password):
            session.update(user_id=user["id"], email=user["email"], name=user["name"], role=user["role"])
            audit("LOGIN", "Successful login")
            return redirect(url_for("dashboard"))
        flash("Invalid credentials.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    if "user_id" in session:
        audit("LOGOUT", "User logged out")
    session.clear()
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    conn = db()
    platforms = conn.execute("SELECT * FROM ai_platforms").fetchall()
    if session["role"] == "admin":
        requests = conn.execute("""
            SELECT ar.*, u.name user_name, u.email, p.name platform_name
            FROM access_requests ar JOIN users u ON u.id=ar.user_id
            JOIN ai_platforms p ON p.id=ar.platform_id ORDER BY ar.id DESC
        """).fetchall()
        users = conn.execute("SELECT id,name,email,role,active,created_at FROM users ORDER BY id").fetchall()
        logs = conn.execute("SELECT * FROM audit_logs ORDER BY id DESC LIMIT 12").fetchall()
    else:
        requests = conn.execute("""
            SELECT ar.*, p.name platform_name FROM access_requests ar
            JOIN ai_platforms p ON p.id=ar.platform_id
            WHERE ar.user_id=? ORDER BY ar.id DESC
        """, (session["user_id"],)).fetchall()
        users, logs = [], []
    conn.close()
    return render_template("dashboard.html", platforms=platforms, requests=requests, users=users, logs=logs)

@app.post("/request-access")
@login_required
def request_access():
    platform_id = request.form["platform_id"]
    reason = request.form.get("reason","").strip()
    conn = db()
    conn.execute("INSERT INTO access_requests(user_id,platform_id,reason,created_at) VALUES(?,?,?,?)",
                 (session["user_id"], platform_id, reason, datetime.now().isoformat(timespec="seconds")))
    conn.commit()
    conn.close()
    audit("ACCESS_REQUEST", f"Platform ID {platform_id}")
    flash("Access request submitted.", "success")
    return redirect(url_for("dashboard"))

@app.post("/request/<int:req_id>/<action>")
@admin_required
def update_request(req_id, action):
    if action not in ("Approved","Rejected"):
        return redirect(url_for("dashboard"))
    conn = db()
    conn.execute("UPDATE access_requests SET status=? WHERE id=?", (action, req_id))
    conn.commit()
    conn.close()
    audit("ACCESS_REVIEW", f"Request {req_id}: {action}")
    flash(f"Request {action.lower()}.", "success")
    return redirect(url_for("dashboard"))

@app.post("/user/<int:user_id>/toggle")
@admin_required
def toggle_user(user_id):
    conn = db()
    conn.execute("UPDATE users SET active = CASE active WHEN 1 THEN 0 ELSE 1 END WHERE id=?", (user_id,))
    conn.commit()
    conn.close()
    audit("USER_STATUS", f"User {user_id} status toggled")
    return redirect(url_for("dashboard"))

if __name__ == "__main__":
    init_db()
    app.run(debug=False, use_reloader=False, host="127.0.0.1", port=5000)
