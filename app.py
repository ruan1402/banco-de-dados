#!/usr/bin/env python3
"""
Catálogo de Aplicações — cadastro dos seus apps, com código guardado no banco.

- Banco: SQLite (arquivo data/catalogo.db)
- Admin: o e-mail definido em ADMIN_EMAIL (padrão domruan1402@gmail.com) pode
  criar, editar, excluir e enviar código. Qualquer outro e-mail cadastrado só visualiza.
- Rodar:  pip install -r requirements.txt  &&  python app.py
"""
import io
import os
import re
import sys
import time
import secrets
import sqlite3
import zipfile
import hashlib
import hmac
import posixpath
import unicodedata
from datetime import datetime, timezone
from functools import wraps
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

import markdown as md
from flask import Flask, Response, g, jsonify, request, send_from_directory, session

BASE = Path(__file__).parent.resolve()
DATA = Path(os.environ.get("DATA_DIR", BASE / "data"))
DATA.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA / "catalogo.db"

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "domruan1402@gmail.com").strip().lower()

MAX_FILE = 5 * 1024 * 1024          # 5 MB por arquivo
MAX_TOTAL = 50 * 1024 * 1024        # 50 MB por versão
MAX_FILES = 1000                    # arquivos por versão
MAX_VIEW = 300_000                  # bytes mostrados no visualizador
STATUSES = ("ideia", "desenvolvimento", "pronto", "arquivado")
SKIP_PARTS = {".git", "node_modules", "__pycache__", ".DS_Store", ".venv", "venv"}


# --------------------------------------------------------------------------- app
def load_secret():
    f = DATA / "secret.key"
    if not f.exists():
        f.write_text(secrets.token_hex(32))
        try:
            f.chmod(0o600)
        except OSError:
            pass
    return f.read_text().strip()


app = Flask(__name__, static_folder=str(BASE / "static"), static_url_path="/static")
app.config.update(
    SECRET_KEY=load_secret(),
    MAX_CONTENT_LENGTH=60 * 1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE") == "1",
    PERMANENT_SESSION_LIFETIME=60 * 60 * 24 * 30,
    JSON_AS_ASCII=False,
)
if os.environ.get("BEHIND_PROXY") == "1":
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)


# --------------------------------------------------------------------------- banco
SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT NOT NULL UNIQUE,
  pw_hash TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS apps (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  slug TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  category TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'desenvolvimento',
  tech TEXT NOT NULL DEFAULT '',
  url TEXT NOT NULL DEFAULT '',
  readme TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS versions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  app_id INTEGER NOT NULL REFERENCES apps(id) ON DELETE CASCADE,
  tag TEXT NOT NULL,
  notes TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  UNIQUE(app_id, tag)
);
CREATE TABLE IF NOT EXISTS files (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  version_id INTEGER NOT NULL REFERENCES versions(id) ON DELETE CASCADE,
  path TEXT NOT NULL,
  size INTEGER NOT NULL,
  is_text INTEGER NOT NULL,
  content BLOB NOT NULL,
  UNIQUE(version_id, path)
);
CREATE INDEX IF NOT EXISTS idx_versions_app ON versions(app_id);
CREATE INDEX IF NOT EXISTS idx_files_version ON files(version_id);
"""

# --------------------------------------------------------------------------- banco
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://"):]
if os.environ.get("REQUIRE_DATABASE_URL") == "1" and not DATABASE_URL:
    raise SystemExit("DATABASE_URL não definida: sem ela os dados se perderiam a cada reinício.")
if DATABASE_URL:
    import psycopg
    from psycopg.rows import dict_row
    INTEGRITY = (sqlite3.IntegrityError, psycopg.IntegrityError)
else:
    INTEGRITY = (sqlite3.IntegrityError,)


def pg_sql(sql):
    """Traduz o SQL (escrito com ? do SQLite) para o estilo do Postgres."""
    return sql.replace("?", "%s")


class PGCursor:
    def __init__(self, cur, lastrowid=None):
        self._cur, self.lastrowid = cur, lastrowid

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    def __iter__(self):
        return iter(self._cur)


class PGConn:
    """Mesma interface usada do sqlite3 (execute/executemany/commit/close), em cima do Postgres."""

    def __init__(self):
        self.c = psycopg.connect(DATABASE_URL, row_factory=dict_row, prepare_threshold=None)

    def execute(self, sql, params=()):
        q = pg_sql(sql)
        is_insert = q.lstrip().upper().startswith("INSERT") and "RETURNING" not in q.upper()
        if is_insert:
            q += " RETURNING id"
        cur = self.c.execute(q, params)
        return PGCursor(cur, cur.fetchone()["id"] if is_insert else None)

    def executemany(self, sql, seq):
        with self.c.cursor() as cur:
            cur.executemany(pg_sql(sql), list(seq))

    def commit(self):
        self.c.commit()

    def rollback(self):
        self.c.rollback()

    def close(self):
        self.c.close()


def pg_schema(schema):
    return schema.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY").replace("BLOB", "BYTEA")


def raw_connect():
    if DATABASE_URL:
        return PGConn()
    con = sqlite3.connect(DB_PATH, timeout=15)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    return con


def apply_schema(con):
    if DATABASE_URL:
        for stmt in pg_schema(SCHEMA).split(";"):
            if stmt.strip():
                con.execute(stmt)
    else:
        con.execute("PRAGMA journal_mode=WAL")
        con.executescript(SCHEMA)



def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def db():
    if "db" not in g:
        g.db = raw_connect()
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    d = g.pop("db", None)
    if d is not None:
        d.close()


def hash_pw(pw):
    salt = secrets.token_bytes(16)
    h = hashlib.scrypt(pw.encode(), salt=salt, n=2 ** 14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${h.hex()}"


def check_pw(pw, stored):
    try:
        _, salt, h = stored.split("$")
        calc = hashlib.scrypt(pw.encode(), salt=bytes.fromhex(salt), n=2 ** 14, r=8, p=1, dklen=32)
        return hmac.compare_digest(calc.hex(), h)
    except Exception:
        return False


DUMMY_HASH = hash_pw("dummy-password")


def init_db():
    con = raw_connect()
    if DATABASE_URL:
        con.execute("SELECT pg_advisory_lock(424242)")  # evita corrida entre os workers do gunicorn
    apply_schema(con)
    row = con.execute("SELECT id FROM users WHERE email=?", (ADMIN_EMAIL,)).fetchone()
    if not row:
        pw = os.environ.get("ADMIN_PASSWORD")
        generated = False
        if not pw:
            pw = secrets.token_urlsafe(12)
            generated = True
        con.execute(
            "INSERT INTO users(email, pw_hash, created_at) VALUES (?,?,?)",
            (ADMIN_EMAIL, hash_pw(pw), now()),
        )
        con.commit()
        if generated:
            f = DATA / "senha_admin_inicial.txt"
            f.write_text(f"Admin: {ADMIN_EMAIL}\nSenha inicial: {pw}\n"
                         "Troque a senha pelo site (menu 'Alterar senha') e apague este arquivo.\n")
            try:
                f.chmod(0o600)
            except OSError:
                pass
            print("=" * 60)
            print(f" Conta admin criada: {ADMIN_EMAIL}")
            print(f" Senha inicial: {pw}")
            print(f" (também salva em {f})")
            print("=" * 60)
    con.commit()
    con.close()


# --------------------------------------------------------------------------- segurança
@app.before_request
def csrf_guard():
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        if request.headers.get("X-Requested-With") != "catalogo":
            return jsonify(error="Requisição inválida."), 403


@app.after_request
def security_headers(r):
    r.headers["X-Content-Type-Options"] = "nosniff"
    r.headers["X-Frame-Options"] = "DENY"
    r.headers["Referrer-Policy"] = "same-origin"
    r.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' https: data:; style-src 'self' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; "
        "script-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    )
    if request.path.startswith("/api/"):
        r.headers["Cache-Control"] = "no-store"
    return r


@app.errorhandler(413)
def too_big(_e):
    return jsonify(error="Envio grande demais (máximo 60 MB)."), 413


@app.errorhandler(404)
def not_found(_e):
    if request.path.startswith("/api/"):
        return jsonify(error="Não encontrado."), 404
    return "Não encontrado", 404


def me():
    if "me" not in g:
        uid = session.get("uid")
        g.me = None
        if uid:
            g.me = db().execute("SELECT id, email FROM users WHERE id=?", (uid,)).fetchone()
    return g.me


def is_admin(u):
    return bool(u) and u["email"] == ADMIN_EMAIL


def login_required(f):
    @wraps(f)
    def w(*a, **k):
        if not me():
            return jsonify(error="Faça login para continuar."), 401
        return f(*a, **k)
    return w


def admin_required(f):
    @wraps(f)
    def w(*a, **k):
        u = me()
        if not u:
            return jsonify(error="Faça login para continuar."), 401
        if not is_admin(u):
            return jsonify(error="Apenas o administrador pode fazer isso."), 403
        return f(*a, **k)
    return w


FAILS = {}


def throttled(key):
    t = time.time()
    FAILS[key] = [x for x in FAILS.get(key, []) if t - x < 600]
    return len(FAILS[key]) >= 8


EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")


def read_json():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


# --------------------------------------------------------------------------- contas
def user_payload(u):
    return {"email": u["email"], "admin": is_admin(u)}


@app.get("/api/me")
def api_me():
    u = me()
    return jsonify(user=user_payload(u) if u else None)


@app.post("/api/register")
def api_register():
    d = read_json()
    email = str(d.get("email", "")).strip().lower()
    pw = str(d.get("password", ""))
    if not EMAIL_RE.match(email) or len(email) > 254:
        return jsonify(error="Informe um e-mail válido."), 400
    if len(pw) < 8 or len(pw) > 200:
        return jsonify(error="A senha precisa ter pelo menos 8 caracteres."), 400
    if email == ADMIN_EMAIL:
        return jsonify(error="Este e-mail é reservado ao administrador. Use 'Entrar'."), 403
    try:
        cur = db().execute(
            "INSERT INTO users(email, pw_hash, created_at) VALUES (?,?,?)",
            (email, hash_pw(pw), now()),
        )
        db().commit()
    except INTEGRITY:
        return jsonify(error="Este e-mail já está cadastrado. Use 'Entrar'."), 409
    session.clear()
    session["uid"] = cur.lastrowid
    session.permanent = True
    g.pop("me", None)
    return jsonify(user=user_payload(me())), 201


@app.post("/api/login")
def api_login():
    d = read_json()
    email = str(d.get("email", "")).strip().lower()
    pw = str(d.get("password", ""))
    key = (request.remote_addr, email)
    if throttled(key):
        return jsonify(error="Muitas tentativas. Aguarde alguns minutos."), 429
    u = db().execute("SELECT id, email, pw_hash FROM users WHERE email=?", (email,)).fetchone()
    ok = check_pw(pw, u["pw_hash"] if u else DUMMY_HASH)
    if not u or not ok:
        FAILS.setdefault(key, []).append(time.time())
        return jsonify(error="E-mail ou senha incorretos."), 401
    FAILS.pop(key, None)
    session.clear()
    session["uid"] = u["id"]
    session.permanent = True
    g.pop("me", None)
    return jsonify(user=user_payload(me()))


@app.post("/api/logout")
def api_logout():
    session.clear()
    return jsonify(ok=True)


@app.post("/api/password")
@login_required
def api_password():
    d = read_json()
    cur_pw, new_pw = str(d.get("atual", "")), str(d.get("nova", ""))
    u = db().execute("SELECT id, pw_hash FROM users WHERE id=?", (me()["id"],)).fetchone()
    if not check_pw(cur_pw, u["pw_hash"]):
        return jsonify(error="A senha atual está incorreta."), 400
    if len(new_pw) < 8 or len(new_pw) > 200:
        return jsonify(error="A nova senha precisa ter pelo menos 8 caracteres."), 400
    db().execute("UPDATE users SET pw_hash=? WHERE id=?", (hash_pw(new_pw), u["id"]))
    db().commit()
    return jsonify(ok=True)


@app.get("/api/users")
@admin_required
def api_users():
    rows = db().execute("SELECT id, email, created_at FROM users ORDER BY id").fetchall()
    return jsonify(users=[
        {"id": r["id"], "email": r["email"], "created_at": r["created_at"], "admin": r["email"] == ADMIN_EMAIL}
        for r in rows
    ])


@app.delete("/api/users/<int:uid>")
@admin_required
def api_user_delete(uid):
    r = db().execute("SELECT email FROM users WHERE id=?", (uid,)).fetchone()
    if not r:
        return jsonify(error="Usuário não encontrado."), 404
    if r["email"] == ADMIN_EMAIL:
        return jsonify(error="A conta de administrador não pode ser removida."), 400
    db().execute("DELETE FROM users WHERE id=?", (uid,))
    db().commit()
    return jsonify(ok=True)


# --------------------------------------------------------------------------- markdown seguro
ALLOWED_TAGS = {
    "p", "br", "hr", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li", "strong", "em", "b", "i",
    "code", "pre", "blockquote", "a", "img", "table", "thead", "tbody", "tr", "th", "td", "del",
}
VOID_TAGS = {"br", "hr", "img"}
DROP_WITH_CONTENT = {"script", "style", "iframe", "object", "embed", "textarea", "title", "noscript"}


def safe_url(value, schemes):
    v = re.sub(r"[\x00-\x20\x7f]+", "", value or "")
    if not v:
        return None
    scheme = urlparse(v).scheme.lower()
    if scheme and scheme not in schemes:
        return None
    return value.strip()


class Cleaner(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in DROP_WITH_CONTENT:
            self.skip += 1
            return
        if self.skip or tag not in ALLOWED_TAGS:
            return
        a = dict(attrs)
        extra = ""
        if tag == "a":
            href = safe_url(a.get("href"), {"http", "https", "mailto"})
            if href:
                extra = f' href="{escape(href, True)}" target="_blank" rel="noopener noreferrer"'
        elif tag == "img":
            src = safe_url(a.get("src"), {"http", "https"})
            if not src:
                return
            extra = f' src="{escape(src, True)}" alt="{escape(a.get("alt") or "", True)}"'
        self.out.append(f"<{tag}{extra}>")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag in DROP_WITH_CONTENT:
            self.skip = max(0, self.skip - 1)
            return
        if self.skip or tag not in ALLOWED_TAGS or tag in VOID_TAGS:
            return
        self.out.append(f"</{tag}>")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(escape(data))


def render_md(src):
    html = md.markdown(src or "", extensions=["fenced_code", "tables", "sane_lists"])
    c = Cleaner()
    c.feed(html)
    c.close()
    return "".join(c.out)


@app.post("/api/markdown")
@admin_required
def api_markdown():
    return jsonify(html=render_md(str(read_json().get("text", ""))[:100_000]))


# --------------------------------------------------------------------------- apps
def slugify(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:50] or "app"


def unique_slug(base, ignore_id=None):
    slug, n = base, 2
    while True:
        r = db().execute("SELECT id FROM apps WHERE slug=?", (slug,)).fetchone()
        if not r or r["id"] == ignore_id:
            return slug
        slug = f"{base}-{n}"
        n += 1


def clean_app_fields(d):
    name = str(d.get("name", "")).strip()
    if not name or len(name) > 80:
        return None, "Informe o nome do app (até 80 caracteres)."
    status = str(d.get("status", "desenvolvimento"))
    if status not in STATUSES:
        return None, "Status inválido."
    url = str(d.get("url", "")).strip()
    if url and (not re.match(r"^https?://\S+$", url) or len(url) > 300):
        return None, "O link precisa começar com http:// ou https://."
    tech = ", ".join(t.strip() for t in str(d.get("tech", "")).split(",") if t.strip())
    out = {
        "name": name,
        "description": str(d.get("description", "")).strip()[:300],
        "category": str(d.get("category", "")).strip()[:40],
        "status": status,
        "tech": tech[:200],
        "url": url,
        "readme": str(d.get("readme", ""))[:100_000],
    }
    return out, None


def app_dict(r):
    return {
        "id": r["id"], "slug": r["slug"], "name": r["name"], "description": r["description"],
        "category": r["category"], "status": r["status"],
        "tech": [t for t in r["tech"].split(", ") if t], "url": r["url"],
        "created_at": r["created_at"], "updated_at": r["updated_at"],
    }


@app.get("/api/apps")
@login_required
def api_apps():
    rows = db().execute(
        """SELECT a.*,
           (SELECT tag FROM versions v WHERE v.app_id=a.id ORDER BY v.id DESC LIMIT 1) AS latest,
           (SELECT COUNT(*) FROM versions v WHERE v.app_id=a.id) AS n_versions
           FROM apps a ORDER BY a.updated_at DESC, a.id DESC"""
    ).fetchall()
    out = []
    for r in rows:
        d = app_dict(r)
        d["latest"] = r["latest"]
        d["n_versions"] = r["n_versions"]
        out.append(d)
    return jsonify(apps=out)


@app.post("/api/apps")
@admin_required
def api_app_create():
    f, err = clean_app_fields(read_json())
    if err:
        return jsonify(error=err), 400
    slug = unique_slug(slugify(f["name"]))
    t = now()
    db().execute(
        """INSERT INTO apps(slug,name,description,category,status,tech,url,readme,created_at,updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (slug, f["name"], f["description"], f["category"], f["status"], f["tech"], f["url"], f["readme"], t, t),
    )
    db().commit()
    return jsonify(slug=slug), 201


def get_app(slug):
    return db().execute("SELECT * FROM apps WHERE slug=?", (slug,)).fetchone()


@app.get("/api/apps/<slug>")
@login_required
def api_app_get(slug):
    a = get_app(slug)
    if not a:
        return jsonify(error="App não encontrado."), 404
    vers = db().execute(
        """SELECT v.id, v.tag, v.notes, v.created_at,
           (SELECT COUNT(*) FROM files f WHERE f.version_id=v.id) AS n_files,
           (SELECT COALESCE(SUM(size),0) FROM files f WHERE f.version_id=v.id) AS total_size
           FROM versions v WHERE v.app_id=? ORDER BY v.id DESC""", (a["id"],)
    ).fetchall()
    d = app_dict(a)
    d["readme"] = a["readme"] if is_admin(me()) else ""
    d["readme_html"] = render_md(a["readme"])
    d["versions"] = [dict(v) for v in vers]
    return jsonify(app=d)


@app.put("/api/apps/<slug>")
@admin_required
def api_app_update(slug):
    a = get_app(slug)
    if not a:
        return jsonify(error="App não encontrado."), 404
    f, err = clean_app_fields(read_json())
    if err:
        return jsonify(error=err), 400
    new_slug = a["slug"]
    if f["name"] != a["name"]:
        new_slug = unique_slug(slugify(f["name"]), ignore_id=a["id"])
    db().execute(
        """UPDATE apps SET slug=?,name=?,description=?,category=?,status=?,tech=?,url=?,readme=?,updated_at=?
           WHERE id=?""",
        (new_slug, f["name"], f["description"], f["category"], f["status"], f["tech"], f["url"],
         f["readme"], now(), a["id"]),
    )
    db().commit()
    return jsonify(slug=new_slug)


@app.delete("/api/apps/<slug>")
@admin_required
def api_app_delete(slug):
    a = get_app(slug)
    if not a:
        return jsonify(error="App não encontrado."), 404
    db().execute("DELETE FROM apps WHERE id=?", (a["id"],))
    db().commit()
    return jsonify(ok=True)


# --------------------------------------------------------------------------- versões e arquivos
def clean_path(p):
    parts = [x for x in (p or "").replace("\\", "/").split("/") if x not in ("", ".")]
    if not parts or any(x == ".." for x in parts) or any(x in SKIP_PARTS for x in parts):
        return None
    out = "/".join(parts)
    return out if len(out) <= 300 else None


def looks_text(data):
    if b"\x00" in data[:8000]:
        return False
    try:
        data.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def collect_uploads():
    files = request.files.getlist("files")
    paths = request.form.getlist("paths")
    if not files:
        raise ValueError("Escolha uma pasta, arquivos ou um .zip com o código.")
    raw = []
    if len(files) == 1 and (files[0].filename or "").lower().endswith(".zip"):
        try:
            z = zipfile.ZipFile(files[0].stream)
            infos = [i for i in z.infolist() if not i.is_dir()]
            if len(infos) > MAX_FILES * 2:
                raise ValueError(f"O zip tem arquivos demais (máximo {MAX_FILES}).")
            if sum(i.file_size for i in infos) > MAX_TOTAL * 4:
                raise ValueError("O conteúdo do zip é grande demais.")
            for i in infos:
                if clean_path(i.filename) is None:
                    continue
                if i.file_size > MAX_FILE:
                    raise ValueError(f"O arquivo {i.filename} passa de 5 MB.")
                raw.append((i.filename, z.read(i)))
        except zipfile.BadZipFile:
            raise ValueError("Não consegui abrir esse .zip.")
        except RuntimeError:
            raise ValueError("Zip protegido por senha não é aceito.")
    else:
        for idx, f in enumerate(files):
            name = paths[idx] if idx < len(paths) and paths[idx] else f.filename
            data = f.read()
            if clean_path(name) is None:
                continue
            if len(data) > MAX_FILE:
                raise ValueError(f"O arquivo {name} passa de 5 MB.")
            raw.append((name, data))

    items = {}
    for name, data in raw:
        p = clean_path(name)
        if p:
            items[p] = data
    if not items:
        raise ValueError("Nenhum arquivo aproveitável (pastas como .git e node_modules são ignoradas).")
    if len(items) > MAX_FILES:
        raise ValueError(f"Arquivos demais (máximo {MAX_FILES}).")
    tops = {p.split("/")[0] for p in items}
    if len(tops) == 1 and all("/" in p for p in items):
        items = {p.split("/", 1)[1]: d for p, d in items.items()}
    if sum(len(d) for d in items.values()) > MAX_TOTAL:
        raise ValueError("A versão passa de 50 MB no total.")
    return items


@app.post("/api/apps/<slug>/versions")
@admin_required
def api_version_create(slug):
    a = get_app(slug)
    if not a:
        return jsonify(error="App não encontrado."), 404
    tag = request.form.get("tag", "").strip()
    notes = request.form.get("notes", "").strip()[:2000]
    if not re.match(r"^[\w.\- ]{1,30}$", tag):
        return jsonify(error="Nome da versão inválido (até 30 caracteres: letras, números, ponto, traço)."), 400
    try:
        items = collect_uploads()
    except ValueError as e:
        return jsonify(error=str(e)), 400
    try:
        cur = db().execute(
            "INSERT INTO versions(app_id, tag, notes, created_at) VALUES (?,?,?,?)",
            (a["id"], tag, notes, now()),
        )
    except INTEGRITY:
        return jsonify(error=f"A versão '{tag}' já existe neste app."), 409
    vid = cur.lastrowid
    db().executemany(
        "INSERT INTO files(version_id, path, size, is_text, content) VALUES (?,?,?,?,?)",
        [(vid, p, len(d), 1 if looks_text(d) else 0, d) for p, d in sorted(items.items())],
    )
    db().execute("UPDATE apps SET updated_at=? WHERE id=?", (now(), a["id"]))
    db().commit()
    return jsonify(id=vid, files=len(items)), 201


def get_version(vid):
    return db().execute(
        "SELECT v.*, a.slug AS app_slug FROM versions v JOIN apps a ON a.id=v.app_id WHERE v.id=?", (vid,)
    ).fetchone()


@app.delete("/api/versions/<int:vid>")
@admin_required
def api_version_delete(vid):
    v = get_version(vid)
    if not v:
        return jsonify(error="Versão não encontrada."), 404
    db().execute("DELETE FROM versions WHERE id=?", (vid,))
    db().execute("UPDATE apps SET updated_at=? WHERE id=?", (now(), v["app_id"]))
    db().commit()
    return jsonify(ok=True)


@app.get("/api/versions/<int:vid>/files")
@login_required
def api_version_files(vid):
    if not get_version(vid):
        return jsonify(error="Versão não encontrada."), 404
    rows = db().execute(
        "SELECT path, size, is_text FROM files WHERE version_id=? ORDER BY path", (vid,)
    ).fetchall()
    return jsonify(files=[{"path": r["path"], "size": r["size"], "is_text": bool(r["is_text"])} for r in rows])


@app.get("/api/versions/<int:vid>/file")
@login_required
def api_version_file(vid):
    r = db().execute(
        "SELECT path, size, is_text, content FROM files WHERE version_id=? AND path=?",
        (vid, request.args.get("path", "")),
    ).fetchone()
    if not r:
        return jsonify(error="Arquivo não encontrado."), 404
    text = None
    if r["is_text"]:
        text = bytes(r["content"][:MAX_VIEW]).decode("utf-8", "replace")
    return jsonify(path=r["path"], size=r["size"], is_text=bool(r["is_text"]),
                   text=text, truncated=r["size"] > MAX_VIEW)


def safe_filename(s):
    return re.sub(r"[^A-Za-z0-9._-]", "_", s)[:120] or "arquivo"


@app.get("/api/versions/<int:vid>/raw")
@login_required
def api_version_raw(vid):
    r = db().execute(
        "SELECT path, content FROM files WHERE version_id=? AND path=?", (vid, request.args.get("path", ""))
    ).fetchone()
    if not r:
        return jsonify(error="Arquivo não encontrado."), 404
    name = safe_filename(posixpath.basename(r["path"]))
    return Response(bytes(r["content"]), mimetype="application/octet-stream",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@app.get("/api/versions/<int:vid>/download")
@login_required
def api_version_zip(vid):
    v = get_version(vid)
    if not v:
        return jsonify(error="Versão não encontrada."), 404
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for r in db().execute("SELECT path, content FROM files WHERE version_id=? ORDER BY path", (vid,)):
            z.writestr(r["path"], bytes(r["content"]))
    name = safe_filename(f'{v["app_slug"]}-{v["tag"]}') + ".zip"
    return Response(buf.getvalue(), mimetype="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


# --------------------------------------------------------------------------- páginas
@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


# --------------------------------------------------------------------------- exemplos
EXEMPLOS = [
    ("Meu Dia", "Tarefas, hábitos e agenda num só lugar.", "Produtividade"),
    ("Memorix", "Jogo da memória em português.", "Jogo"),
    ("Palavrando", "Jogo de adivinhar a palavra, estilo Termo.", "Jogo"),
    ("Cobrinha do Jardim", "Jogo da cobrinha com recordes, moedas e skins.", "Jogo"),
    ("Ritmo Neon", "Jogo de digitação em ritmo, com visual neon.", "Jogo"),
    ("Quiz do Milhão", "Quiz interativo estilo Show do Milhão.", "Jogo"),
    ("Batalha Naval", "Jogo de Batalha Naval com vários modos.", "Jogo"),
    ("Jogo da Velha", "Jogo da velha com modos diferentes, contra IA ou dois jogadores.", "Jogo"),
    ("Roleta de Sorteios", "Roleta com opções personalizáveis, até 20 itens.", "Utilitário"),
    ("Meus Jogos Favoritos", "Ranking dos 10 jogos favoritos, com notas e pódio.", "Utilitário"),
    ("Consultor de Clima", "Previsão do tempo para várias cidades.", "Utilitário"),
    ("Gerenciador de Senhas", "Gerenciador de senhas pessoal.", "Utilitário"),
    ("Chat Local", "Chat local estilo WhatsApp, sem ligações.", "Comunicação"),
]


def seed():
    con = raw_connect()
    n = 0
    for name, desc, cat in EXEMPLOS:
        slug = slugify(name)
        if con.execute("SELECT 1 FROM apps WHERE slug=?", (slug,)).fetchone():
            continue
        t = now()
        con.execute(
            """INSERT INTO apps(slug,name,description,category,status,tech,url,readme,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (slug, name, desc, cat, "desenvolvimento", "HTML, CSS, JavaScript", "",
             f"# {name}\n\n{desc}\n", t, t),
        )
        n += 1
    con.commit()
    con.close()
    print(f"{n} app(s) de exemplo cadastrados. Ajuste status, links e README pelo site.")


def _startup():
    init_db()
    if os.environ.get("SEED_ON_START") == "1":
        _c = raw_connect()
        _n = _c.execute("SELECT COUNT(*) AS n FROM apps").fetchone()["n"]
        _c.close()
        if _n == 0:
            seed()


if DATABASE_URL:
    _startup()  # no Postgres a corrida é evitada pelo advisory lock
else:
    import fcntl  # SQLite: um único worker inicializa por vez
    DATA.mkdir(parents=True, exist_ok=True)
    with open(DATA / ".init.lock", "w") as _lf:
        fcntl.flock(_lf, fcntl.LOCK_EX)
        _startup()


@app.get("/healthz")
def healthz():
    return {"ok": True}


if __name__ == "__main__":
    if "--seed" in sys.argv:
        seed()
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    print(f"Catálogo rodando em http://{host}:{port}")
    app.run(host=host, port=port, debug=False)
