import os
import sqlite3
from pathlib import Path
from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

APP_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("SG_DB_PATH", APP_DIR / "shadowgallery.db"))
UPLOAD_DIR = Path(os.environ.get("SG_UPLOAD_DIR", "/var/lib/shadowgallery/uploads"))
UPLOAD_TOKEN = os.environ.get("SG_UPLOAD_TOKEN", "sg-upload-dev-token-change-at-deploy")

app = Flask(__name__)
app.secret_key = os.environ.get("SG_SECRET_KEY", "local-ctf-only-change-this")


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with db() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY,
            owner_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            body TEXT NOT NULL
        )""")
        if not conn.execute("SELECT id FROM documents WHERE id=1").fetchone():
            conn.execute(
                "INSERT INTO documents(id, owner_id, title, body) VALUES(1, 1, ?, ?)",
                ("Welcome", "Welcome to ShadowGallery. Uploads are processed by the legacy thumbnail worker.")
            )
            conn.execute(
                "INSERT INTO documents(id, owner_id, title, body) VALUES(2, 1, ?, ?)",
                ("Internal image-worker notes",
                 "Legacy worker upload token: " + UPLOAD_TOKEN +
                 "\nMaintenance note: image-worker invokes the system file utility on uploaded names.")
            )


@app.before_request
def prepare():
    init_db()


@app.get("/")
def index():
    return render_template("index.html", username=session.get("username"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if len(username) < 3 or len(password) < 8:
            flash("Use a username of at least 3 characters and password of at least 8.")
            return render_template("register.html")
        try:
            with db() as conn:
                conn.execute("INSERT INTO users(username, password_hash) VALUES(?, ?)",
                             (username, generate_password_hash(password)))
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("That username is already registered.")
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        with db() as conn:
            user = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect(url_for("index"))
        flash("Invalid username or password.")
    return render_template("login.html")


@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.get("/documents")
def documents():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    with db() as conn:
        rows = conn.execute(
            "SELECT id, title FROM documents WHERE owner_id=? OR id=1 ORDER BY id",
            (session["user_id"],)
        ).fetchall()
    return render_template("documents.html", documents=rows)


@app.get("/api/documents/<int:doc_id>")
def document_api(doc_id):
    if not session.get("user_id"):
        abort(401)
    # INTENTIONAL CTF BUG: authentication exists, but document ownership is not checked.
    with db() as conn:
        row = conn.execute("SELECT id, title, body FROM documents WHERE id=?", (doc_id,)).fetchone()
    if not row:
        abort(404)
    return {"id": row["id"], "title": row["title"], "body": row["body"]}


@app.route("/upload", methods=["GET", "POST"])
def upload():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    if request.method == "POST":
        if request.form.get("token") != UPLOAD_TOKEN:
            abort(403)
        uploaded = request.files.get("file")
        if not uploaded or not uploaded.filename:
            flash("Choose a file.")
            return render_template("upload.html")
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        # INTENTIONAL CTF BUG: basename prevents directory traversal, but shell metacharacters remain.
        filename = os.path.basename(uploaded.filename)
        destination = UPLOAD_DIR / filename
        uploaded.save(destination)
        # INTENTIONAL CTF BUG: user-controlled filename is concatenated into a shell command.
        os.system(f"/usr/bin/file {destination} >/dev/null 2>&1")
        flash("Upload accepted and queued for thumbnail processing.")
        return render_template("upload.html")
    return render_template("upload.html")


@app.get("/health")
def health():
    return {"status": "ok", "service": "shadowgallery"}


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
