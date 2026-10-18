import os
import sqlite3
import subprocess
from pathlib import Path
from flask import Blueprint, abort, current_app, flash, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

bp = Blueprint("main", __name__)

def db():
    con = sqlite3.connect(current_app.config["DATABASE"])
    con.row_factory = sqlite3.Row
    return con

def init_db():
    Path(current_app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    with db() as con:
        con.execute("CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE, password_hash TEXT)")
        con.execute("CREATE TABLE IF NOT EXISTS documents(id INTEGER PRIMARY KEY, owner_id INTEGER, title TEXT, body TEXT)")
        con.execute("INSERT OR IGNORE INTO documents VALUES(1,1,'Welcome','Welcome to ShadowGallery.')")
        con.execute("INSERT OR IGNORE INTO documents VALUES(2,1,'Internal worker notes',?)",
                    ("Legacy upload worker token: " + current_app.config["UPLOAD_TOKEN"] + ". Worker binary: /usr/local/bin/gallery-worker",))

@bp.before_app_request
def setup_db():
    init_db()

@bp.get("/")
def index():
    return render_template("index.html", username=session.get("username"))

@bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if len(username) < 3 or len(password) < 8:
            flash("Username must be 3+ characters and password 8+.")
            return redirect(url_for("main.register"))
        try:
            with db() as con:
                con.execute("INSERT INTO users(username,password_hash) VALUES(?,?)",
                            (username, generate_password_hash(password)))
            flash("Account created. Please sign in.")
            return redirect(url_for("main.login"))
        except sqlite3.IntegrityError:
            flash("That username is already registered.")
    return render_template("register.html")

@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        with db() as con:
            user = con.execute("SELECT * FROM users WHERE username=?",
                               (request.form.get("username", ""),)).fetchone()
        if user and check_password_hash(user["password_hash"], request.form.get("password", "")):
            session["user_id"], session["username"] = user["id"], user["username"]
            return redirect(url_for("main.documents"))
        flash("Invalid username or password.")
    return render_template("login.html")

@bp.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("main.index"))

@bp.get("/documents")
def documents():
    if "user_id" not in session:
        return redirect(url_for("main.login"))
    with db() as con:
        rows = con.execute("SELECT id,title FROM documents WHERE owner_id=? OR id=1 ORDER BY id",
                           (session["user_id"],)).fetchall()
    return render_template("documents.html", documents=rows)

@bp.get("/api/documents/<int:doc_id>")
def document_api(doc_id):
    if "user_id" not in session:
        abort(401)
    # CTF BUG: authentication is checked, but ownership is not.
    with db() as con:
        row = con.execute("SELECT id,title,body FROM documents WHERE id=?", (doc_id,)).fetchone()
    if not row:
        abort(404)
    return jsonify(dict(row))

@bp.route("/upload", methods=["GET", "POST"])
def upload():
    if "user_id" not in session:
        return redirect(url_for("main.login"))
    if request.method == "POST":
        if request.form.get("token") != current_app.config["UPLOAD_TOKEN"]:
            abort(403)
        incoming = request.files.get("file")
        if incoming is None or not incoming.filename:
            flash("Choose a file.")
            return redirect(url_for("main.upload"))
        # The saved name is sanitized for path traversal; the legacy worker still
        # receives the original name through an unsafe shell command in this lab.
        safe_name = secure_filename(incoming.filename)
        if not safe_name:
            abort(400)
        upload_dir = Path(current_app.config["UPLOAD_DIR"])
        upload_dir.mkdir(parents=True, exist_ok=True)
        destination = upload_dir / safe_name
        incoming.save(destination)
        # INTENTIONAL CTF BUG: shell=True with attacker-controlled filename.
        subprocess.run(f"/usr/local/bin/gallery-worker {destination}", shell=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        flash("Asset uploaded and sent to the legacy worker.")
        return redirect(url_for("main.upload"))
    return render_template("upload.html")

@bp.get("/health")
def health():
    return jsonify(status="ok", service="shadowgallery")
