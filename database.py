import sqlite3
import os
import re
import json
import requests
import time
from datetime import date as dt
from werkzeug.utils import secure_filename

import schema


DB_PATH = './instance/site.db'


##schemas
class AboutData:
    def __init__(self, name, about, dp):  ##Init is the constructor for python classes
        self.name = name
        self.about = about
        self.dp = dp


class Record:
    """Row of Projects / Publications.  Every column (and every template-specific field that lives in the
    JSON `data` column) is available as an attribute; anything missing reads as '' so templates never crash."""
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def __getattr__(self, name):          # only called when normal lookup fails
        if name.startswith("__"):
            raise AttributeError(name)
        return ""


class Publications(Record):
    pass


class Projects(Record):
    pass


class Miscellaneous:
    def __init__(self, id, loader, logo, resume, email, linkedin, instagram, topmate, github):
        self.id = id
        self.loader = loader
        self.logo = logo
        self.resume = resume
        self.email = email
        self.linkedin = linkedin
        self.instagram = instagram
        self.topmate = topmate
        self.github = github

class Skills:
    def __init__(self, id, skill, icon):
        self.id = id
        self.skill = skill
        self.icon = icon

class Footer:
    def __init__(self,id,footerlogo,banner,text,copyright,year):
        self.id = id
        self.footerlogo = footerlogo
        self.banner = banner
        self.text = text
        self.copyright = copyright
        self.year = year

EDUCATION_STATUSES = ["Pursuing", "Completed"]


class Education:
    def __init__(self,id,degree,specialisation, grades, html, icon, institute, status='Completed'):
        self.id = id
        self.degree = degree
        self.specialisation = specialisation
        self.grades = (grades or '').strip()          # CGPA / % - optional
        self.html = html
        self.icon = icon
        self.institute = institute
        self.status = status if status in EDUCATION_STATUSES else 'Completed'

    @property
    def as_dict(self):
        return {"id": self.id, "degree": self.degree, "specialisation": self.specialisation, "grades": self.grades,
                "html": self.html or '', "institute": self.institute, "status": self.status}
class Portfolio:
    def __init__(self,id,title,page):
        self.id = id
        self.title = title
        self.page = page

class Writing:
    def __init__(self,id,title,url='',linkedin_url='',medium_url=''):
        self.id = id
        self.title = title
        self.url = url                      # legacy single link (kept for entries that are on neither site)
        self.linkedin_url = linkedin_url or ''
        self.medium_url = medium_url or ''

    @property
    def other_url(self):
        """The old single link, shown as a plain "Read" link only when it is not already a LinkedIn / Medium one."""
        if self.url and self.url not in (self.linkedin_url, self.medium_url):
            return self.url
        return ''

class Artifact:
    """A standalone commercial artifact (a product, kit, app ...) - not tied to a project or publication."""
    def __init__(self, id, title, url, note=''):
        self.id = id
        self.title = title
        self.url = url
        self.note = note or ''

# What a person did at a conference (the choices of the "Participation" drop-down in the editor).
CONFERENCE_ROLES = ["Paper Presented", "Poster Presented", "Volunteered", "Attended", "Workshop / Tutorial", "Organised", "Invited Talk"]


CERT_FILE_TYPES = {".pdf": b"%PDF", ".png": b"\x89PNG", ".jpg": b"\xff\xd8", ".jpeg": b"\xff\xd8", ".gif": b"GIF8", ".webp": b"RIFF"}


class Certification:
    """A course / credential: who issued it, the credential, and the certificate itself (a file kept on this site)."""
    def __init__(self, id, title, company, credential='', issued='', link='', file=''):
        self.id = id
        self.title = title
        self.company = company
        self.credential = credential or ''
        self.issued = issued or ''
        self.link = link or ''            # older entries may still point to an external link
        self.file = file or ''            # file name inside static/uploads/certificates

    @property
    def is_pdf(self):
        return self.file.lower().endswith('.pdf')

    @property
    def as_dict(self):
        return {"id": self.id, "title": self.title, "company": self.company, "credential": self.credential,
                "issued": self.issued, "has_file": bool(self.file)}


def _slug(text):
    return re.sub(r'[^a-z]+', '-', (text or '').lower()).strip('-')


def _parse_roles(raw):
    """The Role column holds a JSON list (older rows: one plain word) -> list of known roles, in the editor's order."""
    try:
        data = json.loads(raw) if (raw or '').lstrip().startswith('[') else [raw]
    except ValueError:
        data = [raw]
    data = [str(x).strip() for x in data if str(x).strip()]
    return [r for r in CONFERENCE_ROLES if r in data] + [r for r in data if r not in CONFERENCE_ROLES]


class Conference:
    """A conference I took part in, and how (paper presented, volunteered ... - one or several)."""
    def __init__(self, id, name, role, paper_title='', location='', held_on='', link=''):
        self.id = id
        self.name = name
        self.roles = _parse_roles(role)
        self.paper_title = paper_title or ''
        self.location = location or ''
        self.held_on = held_on or ''
        self.link = link or ''

    @property
    def role(self):
        return ", ".join(self.roles)

    @property
    def role_tags(self):
        return [(r, _slug(r)) for r in self.roles]

    @property
    def as_dict(self):
        return {"id": self.id, "name": self.name, "roles": self.roles, "paper_title": self.paper_title,
                "location": self.location, "held_on": self.held_on, "link": self.link}


def getdoidata(doi):

    url = f"https://api.crossref.org/works/{doi}"

    try:
        response = requests.get(url, timeout=20)
        data = response.json()

        title = data["message"]["title"][0]
        authors = ", ".join(f"{a['given']} {a['family']}" for a in data["message"]["author"])
        year = data["message"]["issued"]["date-parts"][0][0]
    except Exception as exc:
        raise ValueError("Could not read the DOI details from Crossref - check the DOI link and your connection.") from exc
    return title, authors, year


# ---------------------------------------------------------------------------
# Tables.  CREATE TABLE is for brand-new databases; _migrate() below upgrades an existing site.db in place
# (it only ever ADDs columns, so every existing row and upload keeps working).
# ---------------------------------------------------------------------------
_NEW_ENTRY_COLUMNS = {
    # shared by Projects and Publications
    "hidden": "TEXT DEFAULT 'false'",
    "template": "TEXT NOT NULL DEFAULT 'hci'",     # hci | tech | edtech  (see schema.py)
    "data": "TEXT NOT NULL DEFAULT '{}'",          # JSON: fields of the tech / edtech templates
    "show_video": "INTEGER NOT NULL DEFAULT 0",    # video overview on/off
    "show_model": "INTEGER NOT NULL DEFAULT 0",    # 3D model viewer on/off
    "model_src": "TEXT DEFAULT ''",                # uploaded .glb/.gltf file name, or a URL
    "awards": "TEXT DEFAULT ''",
    "commercial_artifacts": "TEXT DEFAULT ''",
    "resources": "TEXT DEFAULT ''",
    "tech_stack": "TEXT DEFAULT ''",
}
_NEW_COLUMNS = {
    "Projects": {**_NEW_ENTRY_COLUMNS, "role": "TEXT DEFAULT ''", "timeline": "TEXT DEFAULT ''"},
    "Publications": {**_NEW_ENTRY_COLUMNS, "venue": "TEXT DEFAULT ''", "keywords": "TEXT DEFAULT ''"},
    "Writing": {"linkedin_url": "TEXT DEFAULT ''", "medium_url": "TEXT DEFAULT ''"},
    "Photo": {"insta": "TEXT DEFAULT ''"},
    "Education": {"status": "TEXT DEFAULT 'Completed'"},
    "Certification": {"file": "TEXT DEFAULT ''"},
    "Repo": {"stack": "TEXT DEFAULT ''", "has_pages": "INTEGER DEFAULT 0"},
}


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _migrate(conn):
    for table, cols in _NEW_COLUMNS.items():
        existing = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        for name, ddl in cols.items():
            if name in existing:
                continue
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")
            # Publications that already had a video link were showing it - keep showing it.
            if table == "Publications" and name == "show_video":
                conn.execute("UPDATE Publications SET show_video = 1 WHERE COALESCE(mylink, '') != ''")
            # Writings used to have one link: file it under the site it points to
            if table == "Writing" and name == "linkedin_url":
                conn.execute("UPDATE Writing SET linkedin_url = url WHERE url LIKE '%linkedin.com%'")
            # Degrees that were written as "PhD (Pursuing)" get the new status field instead
            if table == "Education" and name == "status":
                for row in conn.execute("SELECT id, degree FROM Education").fetchall():
                    m = re.search(r'\s*[\(\[]\s*(pursuing|ongoing|in progress)\s*[\)\]]\s*', row[1] or '', re.I)
                    if m:
                        conn.execute("UPDATE Education SET status = 'Pursuing', degree = ? WHERE id = ?",
                                     ((row[1][:m.start()] + ' ' + row[1][m.end():]).strip(), row[0]))
            if table == "Writing" and name == "medium_url":
                conn.execute("UPDATE Writing SET medium_url = url WHERE url LIKE '%medium.com%'")


with sqlite3.connect(DB_PATH) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS About (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, about TEXT NOT NULL, photo TEXT NOT NULL)")
        conn.execute("CREATE TABLE IF NOT EXISTS Publications (id INTEGER PRIMARY KEY AUTOINCREMENT, doi TEXT NOT NULL, title TEXT NOT NULL, authors TEXT NOT NULL, summary TEXT NOT NULL, icon TEXT NOT NULL, year INTEGER NOT NULL, rep_image TEXT NOT NULL, mylink TEXT NOT NULL, html TEXT, display_order INTEGER, hidden TEXT DEFAULT 'false')")
        conn.execute("CREATE TABLE IF NOT EXISTS Miscellaneous (id INTEGER PRIMARY KEY AUTOINCREMENT, loader TEXT NOT NULL, logo TEXT NOT NULL, resume TEXT NOT NULL, email TEXT NOT NULL, linkedin TEXT NOT NULL, instagram TEXT NOT NULL, topmate TEXT NOT NULL, github TEXT NOT NULL)")
        conn.execute("CREATE TABLE IF NOT EXISTS Skills (id INTEGER PRIMARY KEY AUTOINCREMENT, skill TEXT NOT NULL, icon TEXT NOT NULL, display_order INTEGER)")
        conn.execute("CREATE TABLE IF NOT EXISTS Footer (id INTEGER PRIMARY KEY AUTOINCREMENT, logo TEXT NOT NULL, banner TEXT NOT NULL, text TEXT NOT NULL, copyright TEXT NOT NULL)")
        conn.execute("CREATE TABLE IF NOT EXISTS Projects (id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT ,userpersonaimage TEXT NOT NULL,userquote TEXT,problemstatement TEXT , designchallenge TEXT ,targetplatformimage TEXT NOT NULL, goalstatement TEXT,scope TEXT, interactionconcept TEXT ,ss1 TEXT NOT NULL,ss2 TEXT NOT NULL,ss3 TEXT NOT NULL,ss4 TEXT NOT NULL,bb1 TEXT NOT NULL,bb2 TEXT NOT NULL,bb3 TEXT NOT NULL,bb4 TEXT NOT NULL,insight1 TEXT,insight2 TEXT,link TEXT,video TEXT,icon TEXT NOT NULL, display_order INTEGER, hidden TEXT DEFAULT 'false')")
        conn.execute("CREATE TABLE IF NOT EXISTS Education (id INTEGER PRIMARY KEY AUTOINCREMENT, degree TEXT NOT NULL, specialisation TEXT NOT NULL, grades TEXT NOT NULL, html TEXT, icon TEXT NOT NULL, Institute TEXT NOT NULL, display_order INTEGER)")
        conn.execute("CREATE TABLE IF NOT EXISTS Portfolio (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, page TEXT NOT NULL, display_order INTEGER)")
        conn.execute("CREATE TABLE IF NOT EXISTS Writing (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, url TEXT NOT NULL, display_order INTEGER)")
        _artifact_table_is_new = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='Artifact'").fetchone() is None
        conn.execute("CREATE TABLE IF NOT EXISTS Artifact (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, url TEXT NOT NULL, note TEXT DEFAULT '', display_order INTEGER)")
        if _artifact_table_is_new:
            conn.execute("INSERT INTO Artifact (title, url, note) VALUES (?,?,?)",
                         ("ThinkBlocks", "https://gaurishgarg.github.io/thinkblocks/",
                          "A physical, play-based learning kit for children around 6 to 11, with puzzles, cards and interactive games that build reasoning and decision-making."))
        conn.execute("CREATE TABLE IF NOT EXISTS Certification (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, company TEXT NOT NULL, credential TEXT DEFAULT '', issued TEXT DEFAULT '', link TEXT DEFAULT '', file TEXT DEFAULT '', display_order INTEGER)")
        conn.execute("CREATE TABLE IF NOT EXISTS Conference (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, role TEXT NOT NULL, paper_title TEXT DEFAULT '', location TEXT DEFAULT '', held_on TEXT DEFAULT '', link TEXT DEFAULT '', display_order INTEGER)")
        conn.execute("CREATE TABLE IF NOT EXISTS Repo (id INTEGER PRIMARY KEY AUTOINCREMENT, full_name TEXT NOT NULL UNIQUE, name TEXT NOT NULL, url TEXT NOT NULL, "
                     "gh_description TEXT DEFAULT '', description TEXT DEFAULT '', title TEXT DEFAULT '', language TEXT DEFAULT '', stars INTEGER DEFAULT 0, forks INTEGER DEFAULT 0, "
                     "gh_homepage TEXT DEFAULT '', homepage TEXT DEFAULT '', topics TEXT DEFAULT '[]', category TEXT DEFAULT '', pinned INTEGER DEFAULT 0, hidden INTEGER DEFAULT 0, "
                     "is_fork INTEGER DEFAULT 0, archived INTEGER DEFAULT 0, pushed_at TEXT DEFAULT '', display_order INTEGER)")
        conn.execute("CREATE TABLE IF NOT EXISTS ARScene (id INTEGER PRIMARY KEY, mind_file TEXT DEFAULT '', model_file TEXT DEFAULT '', target_index INTEGER DEFAULT 0, position TEXT DEFAULT '0 0 0', rotation TEXT DEFAULT '0 0 0', scale TEXT DEFAULT '0.2 0.2 0.2', anim TEXT DEFAULT 'none', anim_speed REAL DEFAULT 1, anim_clip TEXT DEFAULT '', anim_custom TEXT DEFAULT '')")
        conn.execute("CREATE TABLE IF NOT EXISTS Photo (id INTEGER PRIMARY KEY AUTOINCREMENT, file TEXT NOT NULL, caption TEXT DEFAULT '', taken TEXT DEFAULT '', category TEXT DEFAULT '', display_order INTEGER)")
        _migrate(conn)





def store_about(name, about, photo_file, uploads):
    photo_filename = ""
    if photo_file and photo_file.filename != "":
        timestamp = int(time.time() * 1000)  # milliseconds
        filename = str(timestamp) + secure_filename(photo_file.filename)
        photo_path = os.path.join(uploads, filename)
        photo_file.save(photo_path)
        photo_filename = filename
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("DELETE FROM About")
            conn.execute("INSERT INTO About (name, about, photo) VALUES (?, ?, ?)",
                        (name, about, photo_filename))


def store_writing(title, linkedin_url='', medium_url=''):
        title, linkedin_url, medium_url = (title or '').strip(), (linkedin_url or '').strip(), (medium_url or '').strip()
        if not title:
            raise ValueError("Give the writing a title.")
        if not (linkedin_url or medium_url):
            raise ValueError("Add a LinkedIn article link, a Medium article link, or both.")
        for label, link in (("LinkedIn", linkedin_url), ("Medium", medium_url)):
            if link and not re.match(r'^https?://', link, re.I):
                raise ValueError(f"The {label} link must start with http:// or https://")
        with sqlite3.connect(DB_PATH) as conn:
            # url (NOT NULL in the old schema) keeps the first link so older code still has something to read
            conn.execute("INSERT INTO Writing (title, url, linkedin_url, medium_url) VALUES (?,?,?,?)",
                        (title, linkedin_url or medium_url, linkedin_url, medium_url))


def store_artifact(title, url, note=''):
        title, url, note = (title or '').strip(), (url or '').strip(), (note or '').strip()
        if not title:
            raise ValueError("Give the artifact a title.")
        if not re.match(r'^https?://', url, re.I):
            raise ValueError("The link must start with http:// or https://")
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("INSERT INTO Artifact (title, url, note) VALUES (?,?,?)", (title, url, note))


def store_Pages(title,page,uploads):
    if (page and page.filename != ""):
        timestamp = int(time.time() * 1000)  # milliseconds
        filename1 = str(timestamp) + secure_filename(page.filename)
        page_path1 = os.path.join(uploads, "html",filename1)
        page.save(page_path1)
        page_filename1 = filename1

        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("INSERT INTO Portfolio (title, page) VALUES (?,?)",
                        (title,page_filename1))


def store_glance_page(title, html_text, uploads, replace_id=None):
    """Save a page made in the /glance constructor.  New page -> new Portfolio row; replace_id -> overwrite that page's file."""
    html_dir = os.path.join(uploads, "html")
    os.makedirs(html_dir, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        if replace_id:
            row = conn.execute("SELECT page FROM Portfolio WHERE id = ?", (replace_id,)).fetchone()
            if row:
                with open(os.path.join(html_dir, secure_filename(row[0])), "w", encoding="utf-8") as fh:
                    fh.write(html_text)
                conn.execute("UPDATE Portfolio SET title = ? WHERE id = ?", (title, replace_id))
                return int(replace_id)
        slug = secure_filename(re.sub(r"\s+", "_", title.strip().lower())) or "page"
        filename = str(int(time.time() * 1000)) + slug + ".html"
        with open(os.path.join(html_dir, filename), "w", encoding="utf-8") as fh:
            fh.write(html_text)
        cur = conn.execute("INSERT INTO Portfolio (title, page) VALUES (?,?)", (title, filename))
        return cur.lastrowid


def load_pages():
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("SELECT * FROM Portfolio ORDER BY display_order ASC").fetchall()
        return [Portfolio(id=value[0],title=value[1],page=value[2]) for value in rows]



def load_artifacts():
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("SELECT id, title, url, note FROM Artifact ORDER BY display_order ASC, id DESC").fetchall()
        return [Artifact(id=v[0], title=v[1], url=v[2], note=v[3]) for v in rows]


def store_order_in_artifacts(ordered_list):
    with sqlite3.connect(DB_PATH) as conn:
        for item in ordered_list:
            conn.execute("UPDATE Artifact SET display_order = ? WHERE id = ?", (item['position'], item['id']))


def delete_id_artifact(id_to_delete):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM Artifact WHERE id = ?", (id_to_delete,))


def _clean_link(link, label):
    link = (link or '').strip()
    if link and not re.match(r'^https?://', link, re.I):
        raise ValueError(f"The {label} must start with http:// or https://")
    return link


def _save_certificate_file(upload, uploads):
    """Check and store an uploaded certificate (PDF or image) under static/uploads/certificates; returns the file name."""
    name = secure_filename(upload.filename or '')
    ext = os.path.splitext(name)[1].lower()
    if ext not in CERT_FILE_TYPES:
        raise ValueError("The certificate must be a PDF or an image (png, jpg, gif, webp).")
    head = upload.stream.read(12)
    upload.stream.seek(0)
    if not head.startswith(CERT_FILE_TYPES[ext]) or (ext == ".webp" and head[8:12] != b"WEBP"):
        raise ValueError("That file does not look like a real " + ext.lstrip('.').upper() + ".")
    folder = os.path.join(uploads, "certificates")
    os.makedirs(folder, exist_ok=True)
    stored = str(int(time.time() * 1000)) + "_" + name
    upload.save(os.path.join(folder, stored))
    return stored


def _remove_certificate_file(uploads, stored):
    if stored:
        try:
            os.remove(os.path.join(uploads, "certificates", os.path.basename(stored)))
        except OSError:
            pass


def store_certification(title, company, credential='', issued='', upload=None, uploads='static/uploads', id=None):
    """Add a certification (id=None) or change an existing one.  upload = the certificate file (kept in-house)."""
    title, company, credential, issued = [(v or '').strip() for v in (title, company, credential, issued)]
    if not title:
        raise ValueError("Give the certification a title.")
    if not company:
        raise ValueError("Add the company / organisation that issued it.")
    new_file = _save_certificate_file(upload, uploads) if (upload and upload.filename) else ''
    with sqlite3.connect(DB_PATH) as conn:
        if id:
            old = conn.execute("SELECT file FROM Certification WHERE id=?", (id,)).fetchone()
            conn.execute("UPDATE Certification SET title=?, company=?, credential=?, issued=? WHERE id=?",
                         (title, company, credential, issued, id))
            if new_file:                                   # a new file replaces the old file (and any old external link)
                conn.execute("UPDATE Certification SET file=?, link='' WHERE id=?", (new_file, id))
                _remove_certificate_file(uploads, old[0] if old else '')
        else:
            conn.execute("INSERT INTO Certification (title, company, credential, issued, file) VALUES (?,?,?,?,?)",
                         (title, company, credential, issued, new_file))


def load_certifications():
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("SELECT id, title, company, credential, issued, link, file FROM Certification "
                            "ORDER BY COALESCE(display_order, 999999) ASC, id ASC").fetchall()
        return [Certification(*v) for v in rows]


def store_order_in_certifications(ordered_list):
    with sqlite3.connect(DB_PATH) as conn:
        for item in ordered_list:
            conn.execute("UPDATE Certification SET display_order = ? WHERE id = ?", (item['position'], item['id']))


def delete_id_certification(id_to_delete, uploads='static/uploads'):
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT file FROM Certification WHERE id = ?", (id_to_delete,)).fetchone()
        conn.execute("DELETE FROM Certification WHERE id = ?", (id_to_delete,))
    _remove_certificate_file(uploads, row[0] if row else '')


def store_conference(name, roles, paper_title='', location='', held_on='', link='', id=None):
    """Add a conference (id=None) or change an existing one.  roles = one or more of CONFERENCE_ROLES."""
    name, paper_title, location, held_on = [(v or '').strip() for v in (name, paper_title, location, held_on)]
    if isinstance(roles, str):
        roles = [roles]
    roles = [r for r in CONFERENCE_ROLES if r in (roles or [])]          # known choices only, in the editor's order
    if not name:
        raise ValueError("Give the conference a name.")
    if not roles:
        raise ValueError("Choose how you took part (Paper Presented, Volunteered ...) - at least one.")
    link = _clean_link(link, "link")
    stored = json.dumps(roles)
    with sqlite3.connect(DB_PATH) as conn:
        if id:
            conn.execute("UPDATE Conference SET name=?, role=?, paper_title=?, location=?, held_on=?, link=? WHERE id=?",
                         (name, stored, paper_title, location, held_on, link, id))
        else:
            conn.execute("INSERT INTO Conference (name, role, paper_title, location, held_on, link) VALUES (?,?,?,?,?,?)",
                         (name, stored, paper_title, location, held_on, link))


def load_conferences():
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("SELECT id, name, role, paper_title, location, held_on, link FROM Conference "
                            "ORDER BY COALESCE(display_order, 999999) ASC, id ASC").fetchall()
        return [Conference(*v) for v in rows]


def store_order_in_conferences(ordered_list):
    with sqlite3.connect(DB_PATH) as conn:
        for item in ordered_list:
            conn.execute("UPDATE Conference SET display_order = ? WHERE id = ?", (item['position'], item['id']))


def delete_id_conference(id_to_delete):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM Conference WHERE id = ?", (id_to_delete,))


def tech_key(name):
    """'C#' -> 'csharp', 'Node.js' -> 'nodejs', 'Machine Learning' -> 'machinelearning' (a URL-safe key for filtering / linking)."""
    return re.sub(r'[^a-z0-9]+', '', (name or '').lower().replace('#', 'sharp').replace('+', 'plus'))


def code_tech_index(repos):
    """Feeds the Code page's tech-stack bar and the tags on its cards.
    Returns (tech_bar, per_repo):
      tech_bar  [{'name','key','count'}]            every technology, most-used first
      per_repo  {repo id: [{'name','key'}]}         the technologies of each repo"""
    counts, per_repo = {}, {}
    for r in repos:
        seen, chips = set(), []
        for tag in r.tech_tags:
            key = tech_key(tag)
            if key in seen:
                continue
            seen.add(key)
            chips.append({"name": tag, "key": key})
            counts.setdefault(key, {"name": tag, "key": key, "count": 0})["count"] += 1
        per_repo[r.id] = chips
    tech_bar = sorted(counts.values(), key=lambda c: (-c["count"], c["name"].lower()))
    return tech_bar, per_repo


# "Built with ..." technologies and domains recognised in a repository's topics, name and description (aliases are whole words;
# two neighbouring words also count joined, so "micro-bit" is found as "microbit"). Not programming languages: those have their own bar.
TECH_VOCAB = [
    ("Unity", ("unity", "unity3d", "unity2d", "shaderlab")),
    ("Micro:bit", ("microbit", "makecode", "microbitv2")),
    ("Arduino", ("arduino",)),
    ("ESP32", ("esp32", "esp8266")),
    ("Raspberry Pi", ("raspberrypi", "raspberry", "rpi")),
    ("OpenXR", ("openxr",)),
    ("WebXR", ("webxr", "aframe", "a-frame")),
    ("AR Foundation", ("arfoundation",)),
    ("ARCore", ("arcore",)),
    ("Vuforia", ("vuforia",)),
    ("Unreal Engine", ("unreal", "unrealengine", "ue4", "ue5")),
    ("Godot", ("godot",)),
    ("Meta Quest", ("quest", "quest2", "quest3", "oculus")),
    ("HoloLens", ("hololens",)),
    ("Three.js", ("threejs", "three")),
    ("Blender", ("blender",)),
    ("3D Printing", ("3dprinting", "3dprint", "stl")),
    ("Flask", ("flask",)),
    ("Django", ("django",)),
    ("FastAPI", ("fastapi",)),
    ("Node.js", ("nodejs", "node", "express")),
    ("React", ("react", "reactjs", "nextjs")),
    ("Bootstrap", ("bootstrap",)),
    ("HTML/CSS/JS", ("html", "css", "javascript", "js", "frontend", "typescript", "webpage", "website")),
    ("SQLite", ("sqlite", "sqlite3")),
    ("GitHub Pages", ("githubpages",)),
    ("Jupyter", ("jupyter", "notebook", "ipynb")),
    ("PyTorch", ("pytorch", "torch")),
    ("TensorFlow", ("tensorflow", "keras")),
    ("OpenCV", ("opencv",)),
    ("MediaPipe", ("mediapipe",)),
    ("Machine Learning", ("machinelearning", "ml", "deeplearning")),
    ("Data Analysis", ("pandas", "numpy", "dataanalysis", "statistics")),
    ("LaTeX", ("latex",)),
    ("Learning Analytics", ("learninganalytics", "la-reflect", "lareflect")),
]
# GitHub's detected language -> the technology it usually means (everything else is just a language and is left out of the stack)
LANGUAGE_TECH = {"HTML": "HTML/CSS/JS", "CSS": "HTML/CSS/JS", "JavaScript": "HTML/CSS/JS", "TypeScript": "HTML/CSS/JS", "ShaderLab": "Unity", "HLSL": "Unity",
                 "Jupyter Notebook": "Jupyter", "TeX": "LaTeX"}
_LANGUAGE_WORDS = {"python", "c", "cpp", "csharp", "java", "shell", "bash", "go", "rust", "kotlin", "swift", "php", "ruby", "r", "matlab", "dart"}


def detect_tech(name='', description='', topics=(), language=''):
    """Technologies / domains a repo is built with, from its topics, name, description and GitHub language."""
    words = []
    for chunk in list(topics or []) + [name or '', description or '']:
        words += [w for w in re.split(r'[^a-z0-9]+', (chunk or '').lower()) if w]
    tokens = set(words) | {a + b for a, b in zip(words, words[1:])}
    found = []
    for display, aliases in TECH_VOCAB:
        if any(tech_key(a) in tokens for a in aliases):
            found.append(display)
    lang_tech = LANGUAGE_TECH.get(language or '')
    if lang_tech and lang_tech not in found:
        found.append(lang_tech)
    # topics the list does not know are kept as domains (e.g. "spatial-reasoning"), unless they are just a language name
    known = {tech_key(a) for _, al in TECH_VOCAB for a in al}
    for t in topics or []:
        k = tech_key(t)
        if k and k not in known and k not in _LANGUAGE_WORDS and k not in {"hacktoberfest", "project", "demo", "app", "code"}:
            label = t.replace('-', ' ').strip()
            found.append(label[:1].upper() + label[1:])
    return found


class Repo:
    """A GitHub repository shown on the Code page: what GitHub says + the things I curate (title, text, category, pin, hide)."""
    def __init__(self, id, full_name, name, url, gh_description='', description='', title='', language='', stars=0, forks=0,
                 gh_homepage='', homepage='', topics='[]', category='', pinned=0, hidden=0, is_fork=0, archived=0, pushed_at='', stack='', has_pages=0):
        self.id, self.full_name, self.name, self.url = id, full_name, name, url
        self.gh_description, self.custom_description = gh_description or '', description or ''
        self.custom_title = title or ''
        self.language, self.stars, self.forks = language or '', stars or 0, forks or 0
        self.gh_homepage, self.custom_homepage = gh_homepage or '', homepage or ''
        try:
            self.topics = [t for t in json.loads(topics or '[]') if isinstance(t, str)]
        except ValueError:
            self.topics = []
        self.category = category or ''
        self.pinned, self.hidden = bool(pinned), bool(hidden)
        self.is_fork, self.archived = bool(is_fork), bool(archived)
        self.pushed_at = pushed_at or ''
        self.custom_stack = stack or ''
        self.has_pages = bool(has_pages)

    @property
    def tech_tags(self):
        """What the repo is built with (Unity, Micro:bit, Flask, HTML/CSS/JS ...): my own "tech stack" list when I filled it in,
        otherwise detected from its GitHub topics, name, description and language."""
        if self.custom_stack.strip():
            raw = [t.strip() for t in re.split(r'[,\n]', self.custom_stack)]
        else:
            raw = detect_tech(self.name, self.description, self.topics, self.language)
        out, seen = [], set()
        for t in raw:
            key = tech_key(t)
            if t and key and key not in seen:
                seen.add(key)
                out.append(t)
        return out

    @property
    def pages_url(self):
        """Link to the repository's GitHub Pages deployment, or '' when it has none: the address I typed in the editor, else the homepage
        set on GitHub when that is a github.io address, else the standard address when GitHub reports that Pages is switched on."""
        if self.custom_homepage.strip():
            return self.custom_homepage.strip()
        if "github.io" in self.gh_homepage.lower():
            return self.gh_homepage.strip()
        if self.has_pages:
            owner = self.full_name.split("/")[0].lower()
            if self.name.lower() == owner + ".github.io":            # a user site lives at the root
                return "https://" + owner + ".github.io/"
            return "https://" + owner + ".github.io/" + self.name + "/"
        return ''

    @property
    def category_or_other(self):
        return self.category or "Other"

    @property
    def title(self):
        """My title if I set one, otherwise the repo name made readable (Project_Mitra -> Project Mitra)."""
        return self.custom_title or re.sub(r'[-_]+', ' ', self.name).strip()

    @property
    def description(self):
        return self.custom_description or self.gh_description

    @property
    def updated(self):
        """'Nov 2026' from GitHub's pushed_at timestamp."""
        try:
            return time.strftime('%b %Y', time.strptime(self.pushed_at[:10], '%Y-%m-%d'))
        except ValueError:
            return ''

    @property
    def as_dict(self):
        return {"id": self.id, "name": self.name, "title": self.custom_title, "description": self.custom_description,
                "category": self.category, "stack": self.custom_stack, "live": self.custom_homepage, "pinned": self.pinned, "hidden": self.hidden}


# Starter categories for the Code page. A category is just a text label - type any other one in the editor.
REPO_CATEGORIES = ["AR / VR & Games", "Tangible & Hardware", "Web & Apps", "Data & ML", "Research", "Coursework", "Tools & Scripts", "Other"]

_CATEGORY_HINTS = [
    ("Coursework", ("course", "assignment", "homework", "lab-", "-lab", "tutorial", "class", "semester", "et-6", "cs-", "cs1", "cs2")),
    ("Tangible & Hardware", ("microbit", "micro-bit", "micro:bit", "arduino", "esp32", "raspberry", "iot", "sensor", "tangible", "3d-print", "hardware")),
    ("AR / VR & Games", ("unity", "unreal", "openxr", "xr", "vr", "ar-", "-ar", "quest", "hololens", "arcore", "game", "godot", "webxr", "aframe", "three")),
    ("Data & ML", ("machine-learning", "ml", "deep-learning", "pytorch", "tensorflow", "data", "jupyter", "notebook", "nlp", "analysis", "pandas")),
    ("Research", ("research", "paper", "thesis", "study", "experiment", "survey", "dissertation")),
    ("Web & Apps", ("flask", "django", "react", "vue", "web", "website", "portfolio", "html", "css", "javascript", "node", "app", "api")),
]


def guess_repo_category(name, language='', topics=(), description=''):
    """A first guess at a category from the repo's name, topics and text - only a starting point, editable in the editor."""
    bag = " ".join([name or '', description or '', " ".join(topics or [])]).lower()
    tokens = set(re.split(r'[^a-z0-9:]+', bag))
    for category, hints in _CATEGORY_HINTS:
        for h in hints:
            if (h in tokens) or (len(h) > 3 and h in bag):
                return category
    if (language or '') in ("Jupyter Notebook",):
        return "Data & ML"
    if (language or '') in ("C#", "ShaderLab", "HLSL"):
        return "AR / VR & Games"
    if (language or '') in ("HTML", "CSS", "JavaScript", "TypeScript", "Vue", "PHP"):
        return "Web & Apps"
    if (language or '') in ("Shell", "Batchfile", "PowerShell"):
        return "Tools & Scripts"
    return "Other"


_REPO_COLUMNS = ("id, full_name, name, url, gh_description, description, title, language, stars, forks, gh_homepage, homepage, "
                 "topics, category, pinned, hidden, is_fork, archived, pushed_at, stack, has_pages")


def github_username(profile_link):
    """'https://github.com/gaurishgarg' (or a bare name) -> 'gaurishgarg'."""
    m = re.search(r'github\.com/([A-Za-z0-9-]+)', profile_link or '')
    if m:
        return m.group(1)
    return (profile_link or '').strip().strip('/') if re.match(r'^[A-Za-z0-9-]+$', (profile_link or '').strip().strip('/')) else ''


def _gh_get(url, params=None):
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "portfolio-code-viewer"}
    token = os.getenv("GITHUB_TOKEN")                       # optional (.env): lifts the 60-requests-an-hour limit
    if token:
        headers["Authorization"] = "Bearer " + token
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=20)
    except requests.RequestException as exc:
        raise ValueError("Could not reach GitHub - check your internet connection.") from exc
    if resp.status_code == 404:
        raise ValueError("GitHub says that user / repository does not exist (or is private).")
    if resp.status_code in (403, 429):
        raise ValueError("GitHub's rate limit was hit. Wait a while, or put a GITHUB_TOKEN in your .env file.")
    if not resp.ok:
        raise ValueError(f"GitHub answered with an error ({resp.status_code}).")
    return resp.json()


def _save_repo_rows(conn, remote_repos):
    """Insert new repos / refresh the GitHub-side facts of known ones; my own edits (title, text, category, pin, hide) are never touched."""
    added = updated = 0
    for r in remote_repos:
        full = r.get("full_name")
        if not full:
            continue
        values = (r.get("name") or full.split("/")[-1], r.get("html_url") or "https://github.com/" + full, r.get("description") or '',
                  r.get("language") or '', int(r.get("stargazers_count") or 0), int(r.get("forks_count") or 0), r.get("homepage") or '',
                  json.dumps(r.get("topics") or []), int(bool(r.get("fork"))), int(bool(r.get("archived"))), r.get("pushed_at") or '',
                  int(bool(r.get("has_pages"))))
        if conn.execute("SELECT 1 FROM Repo WHERE full_name = ?", (full,)).fetchone():
            conn.execute("UPDATE Repo SET name=?, url=?, gh_description=?, language=?, stars=?, forks=?, gh_homepage=?, topics=?, is_fork=?, archived=?, pushed_at=?, has_pages=? "
                         "WHERE full_name=?", values + (full,))
            updated += 1
        else:
            category = guess_repo_category(values[0], values[3], r.get("topics") or [], values[2])
            hide = int(bool(r.get("fork")) or bool(r.get("archived")))      # forks / archived start hidden - un-hide the ones worth showing
            conn.execute("INSERT INTO Repo (full_name, name, url, gh_description, language, stars, forks, gh_homepage, topics, is_fork, archived, pushed_at, "
                         "has_pages, category, hidden) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (full,) + values + (category, hide))
            added += 1
    return added, updated


def sync_github_repos(username):
    """Pull every public repo of `username` from GitHub (merge, never overwrite curation). Returns (added, updated, removed)."""
    username = github_username(username)
    if not username:
        raise ValueError("Give your GitHub username (or profile link).")
    remote, page = [], 1
    while True:
        batch = _gh_get(f"https://api.github.com/users/{username}/repos", {"per_page": 100, "page": page, "type": "owner", "sort": "pushed"})
        if not isinstance(batch, list):
            raise ValueError("Unexpected answer from GitHub.")
        remote.extend(batch)
        if len(batch) < 100 or page >= 10:
            break
        page += 1
    with sqlite3.connect(DB_PATH) as conn:
        added, updated = _save_repo_rows(conn, remote)
        # repos that vanished from the account (deleted / made private / renamed) leave the list - but keep ones added by hand from other owners
        mine = {r["full_name"] for r in remote}
        removed = 0
        for rid, full in conn.execute("SELECT id, full_name FROM Repo").fetchall():
            if full not in mine and full.split("/")[0].lower() == username.lower():
                conn.execute("DELETE FROM Repo WHERE id = ?", (rid,))
                removed += 1
    return added, updated, removed


def add_github_repo(repo_ref):
    """Add / refresh one repo by 'owner/name' or its URL - for repos in an organisation or somebody else's account."""
    ref = (repo_ref or '').strip()
    if 'github.com/' in ref:                                  # a link: take the first two path pieces (owner/name), ignore /tree/main ...
        ref = ref.split('github.com/', 1)[1]
    parts = [p for p in re.split(r'[/?#]', ref) if p]
    m = re.match(r'^([A-Za-z0-9-]+)/([A-Za-z0-9._-]+)$', "/".join(parts[:2]))
    if not m:
        raise ValueError("Write the repository as owner/name or paste its GitHub link.")
    owner, repo = m.group(1), re.sub(r'\.git$', '', m.group(2))
    data = _gh_get(f"https://api.github.com/repos/{owner}/{repo}")
    with sqlite3.connect(DB_PATH) as conn:
        _save_repo_rows(conn, [data])
        conn.execute("UPDATE Repo SET hidden = 0 WHERE full_name = ?", (data["full_name"],))      # added on purpose -> shown


def load_repos(only_visible=False):
    """Pinned first, then my order, then most recently pushed."""
    where = "WHERE hidden = 0" if only_visible else ""
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(f"SELECT {_REPO_COLUMNS} FROM Repo {where} "
                            "ORDER BY pinned DESC, COALESCE(display_order, 999999) ASC, pushed_at DESC, id ASC").fetchall()
        return [Repo(*v) for v in rows]


def _unique_tags(text):
    """'Unity 3D,  Micro:bit , unity 3d' -> ['Unity 3D', 'Micro:bit']"""
    out, seen = [], set()
    for t in re.split(r'[,\n]', text or ''):
        t = t.strip()
        if t and tech_key(t) not in seen:
            seen.add(tech_key(t)); out.append(t)
    return out


def store_repo(id, title='', description='', category='', pinned=False, hidden=False, stack='', homepage=''):
    """Save the curated side of a repo."""
    if not id:
        raise ValueError("Pick a repository with its Edit button first.")
    with sqlite3.connect(DB_PATH) as conn:
        if not conn.execute("SELECT 1 FROM Repo WHERE id = ?", (id,)).fetchone():
            raise ValueError("That repository is not in the list any more.")
        homepage = (homepage or '').strip()
        if homepage and not re.match(r'^https?://', homepage, re.I):
            raise ValueError("The live-site link must start with http:// or https://")
        conn.execute("UPDATE Repo SET title=?, description=?, category=?, pinned=?, hidden=?, stack=?, homepage=? WHERE id=?",
                     ((title or '').strip(), (description or '').strip(), (category or '').strip(), int(bool(pinned)), int(bool(hidden)),
                      ", ".join(_unique_tags(stack)), homepage, id))


def toggle_repo(id, field):
    """One-click pin / hide switch from the list."""
    if field not in ("pinned", "hidden"):
        raise ValueError("Unknown switch.")
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(f"UPDATE Repo SET {field} = 1 - COALESCE({field}, 0) WHERE id = ?", (id,))


def store_order_in_repos(ordered_list):
    with sqlite3.connect(DB_PATH) as conn:
        for item in ordered_list:
            conn.execute("UPDATE Repo SET display_order = ? WHERE id = ?", (item['position'], item['id']))


def delete_id_repo(id_to_delete):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM Repo WHERE id = ?", (id_to_delete,))


# ---------------------------------------------------------------- Gallery (photo album)
PHOTO_TYPES = {".jpg": b"\xff\xd8\xff", ".jpeg": b"\xff\xd8\xff", ".png": b"\x89PNG", ".webp": b"RIFF"}
PHOTO_MAX_SIDE = 1600           # longest side of the stored web copy, in pixels


class Photo:
    """One picture of the Gallery album: the file (kept in static/uploads/gallery) and its caption, date text and category."""
    def __init__(self, id, file, caption='', taken='', category='', insta=''):
        self.id, self.file = id, file
        self.caption, self.taken, self.category, self.insta = caption or '', taken or '', category or '', insta or ''

    @property
    def insta_text(self):
        return "Watch the reel on Instagram" if "/reel/" in self.insta else "View the post on Instagram"

    @property
    def meta(self):
        return " \u00b7 ".join(x for x in (self.taken, self.category) if x)

    @property
    def as_dict(self):
        return {"id": self.id, "caption": self.caption, "taken": self.taken, "category": self.category, "insta": self.insta}


def clean_insta_url(url):
    """A link to a public Instagram post or reel -> https://www.instagram.com/p/<code>/ or .../reel/<code>/ ;
    empty -> '' (no link); anything else -> ValueError."""
    import re
    url = (url or '').strip()
    if not url:
        return ''
    m = re.match(r"^(?:https?://)?(?:www\.)?instagram\.com/(?:[A-Za-z0-9._]+/)?(p|reel|reels|tv)/([A-Za-z0-9_-]+)", url)
    if not m:
        raise ValueError("That does not look like a link to an Instagram post or reel (it should look like https://www.instagram.com/reel/XXXX/).")
    return "https://www.instagram.com/%s/%s/" % ("reel" if m.group(1) != "p" else "p", m.group(2))


def _save_photo_file(upload, uploads):
    """Check an uploaded picture and store a web-sized copy under static/uploads/gallery; returns the file name.
    With Pillow installed the copy is resized (longest side PHOTO_MAX_SIDE), turned upright and stripped of hidden data
    (camera model, GPS position ...); without Pillow the original file is kept as it is."""
    name = secure_filename(upload.filename or '')
    stem, ext = os.path.splitext(name)
    ext = ext.lower()
    if ext not in PHOTO_TYPES:
        raise ValueError("Pictures must be JPG, PNG or WebP (phone HEIC photos: export as JPG first).")
    head = upload.stream.read(12)
    upload.stream.seek(0)
    if not head.startswith(PHOTO_TYPES[ext]) or (ext == ".webp" and head[8:12] != b"WEBP"):
        raise ValueError("That file does not look like a real " + ext.lstrip('.').upper() + " picture.")
    folder = os.path.join(uploads, "gallery")
    os.makedirs(folder, exist_ok=True)
    stamp = str(int(time.time() * 1000))
    try:
        from PIL import Image, ImageOps
    except ImportError:
        stored = stamp + "_" + name
        upload.save(os.path.join(folder, stored))
        return stored
    try:
        img = Image.open(upload.stream)
        img = ImageOps.exif_transpose(img)
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGBA")
            flat = Image.new("RGB", img.size, (255, 255, 255))
            flat.paste(img, mask=img.split()[-1])
            img = flat
        else:
            img = img.convert("RGB")
        img.thumbnail((PHOTO_MAX_SIDE, PHOTO_MAX_SIDE))
        stored = stamp + "_" + (stem or "photo") + ".jpg"
        img.save(os.path.join(folder, stored), "JPEG", quality=85, optimize=True, progressive=True)    # new file: no EXIF carried over
    except Exception as exc:
        raise ValueError("That picture could not be read: " + str(exc)) from exc
    return stored


def _remove_photo_file(uploads, stored):
    if stored:
        try:
            os.remove(os.path.join(uploads, "gallery", os.path.basename(stored)))
        except OSError:
            pass


def add_photos(uploads_list, caption='', taken='', category='', uploads='static/uploads', insta=''):
    """Add one or several pictures. The caption and the Instagram link are only used when exactly one picture is added."""
    files = [f for f in (uploads_list or []) if f and f.filename]
    if not files:
        raise ValueError("Choose at least one picture.")
    caption, taken, category = [(v or '').strip() for v in (caption, taken, category)]
    insta = clean_insta_url(insta)
    saved = [_save_photo_file(f, uploads) for f in files]
    with sqlite3.connect(DB_PATH) as conn:
        for stored in saved:
            one = len(saved) == 1
            conn.execute("INSERT INTO Photo (file, caption, taken, category, insta) VALUES (?,?,?,?,?)",
                         (stored, caption if one else '', taken, category, insta if one else ''))
    return len(saved)


def store_photo(id, caption='', taken='', category='', upload=None, uploads='static/uploads', insta=''):
    """Change a picture's texts and Instagram link (and optionally replace the picture itself)."""
    caption, taken, category = [(v or '').strip() for v in (caption, taken, category)]
    insta = clean_insta_url(insta)
    new_file = _save_photo_file(upload, uploads) if (upload and upload.filename) else ''
    with sqlite3.connect(DB_PATH) as conn:
        old = conn.execute("SELECT file FROM Photo WHERE id = ?", (id,)).fetchone()
        if not old:
            raise ValueError("That picture is not in the list any more.")
        conn.execute("UPDATE Photo SET caption=?, taken=?, category=?, insta=? WHERE id=?", (caption, taken, category, insta, id))
        if new_file:
            conn.execute("UPDATE Photo SET file=? WHERE id=?", (new_file, id))
    if new_file:
        _remove_photo_file(uploads, old[0])


# ---- the AR scene shown when the visiting card is scanned: tracking file (.mind), 3D model and animation ----
AR_MODEL_TYPES = {".glb": b"glTF", ".gltf": b"{"}
AR_MAX_BYTES = 40 * 1024 * 1024
AR_ANIMS = ("none", "float", "spin", "pulse", "clip", "custom")


def _ar_vec(text, label, uniform_ok=False):
    """'0.2 0.2 0.2' / '0, 0.1, 0' -> '0.2 0.2 0.2'. With uniform_ok one number means the same value on all three axes."""
    parts = re.split(r"[\s,]+", (text or "").strip())
    try:
        nums = [float(p) for p in parts if p != ""]
    except ValueError:
        nums = []
    if uniform_ok and len(nums) == 1:
        nums = nums * 3
    if len(nums) != 3 or any(abs(n) > 1e6 or n != n for n in nums):
        raise ValueError("%s needs three numbers, for example 0 0.1 0%s." % (label, " (or one number for all three)" if uniform_ok else ""))
    return " ".join(("%g" % n) for n in nums)


def _save_ar_file(upload, uploads, allowed):
    """Store an uploaded .mind / model file under static/uploads/ar and return its new name."""
    name = secure_filename(upload.filename or '')
    stem, ext = os.path.splitext(name)
    ext = ext.lower()
    if ext not in allowed:
        raise ValueError("Unsupported file type %s (allowed: %s)." % (ext or "(none)", ", ".join(sorted(allowed))))
    data = upload.read(AR_MAX_BYTES + 1)
    if not data:
        raise ValueError("%s is empty." % name)
    if len(data) > AR_MAX_BYTES:
        raise ValueError("%s is larger than %d MB; GitHub Pages and phones both prefer smaller files." % (name, AR_MAX_BYTES // 1048576))
    magic = allowed[ext]
    if magic and not data.startswith(magic):
        raise ValueError("%s does not look like a %s file." % (name, ext.upper().lstrip('.')))
    folder = os.path.join(uploads, "ar")
    os.makedirs(folder, exist_ok=True)
    stored = "%d_%s%s" % (int(time.time() * 1000), (stem or "file")[:40], ext)
    with open(os.path.join(folder, stored), "wb") as f:
        f.write(data)
    return stored


def _remove_ar_file(uploads, stored):
    if stored:
        path = os.path.join(uploads, "ar", os.path.basename(stored))
        if os.path.isfile(path):
            os.remove(path)


def load_ar_config():
    """The saved AR scene as a dict, or None when nothing was saved yet (the demo scene is used then)."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM ARScene WHERE id = 1").fetchone()
        return dict(row) if row else None


def store_ar_config(form, mind_upload, model_upload, uploads='static/uploads'):
    anim = form.get("anim", "none")
    if anim not in AR_ANIMS:
        raise ValueError("Unknown animation.")
    try:
        index = int(form.get("target_index") or 0)
        speed = float(form.get("anim_speed") or 1)
    except ValueError:
        raise ValueError("Image number and speed must be numbers.")
    if not 0 <= index <= 50:
        raise ValueError("Image number must be between 0 and 50.")
    if not 0.1 <= speed <= 10:
        raise ValueError("Speed must be between 0.1 and 10.")
    position = _ar_vec(form.get("position"), "Position")
    rotation = _ar_vec(form.get("rotation"), "Rotation")
    scale = _ar_vec(form.get("scale"), "Size", uniform_ok=True)
    clip = (form.get("anim_clip") or "").strip()[:100]
    custom = (form.get("anim_custom") or "").strip()[:300]
    if anim == "custom" and not custom:
        raise ValueError("Write the animation settings for the 'custom' choice, or pick another animation.")
    new_mind = _save_ar_file(mind_upload, uploads, {".mind": b""}) if (mind_upload and mind_upload.filename) else ''
    try:
        new_model = _save_ar_file(model_upload, uploads, AR_MODEL_TYPES) if (model_upload and model_upload.filename) else ''
    except ValueError:
        _remove_ar_file(uploads, new_mind)
        raise
    old = load_ar_config() or {}
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT OR REPLACE INTO ARScene (id, mind_file, model_file, target_index, position, rotation, scale, anim, anim_speed, anim_clip, anim_custom) "
                     "VALUES (1,?,?,?,?,?,?,?,?,?,?)",
                     (new_mind or old.get("mind_file", ""), new_model or old.get("model_file", ""), index, position, rotation, scale, anim, speed, clip, custom))
    if new_mind:
        _remove_ar_file(uploads, old.get("mind_file"))
    if new_model:
        _remove_ar_file(uploads, old.get("model_file"))


def reset_ar_config(uploads='static/uploads'):
    old = load_ar_config() or {}
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM ARScene")
    _remove_ar_file(uploads, old.get("mind_file"))
    _remove_ar_file(uploads, old.get("model_file"))


def load_photos():
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("SELECT id, file, caption, taken, category, insta FROM Photo "
                            "ORDER BY COALESCE(display_order, 999999) ASC, id ASC").fetchall()
        return [Photo(*v) for v in rows]


def store_order_in_photos(ordered_list):
    with sqlite3.connect(DB_PATH) as conn:
        for item in ordered_list:
            conn.execute("UPDATE Photo SET display_order = ? WHERE id = ?", (item['position'], item['id']))


def delete_id_photo(id_to_delete, uploads='static/uploads'):
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT file FROM Photo WHERE id = ?", (id_to_delete,)).fetchone()
        conn.execute("DELETE FROM Photo WHERE id = ?", (id_to_delete,))
    _remove_photo_file(uploads, row[0] if row else '')


def load_writing():
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("SELECT id, title, url, linkedin_url, medium_url FROM Writing ORDER BY display_order ASC").fetchall()
        return [Writing(id=v[0], title=v[1], url=v[2], linkedin_url=v[3], medium_url=v[4]) for v in rows]


def load_about():
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT * FROM About LIMIT 1").fetchone()
        if row:
            return AboutData(name=row[1], about=row[2], dp="uploads/"+row[3])
    return None

def store_order_in_pubs(ordered_list):
    for item in ordered_list:
        doi = item['doi']
        position = item['position']
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("UPDATE Publications SET display_order = ? WHERE doi = ?", (position, doi))


def store_order_in_writings(ordered_list):
    for item in ordered_list:
        id = item['id']
        position = item['position']
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("UPDATE Writing SET display_order = ? WHERE id = ?", (position, id))



def store_order_in_projects(ordered_list):
    for item in ordered_list:
        id = item['id']
        position = item['position']
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("UPDATE Projects SET display_order = ? WHERE id = ?", (position, id))

def store_order_in_pages(ordered_list):
    for item in ordered_list:
        id = item['id']
        position = item['position']
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("UPDATE Portfolio SET display_order = ? WHERE id = ?", (position, id))


def store_order_in_skills(ordered_list):
    for item in ordered_list:
        id = item['id']
        position = item['position']
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("UPDATE Skills SET display_order = ? WHERE id = ?", (position, id))


# ===========================================================================
# Projects & Publications  (template aware)
# ===========================================================================
TABLES = {"project": "Projects", "pub": "Publications"}
_PROTECTED = {"id", "display_order", "hidden", "template", "data"}
_IMAGE_KEYS = {kind: {f["key"] for f in schema.all_fields(kind) if f["type"] == "image"} for kind in TABLES}


def _up(name):
    """File name stored in the DB -> path relative to /static (blank stays blank)."""
    return "uploads/" + name if name else ""


def _asset(value):
    """3D model: an uploaded file name or a full URL."""
    value = (value or "").strip()
    if not value:
        return ""
    return value if re.match(r"^(https?:)?//", value) else _up(value)


def _build_record(kind, row):
    d = dict(row)
    raw = d.pop("data", None)
    try:
        extra = json.loads(raw) if raw else {}
    except ValueError:
        extra = {}
    rec = dict(extra) if isinstance(extra, dict) else {}
    rec.update(d)                                    # real columns win over JSON keys

    rec["template"] = schema.valid_template(rec.get("template"))
    rec["template_label"] = schema.TEMPLATE_LABELS[rec["template"]]
    for key in _IMAGE_KEYS[kind]:
        rec[key] = _up(rec.get(key))

    media = schema.MEDIA[kind]
    rec["video_url"] = (rec.get(media["video"]["value"]) or "").strip()
    rec["show_video"] = bool(rec.get("show_video"))
    rec["show_model"] = bool(rec.get("show_model"))
    rec["has_video"] = rec["show_video"] and schema.video_info(rec["video_url"]) is not None
    rec["model_url"] = _asset(rec.get("model_src"))
    rec["has_model"] = rec["show_model"] and bool(rec["model_url"])
    return (Projects if kind == "project" else Publications)(**rec)


def _load_all(kind):
    with _conn() as conn:
        rows = conn.execute(f"SELECT * FROM {TABLES[kind]} ORDER BY display_order ASC").fetchall()
    return [_build_record(kind, r) for r in rows]


def _load_one(kind, entry_id):
    with _conn() as conn:
        row = conn.execute(f"SELECT * FROM {TABLES[kind]} WHERE id = ?", (entry_id,)).fetchone()
    return _build_record(kind, row) if row else None


def load_pubs():
    return _load_all("pub")


def load_proj():
    return _load_all("project")


def get_publication_by_slug(slug):
    return _load_one("pub", slug)


def get_project_by_slug(slug):
    return _load_one("project", slug)


def visible(entries):
    return [e for e in entries if e.hidden != "true"]


def group_by_template(entries):
    """[{key,label,entries}] for the templates that actually have an entry, in template order."""
    groups = []
    for key, label in schema.TEMPLATES:
        items = [e for e in entries if e.template == key]
        if items:
            groups.append({"key": key, "label": label, "entries": items})
    return groups


def collect_artifacts(projects, pubs):
    """Commercial artifacts of every visible project / publication, flattened for the homepage."""
    out = []
    for kind, entries in (("project", projects), ("pub", pubs)):
        for e in visible(entries):
            for art in schema.parse_list(e.commercial_artifacts):
                out.append({**art, "parent_title": e.title, "parent_kind": kind, "parent_id": e.id, "icon": e.icon})
    return out


def all_artifacts(projects, pubs):
    """Every commercial artifact for the page, the homepage and the menu: standalone ones first, then the ones listed on projects / publications."""
    out = [{"name": a.title, "url": a.url, "note": a.note, "parent_title": "", "parent_kind": "", "parent_id": None,
            "icon": "", "standalone": True} for a in load_artifacts()]
    for art in collect_artifacts(projects, pubs):
        out.append({**art, "standalone": False})
    return out


# ---- reading the add / edit forms ------------------------------------------
def _save_file(file, uploads, timestamp):
    if file and file.filename != "":
        filename = str(timestamp) + secure_filename(file.filename)
        file.save(os.path.join(uploads, filename))
        return filename
    return None


def _has_file(file):
    return bool(file and file.filename)


def _check_model_file(file):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in schema.MODEL_EXTENSIONS:
        raise ValueError("The 3D model must be a .glb or .gltf file.")


def collect_form_values(kind, template, form, files, uploads):
    """Read the 'add' form of a template -> {field: value}.  Raises ValueError with a readable message."""
    template = schema.valid_template(template)
    media = schema.MEDIA[kind]
    specs = schema.fields_for(kind, template)

    # 1. validate before anything is written to disk
    for f in specs:
        if not f["required"]:
            continue
        ok = _has_file(files.get(f["key"])) if f["type"] == "image" else bool((form.get(f["key"]) or "").strip())
        if not ok:
            raise ValueError(f"'{f['label']}' is required.")
    video_on, model_on = bool(form.get(media["video"]["flag"])), bool(form.get(media["model"]["flag"]))
    if video_on and not (form.get("video_url") or "").strip():
        raise ValueError("You ticked 'Video overview' - please add the video link.")
    model_file = files.get("model_file")
    model_url = (form.get("model_url") or "").strip()
    if model_on:
        if _has_file(model_file):
            _check_model_file(model_file)
        elif not model_url:
            raise ValueError("You ticked '3D model viewer' - please upload a .glb/.gltf or add a link.")

    # 2. read / save
    ts = int(time.time() * 1000)
    values = {}
    for f in specs:
        key = f["key"]
        if f["type"] == "image":
            values[key] = _save_file(files.get(key), uploads, ts) or ""
        else:
            values[key] = (form.get(key) or "").strip()

    values[media["video"]["flag"]] = 1 if video_on else 0
    values[media["video"]["value"]] = (form.get("video_url") or "").strip() if video_on else ""
    values[media["model"]["flag"]] = 1 if model_on else 0
    values[media["model"]["value"]] = ""
    if model_on:
        values[media["model"]["value"]] = _save_file(model_file, uploads, ts) or model_url
    return values


def insert_entry(kind, template, values):
    """INSERT a project / publication.  Keys that are real columns go to their column, the rest into JSON `data`."""
    table = TABLES[kind]
    with _conn() as conn:
        info = {r["name"]: r for r in conn.execute(f"PRAGMA table_info({table})")}
        cols, extra = {}, {}
        for key, val in values.items():
            (cols if key in info and key not in _PROTECTED else extra)[key] = val
        cols["template"] = schema.valid_template(template)
        cols["data"] = json.dumps(extra)
        cols["hidden"] = "false"
        for name, r in info.items():                       # NOT NULL columns with no default get an empty value
            if name in cols or r["pk"] or r["dflt_value"] is not None or not r["notnull"]:
                continue
            cols[name] = 0 if "INT" in (r["type"] or "").upper() else ""
        names = list(cols)
        conn.execute(f"INSERT INTO {table} ({', '.join(names)}) VALUES ({', '.join('?' * len(names))})",
                     [cols[n] for n in names])


def store_pub_from_form(template, form, files, uploads):
    values = collect_form_values("pub", template, form, files, uploads)
    values["title"], values["authors"], values["year"] = getdoidata(values["doi"])
    insert_entry("pub", template, values)


def store_project_from_form(template, form, files, uploads):
    values = collect_form_values("project", template, form, files, uploads)
    insert_entry("project", template, values)


# ---- editing one field -----------------------------------------------------
def update_field(kind, entry_id, key, value):
    if not re.fullmatch(r"[a-z0-9_]+", key or "") or key in _PROTECTED:
        raise ValueError("Unknown field")
    table = TABLES[kind]
    with _conn() as conn:
        columns = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        if key in columns:
            conn.execute(f"UPDATE {table} SET {key} = ? WHERE id = ?", (value, entry_id))
            return
        row = conn.execute(f"SELECT data FROM {table} WHERE id = ?", (entry_id,)).fetchone()
        if row is None:
            return
        try:
            extra = json.loads(row["data"] or "{}")
        except ValueError:
            extra = {}
        extra[key] = value
        conn.execute(f"UPDATE {table} SET data = ? WHERE id = ?", (json.dumps(extra), entry_id))


def update_image_field(kind, entry_id, key, file, uploads):
    filename = _save_file(file, uploads, int(time.time() * 1000))
    if filename:
        update_field(kind, entry_id, key, filename)


def set_template(kind, entry_id, template):
    with _conn() as conn:
        conn.execute(f"UPDATE {TABLES[kind]} SET template = ? WHERE id = ?", (schema.valid_template(template), entry_id))


def update_media(kind, entry_id, which, form, files, uploads):
    """Save the 'Video overview' / '3D model viewer' block of the edit page (switch + link/file together)."""
    spec = schema.MEDIA[kind][which]
    update_field(kind, entry_id, spec["flag"], 1 if form.get("show") else 0)
    url = (form.get("url") or "").strip()
    if which == "model":
        file = files.get("file")
        if _has_file(file):
            _check_model_file(file)
            update_field(kind, entry_id, spec["value"], _save_file(file, uploads, int(time.time() * 1000)))
            return
    if url:                                           # a blank box keeps the stored link, so switching back on is easy
        update_field(kind, entry_id, spec["value"], url)


# 1. DOI (also refreshes title, authors, year from Crossref)
def update_publication_doi(pub_id, doi):
    title, authors, year = getdoidata(doi)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE Publications SET doi=?, title=?, authors=?, year=? WHERE id=?",
            (doi, title, authors, year, pub_id)
        )


def delete_Doi_pub(doi_to_delete):
     with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM Publications WHERE doi = ?", (doi_to_delete,))

def delete_id_skill(id_to_delete):
     with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM Skills WHERE id = ?", (id_to_delete,))

def delete_id_proj(id_to_delete):
     with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM Projects WHERE id = ?", (id_to_delete,))
def hide_id_proj(id_to_hide):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE Projects SET hidden = ? WHERE id = ?",
            ("true", id_to_hide)
        )
def show_id_proj(id_to_show):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE Projects SET hidden = ? WHERE id = ?",
            ("false", id_to_show)
        )
def hide_id_pub(id_to_hide):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE Publications SET hidden = ? WHERE id = ?",
            ("true", id_to_hide)
        )
def show_id_pub(id_to_show):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE Publications SET hidden = ? WHERE id = ?",
            ("false", id_to_show)
        )


def delete_id_page(id_to_delete):
     with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM Portfolio WHERE id = ?", (id_to_delete,))

def delete_id_writing(id_to_delete):
     with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM Writing WHERE id = ?", (id_to_delete,))

def delete_id_education(id_to_delete):
     with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM Education WHERE id = ?", (id_to_delete,))


def load_misc():
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT * FROM Miscellaneous LIMIT 1").fetchone()
        if row:
            return Miscellaneous(id=row[0],loader="uploads/"+row[1], logo="uploads/"+row[2], resume="uploads/"+row[3], email=row[4], linkedin=row[5], instagram=row[6], topmate=row[7], github=row[8])
    return None





def _save_upload(f, uploads):
    """Save an uploaded file with a timestamped name; return the stored name, or None if nothing was uploaded."""
    if f and getattr(f, "filename", ""):
        name = str(int(time.time() * 1000)) + secure_filename(f.filename)
        f.save(os.path.join(uploads, name))
        return name
    return None


def update_misc(loader, logo, resume,email, linkedin, instagram, topmate, github, uploads):
     with sqlite3.connect(DB_PATH) as conn:

         row_count = conn.execute("SELECT COUNT(*) FROM Miscellaneous").fetchone()[0]
         if (row_count >= 1):
            row = conn.execute("SELECT * FROM Miscellaneous LIMIT 1").fetchone()
            if row:
                id = row[0]
                # text fields always update; each file only changes if a new one was uploaded
                sets = ["email = ?", "linkedin = ?", "instagram = ?", "topmate = ?", "github = ?"]
                vals = [email, linkedin, instagram, topmate, github]
                for col, f in (("loader", loader), ("logo", logo), ("resume", resume)):
                    saved = _save_upload(f, uploads)
                    if saved:
                        sets.append(col + " = ?"); vals.append(saved)
                conn.execute("UPDATE Miscellaneous SET " + ", ".join(sets) + " WHERE id = ?", vals + [id])
         if (row_count == 0):
            print("Form was submittedd")
            if (resume and resume.filename != "") and (loader and loader.filename != "") and (logo and logo.filename != ""):
                print("Table Was Updated")
                timestamp = int(time.time() * 1000)  # milliseconds
                filename1 = str(timestamp) + secure_filename(resume.filename)
                resume_path1 = os.path.join(uploads, filename1)
                resume.save(resume_path1)
                resume_path1 = filename1


                timestamp = int(time.time() * 1000)  # milliseconds
                filename2 = str(timestamp) + secure_filename(loader.filename)
                loader_path1 = os.path.join(uploads, filename2)
                loader.save(loader_path1)
                loader_path1 = filename2

                timestamp = int(time.time() * 1000)  # milliseconds
                filename3 = str(timestamp) + secure_filename(logo.filename)
                logo_path1 = os.path.join(uploads, filename3)
                logo.save(logo_path1)
                logo_path1 = filename3


                # loader TEXT NOT NULL. logo TEXT NOT NULL, resume TEXT NOT NULL, email TEXT NOT NULL, linkedin TEXT NOT NULL, instagram TEXT NOT NULL, topmate TEXT NOT NULL
                conn.execute("INSERT INTO Miscellaneous (loader,logo,resume,email,linkedin,instagram,topmate,github) VALUES (?,?,?,?,?,?,?,?)",(loader_path1, logo_path1, resume_path1, email, linkedin, instagram, topmate, github))





def insertintoskills(skill, photo_file, uploads):
    photo_filename = ""
    if photo_file and photo_file.filename != "":
        timestamp = int(time.time() * 1000)  # milliseconds
        filename = str(timestamp) + secure_filename(photo_file.filename)
        photo_path = os.path.join(uploads, filename)
        photo_file.save(photo_path)
        photo_filename = filename
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("INSERT INTO Skills (skill, icon) VALUES (?, ?)",
                        (skill, photo_filename))


def load_skills():
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("SELECT * FROM Skills ORDER BY display_order ASC").fetchall()
        return [Skills(id=value[0], skill=value[1], icon="uploads/"+value[2]) for value in rows]

def update_footer(footerlogo, banner, text, copyright, uploads):
     with sqlite3.connect(DB_PATH) as conn:

         row_count = conn.execute("SELECT COUNT(*) FROM Footer").fetchone()[0]
         if (row_count >= 1):
            row = conn.execute("SELECT * FROM Footer LIMIT 1").fetchone()
            if row:
                id = row[0]
                # text and copyright always update; logo / banner only if a new file was uploaded
                sets = ["text = ?", "copyright = ?"]
                vals = [text, copyright]
                for col, f in (("logo", footerlogo), ("banner", banner)):
                    saved = _save_upload(f, uploads)
                    if saved:
                        sets.append(col + " = ?"); vals.append(saved)
                conn.execute("UPDATE Footer SET " + ", ".join(sets) + " WHERE id = ?", vals + [id])
         if (row_count == 0):
            if (footerlogo and footerlogo.filename != "") and (banner and banner.filename != ""):
                timestamp = int(time.time() * 1000)  # milliseconds
                filename1 = str(timestamp) + secure_filename(footerlogo.filename)
                footerlogo_path1 = os.path.join(uploads, filename1)
                footerlogo.save(footerlogo_path1)
                footerlogo_path1 = filename1


                timestamp = int(time.time() * 1000)  # milliseconds
                filename2 = str(timestamp) + secure_filename(banner.filename)
                banner_path1 = os.path.join(uploads, filename2)
                banner.save(banner_path1)
                banner_path1 = filename2



                conn.execute("INSERT INTO Footer (logo,banner,text,copyright) VALUES (?,?,?,?)",(footerlogo_path1,banner_path1,text,copyright))



def load_footer():
    my_year = dt.today().year
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT * FROM Footer LIMIT 1").fetchone()
        if row:
            return Footer(id=row[0],footerlogo="uploads/"+row[1],banner="uploads/"+row[2],text=row[3],copyright=row[4],year=my_year)
    return None


def insertintoeducations(degree,specialisation,grades,html,photo_file, institute, uploads, status='Completed', id=None):
    """Add a degree (id=None) or change an existing one.  CGPA/% is optional; the icon is only needed for a new degree."""
    degree, specialisation, grades, institute = [(v or '').strip() for v in (degree, specialisation, grades, institute)]
    if not (degree and specialisation and institute):
        raise ValueError("Degree, specialisation and institute are required.")
    if status not in EDUCATION_STATUSES:
        raise ValueError("Choose whether the degree is Pursuing or Completed.")
    photo_filename = ""
    if photo_file and photo_file.filename != "":
        timestamp = int(time.time() * 1000)  # milliseconds
        photo_filename = str(timestamp) + secure_filename(photo_file.filename)
        photo_file.save(os.path.join(uploads, photo_filename))
    with sqlite3.connect(DB_PATH) as conn:
        if id:
            conn.execute("UPDATE Education SET degree=?, specialisation=?, grades=?, html=?, institute=?, status=? WHERE id=?",
                         (degree, specialisation, grades, html or '', institute, status, id))
            if photo_filename:
                conn.execute("UPDATE Education SET icon=? WHERE id=?", (photo_filename, id))
        else:
            if not photo_filename:
                raise ValueError("Choose an icon for the new degree.")
            conn.execute("INSERT INTO Education (degree, specialisation, grades, html, icon, institute, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (degree, specialisation, grades, html or '', photo_filename, institute, status))


def load_educations():
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("SELECT id, degree, specialisation, grades, html, icon, Institute, status FROM Education "
                            "ORDER BY COALESCE(display_order, 999999) ASC, id ASC").fetchall()
        return [Education(id=v[0],degree=v[1],specialisation=v[2],grades=v[3],html=v[4],icon="uploads/"+v[5],institute=v[6],status=v[7]) for v in rows]

def store_order_in_educations(ordered_list):
    for item in ordered_list:
        id = item['id']
        position = item['position']
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("UPDATE Education SET display_order = ? WHERE id = ?", (position, id))


# ---- one-time starter entries (see seeds.py) ---------------------------------
def _run_seeds():
    import seeds
    base = os.path.dirname(os.path.abspath(__file__))
    uploads = os.path.join(base, "static", "uploads")
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS SeedLog (name TEXT PRIMARY KEY)")
        done = {r[0] for r in conn.execute("SELECT name FROM SeedLog")}
        already = conn.execute("SELECT 1 FROM Projects WHERE title LIKE '%Mitra%'").fetchone() is not None

    if "constructor_project" not in done:
        with sqlite3.connect(DB_PATH) as conn:
            have = conn.execute("SELECT 1 FROM Projects WHERE title LIKE 'Portfolio Constructor%'").fetchone() is not None
        if not have and all(os.path.exists(os.path.join(uploads, f)) for f in seeds.CONSTRUCTOR_FILES):
            insert_entry("project", "tech", dict(seeds.CONSTRUCTOR_PROJECT))
            have = True
        if have:                      # (images not copied over yet -> skipped, and tried again on the next start)
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("INSERT OR IGNORE INTO SeedLog (name) VALUES ('constructor_project')")

    if "mitra_project" not in done:
        if not already:
            if not all(os.path.exists(os.path.join(uploads, f)) for f in seeds.MITRA_FILES):
                return                  # images not copied over yet - try again on the next start
            insert_entry("project", "edtech", dict(seeds.MITRA_PROJECT))
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("INSERT OR IGNORE INTO SeedLog (name) VALUES ('mitra_project')")

    if "mitra_text_short" not in done:
        with _conn() as conn:
            row = conn.execute("SELECT id, data FROM Projects WHERE title LIKE '%Mitra%' ORDER BY id LIMIT 1").fetchone()
        if row is not None:
            try:
                current = json.loads(row["data"] or "{}")
            except ValueError:
                current = {}
            for key, long_text in seeds.MITRA_TEXT_LONG.items():
                if current.get(key) == long_text:        # still the unedited first version -> condensed one
                    update_field("project", row["id"], key, seeds.MITRA_TEXT_SHORT[key])
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("INSERT OR IGNORE INTO SeedLog (name) VALUES ('mitra_text_short')")

    if "mitra_session_shots" not in done:
        files = seeds.MITRA_SESSION_SHOTS
        if not all(os.path.exists(os.path.join(uploads, f)) for f in files.values()):
            return
        with _conn() as conn:
            row = conn.execute("SELECT id, data FROM Projects WHERE title LIKE '%Mitra%' ORDER BY id LIMIT 1").fetchone()
        if row is not None:
            try:
                current = json.loads(row["data"] or "{}")
            except ValueError:
                current = {}
            for key, filename in files.items():
                if not current.get(key):             # never overwrite something the owner already set
                    update_field("project", row["id"], key, filename)
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("INSERT OR IGNORE INTO SeedLog (name) VALUES ('mitra_session_shots')")


_run_seeds()
