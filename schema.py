"""
schema.py - single source of truth for the portfolio templates.

Every project / publication has a `template`:

    hci     HCI & AR-VR              (your original design case-study layout - unchanged)
    tech    Tech for AR-VR           (systems / engineering write-up)
    edtech  Educational Technology   (learning-design write-up)

Each template lists the fields that appear on the "add" form (/edit), on the
per-item edit page, and on the public detail page.  Fields that already exist as
real database columns are stored there; every other field is stored in the JSON
`data` column of the row (see database.py), so adding a field here is all that is
needed to add a new input - no migration.

Field types
    text    single line, escaped on the page
    html    textarea, rendered as raw HTML (like your existing fields)
    url     URL input
    image   file upload (stored in static/uploads)
    tags    comma separated -> rendered as chips
    list    one entry per line:  Name | URL | Note   (URL and Note optional)
"""

TEMPLATES = [
    ("hci", "HCI & AR-VR"),
    ("tech", "Tech for AR-VR"),
    ("edtech", "Educational Technology"),
]
TEMPLATE_LABELS = dict(TEMPLATES)
DEFAULT_TEMPLATE = "hci"


def F(key, label, type="text", required=False, help=""):
    return {"key": key, "label": label, "type": type, "required": required, "help": help}


# --------------------------------------------------------------------------
# Optional media blocks - available on every template, each with an on/off switch
#   flag  : checkbox column (0/1)
#   value : column holding the URL (video) or the file name / URL (3D model)
# The video column is `video` on projects and `mylink` on publications, because
# those are the column names you already had.
# --------------------------------------------------------------------------
MEDIA = {
    "project": {
        "video": {"flag": "show_video", "value": "video", "label": "Video overview",
                  "placeholder": "YouTube / Vimeo link, or a direct .mp4 link"},
        "model": {"flag": "show_model", "value": "model_src", "label": "3D model viewer",
                  "placeholder": "Link to a .glb / .gltf (or upload one)"},
    },
    "pub": {
        "video": {"flag": "show_video", "value": "mylink", "label": "Video overview",
                  "placeholder": "YouTube / Vimeo link, or a direct .mp4 link"},
        "model": {"flag": "show_model", "value": "model_src", "label": "3D model viewer",
                  "placeholder": "Link to a .glb / .gltf (or upload one)"},
    },
}
MODEL_EXTENSIONS = (".glb", ".gltf")

# --------------------------------------------------------------------------
# Extra columns shared by every template ("commercial artifacts" etc.)
# --------------------------------------------------------------------------
_ARTIFACT_HELP = "One per line:  Name | URL | Note   e.g.  My App on the Meta Quest Store | https://... | Released 2026"

PROJECT_COMMON = [
    F("role", "Role & Team", "text", help="e.g. Lead developer, team of 3"),
    F("timeline", "Timeline / Duration", "text", help="e.g. Jan - Jun 2026"),
    F("tech_stack", "Tools & Technologies", "tags", help="Comma separated: Unity, OpenXR, Micro:bit"),
    F("awards", "Awards & Recognition", "html"),
    F("commercial_artifacts", "Commercial Artifacts", "list",
      help="Apps, store listings, products, licences, patents. " + _ARTIFACT_HELP),
    F("resources", "Resources & Links", "list",
      help="Code, datasets, demos, preprints. One per line:  Name | URL | Note"),
]

PUB_BASE = [
    F("doi", "DOI (full https://doi.org/... link)", "url", required=True),
    F("summary", "One Line Summary", "html", required=True),
    F("icon", "Choose Relevant Icon", "image", required=True),
    F("rep_image", "Choose Representational Image", "image", required=True),
    F("html", "Contributions", "html", help="Custom HTML, shown under 'Details'"),
]

PUB_COMMON = [
    F("venue", "Venue / Publisher", "text", help="e.g. HCII 2025, Springer"),
    F("keywords", "Keywords", "tags", help="Comma separated"),
    F("tech_stack", "Tools & Technologies", "tags", help="Comma separated"),
    F("awards", "Awards & Recognition", "html"),
    F("commercial_artifacts", "Commercial Artifacts", "list",
      help="Apps, products, licences, patents that came out of this work. " + _ARTIFACT_HELP),
    F("resources", "Resources & Links", "list",
      help="Code, datasets, demos, preprints. One per line:  Name | URL | Note"),
]

# --------------------------------------------------------------------------
# PROJECT templates
# --------------------------------------------------------------------------
PROJECT_TEMPLATE_FIELDS = {
    # ---- your original design case study: same fields, same order ----------
    "hci": [
        F("title", "Title", "text", required=True),
        F("userpersonaimage", "User Persona Image (Passport)", "image", required=True),
        F("userquote", "User Quote", "text"),
        F("problemstatement", "Problem Statement", "html"),
        F("designchallenge", "Design Challenge", "html"),
        F("targetplatformimage", "Target Platform Image (Landscape)", "image", required=True),
        F("goalstatement", "Goal Statement", "html"),
        F("scope", "Scope", "html"),
        F("interactionconcept", "Interaction Concept", "html"),
        F("ss1", "Screenshot 1 (Square)", "image", required=True),
        F("ss2", "Screenshot 2 (Square)", "image", required=True),
        F("ss3", "Screenshot 3 (Square)", "image", required=True),
        F("ss4", "Screenshot 4 (Square)", "image", required=True),
        F("bb1", "Building Block 1 (Landscape)", "image", required=True),
        F("bb2", "Building Block 2 (Landscape)", "image", required=True),
        F("bb3", "Building Block 3 (Landscape)", "image", required=True),
        F("bb4", "Building Block 4 (Landscape)", "image", required=True),
        F("insight1", "Insights - 1", "html"),
        F("insight2", "Insights - 2", "html"),
        F("link", "Itch/Github Link", "url"),
        F("icon", "Choose Relevant Icon", "image", required=True),
    ],
    # ---- engineering / systems write-up -------------------------------------
    "tech": [
        F("title", "Title", "text", required=True),
        F("icon", "Choose Relevant Icon", "image", required=True),
        F("problem_motivation", "Problem & Motivation", "html"),
        F("technical_challenge", "Technical Challenge", "html"),
        F("objectives", "Objectives", "html"),
        F("architecture_image", "System Architecture Diagram (Landscape)", "image"),
        F("system_overview", "System Overview & Pipeline", "html"),
        F("implementation", "Implementation Details", "html"),
        F("platforms", "Target Platforms & Devices", "tags", help="Comma separated: Meta Quest 3, HoloLens 2, ARCore"),
        F("ss1", "Demo Screenshot 1 (Square)", "image"),
        F("ss2", "Demo Screenshot 2 (Square)", "image"),
        F("ss3", "Demo Screenshot 3 (Square)", "image"),
        F("ss4", "Demo Screenshot 4 (Square)", "image"),
        F("bb1", "Tech-stack Logo 1 (Landscape)", "image"),
        F("bb2", "Tech-stack Logo 2 (Landscape)", "image"),
        F("bb3", "Tech-stack Logo 3 (Landscape)", "image"),
        F("bb4", "Tech-stack Logo 4 (Landscape)", "image"),
        F("evaluation", "Performance & Evaluation", "html"),
        F("insight1", "Key Metric - 1", "html"),
        F("insight2", "Key Metric - 2", "html"),
        F("limitations", "Limitations & Future Work", "html"),
    ],
    # ---- learning-design write-up -------------------------------------------
    "edtech": [
        F("title", "Title", "text", required=True),
        F("icon", "Choose Relevant Icon", "image", required=True),
        F("userpersonaimage", "Learner Persona Image (Passport)", "image"),
        F("userquote", "Learner Voice / Quote", "text"),
        F("learning_problem", "Learning Problem / Gap", "html"),
        F("learning_objectives", "Learning Objectives", "html"),
        F("target_learners", "Target Learners (age, grade, subject)", "text"),
        F("curriculum", "Curriculum / Topic Alignment", "text"),
        F("pedagogy", "Pedagogical Framework", "html", help="e.g. embodied cognition, constructionism"),
        F("tangible_design", "Tangible / Embodied Artefact Design", "html"),
        F("activity_design", "Learning Activity Design", "html"),
        F("ss1", "Artefact / Classroom Photo 1 (Square)", "image"),
        F("ss2", "Artefact / Classroom Photo 2 (Square)", "image"),
        F("ss3", "Artefact / Classroom Photo 3 (Square)", "image"),
        F("ss4", "Artefact / Classroom Photo 4 (Square)", "image"),
        F("sess1", "In-session Screenshot 1 (Landscape)", "image"),
        F("sess2", "In-session Screenshot 2 (Landscape)", "image"),
        F("sess3", "In-session Screenshot 3 (Landscape)", "image"),
        F("bb1", "Component Logo 1 (Landscape)", "image"),
        F("bb2", "Component Logo 2 (Landscape)", "image"),
        F("bb3", "Component Logo 3 (Landscape)", "image"),
        F("bb4", "Component Logo 4 (Landscape)", "image"),
        F("deployment", "Deployment Context & Participants", "html"),
        F("assessment", "Assessment & Data Collected", "html"),
        F("insight1", "Learning Outcome - 1", "html"),
        F("insight2", "Learning Outcome - 2", "html"),
        F("findings", "Findings & Implications", "html"),
    ],
}

# --------------------------------------------------------------------------
# PUBLICATION templates (the template-specific part; PUB_BASE / PUB_COMMON wrap it)
# --------------------------------------------------------------------------
PUB_TEMPLATE_FIELDS = {
    "hci": [
        F("research_question", "Research Question", "html"),
        F("study_design", "Study Design & Participants", "html"),
        F("key_findings", "Key Findings", "html"),
        F("design_implications", "Design Implications", "html"),
    ],
    "tech": [
        F("technical_contribution", "Technical Contribution", "html"),
        F("system_method", "System / Method Overview", "html"),
        F("evaluation", "Evaluation & Benchmarks", "html"),
        F("limitations", "Limitations & Future Work", "html"),
    ],
    "edtech": [
        F("learning_context", "Learning Context & Target Learners", "html"),
        F("pedagogical_framework", "Pedagogical Framework", "html"),
        F("intervention", "Intervention / Learning Activity", "html"),
        F("study_sample", "Sample, Setting & Duration", "text"),
        F("learning_outcomes", "Learning Outcomes", "html"),
        F("implications_educators", "Implications for Educators", "html"),
    ],
}


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def valid_template(key):
    return key if key in TEMPLATE_LABELS else DEFAULT_TEMPLATE


def template_fields(kind, template):
    """Template-specific fields only (what differs between templates)."""
    template = valid_template(template)
    if kind == "project":
        return list(PROJECT_TEMPLATE_FIELDS[template])
    return list(PUB_TEMPLATE_FIELDS[template])


def base_fields(kind):
    """Fields every template of this kind shares (always shown first)."""
    return list(PUB_BASE) if kind == "pub" else []


def common_fields(kind):
    return list(PUB_COMMON if kind == "pub" else PROJECT_COMMON)


def fields_for(kind, template):
    """All fields (excluding the video / 3D media blocks) used by a template, in form order."""
    return base_fields(kind) + template_fields(kind, template) + common_fields(kind)


def all_fields(kind):
    """Every field of every template (de-duplicated by key) - used for validation / path resolving."""
    seen, out = set(), []
    for tpl, _ in TEMPLATES:
        for f in fields_for(kind, tpl):
            if f["key"] not in seen:
                seen.add(f["key"])
                out.append(f)
    return out


def find_field(kind, key):
    for f in all_fields(kind):
        if f["key"] == key:
            return f
    return None


# --------------------------------------------------------------------------
# parsing helpers used by the page templates
# --------------------------------------------------------------------------
def split_tags(text):
    return [t.strip() for t in (text or "").replace("\n", ",").split(",") if t.strip()]


def _looks_like_url(s):
    s = (s or "").strip().lower()
    return s.startswith(("http://", "https://", "mailto:", "/"))


def parse_list(text):
    """'Name | URL | Note' lines -> [{'name','url','note'}]"""
    items = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("|")]
        name, url, note = parts[0], "", ""
        rest = parts[1:]
        if rest and _looks_like_url(rest[0]):
            url, rest = rest[0], rest[1:]
        note = " | ".join(p for p in rest if p)
        if name or url:
            items.append({"name": name or url, "url": url, "note": note})
    return items


def video_info(url):
    """Turn a pasted video link into something embeddable: ('iframe'|'video', src) or None."""
    import re
    url = (url or "").strip()
    if not url:
        return None
    low = url.lower().split("?")[0]
    if low.endswith((".mp4", ".webm", ".ogg", ".mov")):
        return ("video", url)
    m = re.search(r"(?:youtube\.com/(?:watch\?(?:.*&)?v=|embed/|shorts/|live/)|youtu\.be/)([\w-]{6,})", url)
    if m:
        return ("iframe", "https://www.youtube.com/embed/" + m.group(1))
    m = re.search(r"vimeo\.com/(?:video/)?(\d+)", url)
    if m:
        return ("iframe", "https://player.vimeo.com/video/" + m.group(1))
    return ("iframe", url)          # anything else: assume it is already an embed link
