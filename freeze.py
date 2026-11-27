"""Build the static copy of the site (python freeze.py) -> ./build

Only the public pages are frozen.  The editor pages (/edit, /editor, /glance, /project_edit_page/<id>,
/publication_edit_page/<id>) and every POST/admin route are left out on purpose, so no extension-less
"editor"/"edit"/"glance"/"1"... files end up in the build any more.
"""
import os
import warnings
from flask_frozen import Freezer, MissingURLGeneratorWarning
from app import app
from database import *

app.config['FREEZER_RELATIVE_URLS'] = True
app.config['FREEZER_DEFAULT_MIMETYPE'] = 'text/html'
app.config['FREEZER_IGNORE_MIMETYPE_WARNINGS'] = True

# with_no_argument_rules=False : don't auto-add every parameter-less route (that is what pulled in /edit, /editor, /glance)
# log_url_for=False            : don't crawl the url_for() calls of rendered pages (that is what pulled in the edit pages)
freezer = Freezer(app, with_no_argument_rules=False, log_url_for=False)
# the editor / POST endpoints are deliberately not frozen, so Frozen-Flask's "nothing frozen for endpoints ..." note is expected
warnings.filterwarnings('ignore', category=MissingURLGeneratorWarning)

UPLOADED_PAGES = os.path.join(app.root_path, 'static', 'uploads', 'html')


@freezer.register_generator
def index():
    yield '/'


@freezer.register_generator
def resume_detail():
    yield '/resume.html'


@freezer.register_generator
def artifacts_page():
    yield '/artifacts.html'


@freezer.register_generator
def writing_detail():
    yield '/writings.html'


@freezer.register_generator
def ar_page():
    yield '/ar.html'


@freezer.register_generator
def gallery_page():
    yield '/gallery.html'


@freezer.register_generator
def conferences_page():
    yield '/conferences.html'


@freezer.register_generator
def code_page():
    yield '/code.html'


@freezer.register_generator
def publication_detail():
    for pub in visible(load_pubs()):                     # entries hidden in the editor are not published
        yield f'/publications/{pub.id}.html'


@freezer.register_generator
def project_detail():
    for proj in visible(load_proj()):
        yield f'/projects/{proj.id}.html'


@freezer.register_generator
def serve_portfolio_page():
    # the "works at a glance" pages (/glance output); flipbook reads them from static/uploads/html
    if os.path.isdir(UPLOADED_PAGES):
        for name in sorted(os.listdir(UPLOADED_PAGES)):
            if os.path.isfile(os.path.join(UPLOADED_PAGES, name)):
                yield {'filename': name}


if __name__ == '__main__':
    freezer.freeze()
