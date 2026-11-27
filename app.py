from flask import Flask, render_template, redirect, request, session, abort, url_for, send_from_directory, jsonify
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
import os
import time
import json
from flask_frozen import Freezer

import schema
from database import *

load_dotenv()
app = Flask(__name__)


@app.template_filter("linkedin_connect")
def linkedin_connect(url):
    """LinkedIn profile URL -> the 'send a connection request' dialog URL; anything else is returned unchanged."""
    import re as _re
    m = _re.search(r"linkedin\.com/in/([^/?#]+)", url or "")
    return "https://www.linkedin.com/preload/custom-invite/?vanityName=" + m.group(1) if m else url

load_pubs_flag = True

app.secret_key = os.getenv("SECRET_KEY") 

app.config['UPLOAD_FOLDER'] = "static/uploads"

# helpers the page templates use for the template-specific fields (see schema.py)
app.jinja_env.filters['tags'] = schema.split_tags          # "a, b" -> ['a', 'b']
app.jinja_env.filters['lines'] = schema.parse_list         # "Name | URL | Note" lines -> [{name,url,note}]
app.jinja_env.globals['video_info'] = schema.video_info    # pasted video link -> embeddable source
app.jinja_env.globals['schema'] = schema                   # field lists per template (used by forms and detail pages)


@app.context_processor
def inject_site_state():
    """Which homepage sections have something to show (used by every page's menu)."""
    pubs, projects = visible(load_pubs()), visible(load_proj())
    nav = {
        "education": bool(load_educations()),
        "pubs": bool(pubs),
        "projects": bool(projects),
        "artifacts": bool(all_artifacts(projects, pubs)),
        "skills": bool(load_skills()),
        "writings": bool(load_writing()),
        "conferences": bool(load_conferences()),
        "code": bool(load_repos(only_visible=True)),
        "gallery": True,
        "certifications": bool(load_certifications()),
        "pages": bool(load_pages()),
    }
    return dict(nav=nav)


@app.route("/submitabout", methods=["POST"])
def about_submitted():
    if request.method == "POST":    
        name = request.form["name"]
        about = request.form["about"]
        photo_file = request.files["photo"]
        store_about(name, about, photo_file ,app.config['UPLOAD_FOLDER'])

    return redirect("/edit")

@app.route("/submitskills", methods=["POST"])
def skill_submitted():
    if request.method == "POST":    
        skill = request.form["skill"]
        skill_icon = request.files["skill-icon"]
        insertintoskills(skill,skill_icon,app.config['UPLOAD_FOLDER']) 
    return redirect("/edit")


@app.route("/submiteducation", methods=["POST"])
def education_submitted():
    if request.method == "POST":    
        degree = request.form["degree"]
        specialisation = request.form["specialisation"]
        grades = request.form.get("grades", "")          # optional
        html = request.form.get("html", "")
        icon = request.files.get("icon")
        institute = request.form["institute"]
        try:
            insertintoeducations(degree,specialisation,grades,html,icon,institute,app.config['UPLOAD_FOLDER'],
                                 request.form.get("status", "Completed"), request.form.get("id") or None)
        except ValueError as e:
            abort(400, str(e))
    return redirect("/edit")

@app.route("/submitdoi", methods=["POST"])
def doi_submitted():
    if request.method == "POST":
        template = schema.valid_template(request.form.get("template"))
        try:
            store_pub_from_form(template, request.form, request.files, app.config['UPLOAD_FOLDER'])
        except ValueError as err:
            abort(400, description=str(err))

    return redirect("/edit")


@app.route("/storeproj", methods=["POST"])
def store_projects():
    if request.method == "POST":
        template = schema.valid_template(request.form.get("template"))
        try:
            store_project_from_form(template, request.form, request.files, app.config['UPLOAD_FOLDER'])
        except ValueError as err:
            abort(400, description=str(err))

    return redirect("/edit")


@app.route("/submitwriting", methods=["POST"])
def store_writings():
    if request.method == "POST":    
        try:
            store_writing(request.form.get("title",""), request.form.get("linkedin_url",""), request.form.get("medium_url",""))
        except ValueError as e:
            abort(400, str(e))

    return redirect("/edit")




@app.route("/submitportfolio", methods=["POST"])
def store_pages():
    if request.method == "POST":    
        title = request.form["title"]
        page = request.files["page"]
        store_Pages(title,page,app.config['UPLOAD_FOLDER'])
    return redirect("/edit")


def _ts():
    return int(time.time() * 1000)

# ---------- publication / project UPDATE ROUTES ----------
# One route per kind replaces the old one-route-per-field functions; the URLs are unchanged
# (/updateproj/title, /updatepub/doi, ...).  The allowed fields come from schema.py.

def _update_entry(kind, field, edit_endpoint):
    entry_id = request.form["id"]
    spec = schema.find_field(kind, field)
    if spec is None:
        abort(404)
    try:
        if spec["type"] == "image":
            update_image_field(kind, entry_id, field, request.files.get(field), app.config["UPLOAD_FOLDER"])
        elif kind == "pub" and field == "doi":
            update_publication_doi(entry_id, request.form["doi"].strip())
        else:
            update_field(kind, entry_id, field, (request.form.get(field) or "").strip())
    except ValueError as err:
        abort(400, description=str(err))
    return redirect(url_for(edit_endpoint, id=entry_id))


def _update_media(kind, edit_endpoint):
    entry_id = request.form["id"]
    which = request.form.get("which")
    if which not in ("video", "model"):
        abort(400)
    try:
        update_media(kind, entry_id, which, request.form, request.files, app.config["UPLOAD_FOLDER"])
    except ValueError as err:
        abort(400, description=str(err))
    return redirect(url_for(edit_endpoint, id=entry_id))


def _update_template(kind, edit_endpoint):
    entry_id = request.form["id"]
    set_template(kind, entry_id, request.form.get("template"))
    return redirect(url_for(edit_endpoint, id=entry_id))


@app.route("/updatepub/media", methods=["POST"])
def update_pub_media():
    return _update_media("pub", "publication_edit_page")


@app.route("/updateproj/media", methods=["POST"])
def update_proj_media():
    return _update_media("project", "project_edit_page")


@app.route("/updatepub/template", methods=["POST"])
def update_pub_template():
    return _update_template("pub", "publication_edit_page")


@app.route("/updateproj/template", methods=["POST"])
def update_proj_template():
    return _update_template("project", "project_edit_page")


@app.route("/updatepub/<field>", methods=["POST"])
def update_pub_field(field):
    return _update_entry("pub", field, "publication_edit_page")


@app.route("/updateproj/<field>", methods=["POST"])
def update_proj_field(field):
    return _update_entry("project", field, "project_edit_page")


@app.route("/submitpubsorder", methods = ["POST"])
def pub_order_submitted():
    if request.method == "POST":
        ordered_json = request.form.get("ordered_pubs")  # 'ordered_pubs' matches input name
        if ordered_json:
            ordered_dois = json.loads(ordered_json)            
            store_order_in_pubs(ordered_dois)
    return redirect("/edit")


@app.route("/submitwritingsorder", methods = ["POST"])
def writing_order_submitted():
    if request.method == "POST":
        ordered_json = request.form.get("ordered_writings") 
        if ordered_json:
            ordered_ids = json.loads(ordered_json)            
            store_order_in_writings(ordered_ids)
    return redirect("/edit")


@app.route("/submitskillsorder", methods = ["POST"])
def skill_order_submitted():
    if request.method == "POST":
        ordered_json = request.form.get("ordered_skills")  # 'ordered_pubs' matches input name
        if ordered_json:
            ordered_ids = json.loads(ordered_json)            
            store_order_in_skills(ordered_ids)
    return redirect("/edit")

@app.route("/submiteducationsorder", methods = ["POST"])
def education_order_submitted():
    if request.method == "POST":
        ordered_json = request.form.get("ordered_educations")  # 'ordered_pubs' matches input name
        if ordered_json:
            ordered_ids = json.loads(ordered_json)            
            store_order_in_educations(ordered_ids)
    return redirect("/edit")

@app.route("/submitprojectssorder", methods = ["POST"])
def projects_order_submitted():
    if request.method == "POST":
        ordered_json = request.form.get("ordered_projects")  # 'ordered_pubs' matches input name
        if ordered_json:
            ordered_ids = json.loads(ordered_json)            
            store_order_in_projects(ordered_ids)
    return redirect("/edit")


@app.route("/submitpagesorder", methods = ["POST"])
def pages_order_submitted():
    if request.method == "POST":
        ordered_json = request.form.get("ordered_pages") 
        if ordered_json:
            ordered_ids = json.loads(ordered_json)            
            store_order_in_pages(ordered_ids)
    return redirect("/edit")

@app.route("/editor")
def editorpoint():
        return render_template('editor.html')


@app.route("/edit")
def editpoint():
    if load_pubs_flag == True:
        about = load_about()
        pubs = load_pubs()
        misc = load_misc()
        skills= load_skills()
        footer = load_footer()      
        projects = load_proj()
        educations = load_educations()
        pages = load_pages()
        writings = load_writing()
        return render_template('edit.html', about = about, pubs = pubs, misc = misc, skills = skills, footer = footer, projects = projects, educations = educations, pages = pages, writings = writings, artifact_list = load_artifacts(),
                               certification_list = load_certifications(), conference_list = load_conferences(), conference_roles = CONFERENCE_ROLES,
                               repo_list = load_repos(), repo_categories = REPO_CATEGORIES, github_user = github_username(misc.github if misc else ''),
                               education_statuses = EDUCATION_STATUSES, photo_list = load_photos(), ar_cfg = load_ar_config())
    else:
        return render_template('edit.html')
    

@app.route('/publication_edit_page/<id>')
def publication_edit_page(id):
    publication = get_publication_by_slug(id)    
    if not publication:
        abort(404)
    return render_template('pub_edit.html', publication=publication)

@app.route('/project_edit_page/<id>')
def project_edit_page(id):
    project = get_project_by_slug(id)
    if not project:
        abort(404)
    return render_template('project_edit.html', project = project)
 
@app.route('/publications/<id>.html')
def publication_detail(id):
    publication = get_publication_by_slug(id)    
    if not publication:
        abort(404)
    return render_template('pubs.html', publication=publication)

@app.route('/resume.html')
def resume_detail():
    misc = load_misc()
    footer = load_footer()
    pages = load_pages()
    return render_template('resume.html', misc = misc, footer = footer, pages = pages)


@app.route('/artifacts.html')
def artifacts_page():
    misc = load_misc()
    footer = load_footer()
    artifacts = all_artifacts(visible(load_proj()), visible(load_pubs()))
    return render_template('artifacts.html', misc = misc, footer = footer, artifacts = artifacts)


@app.route('/gallery.html')
def gallery_page():
    """Gallery tab: AR introduction (MindAR) for visitors with my visiting card."""
    misc = load_misc()
    footer = load_footer()
    return render_template('gallery.html', misc = misc, footer = footer, photos = load_photos(), ar = load_ar_config())


@app.route('/ar.html')
def ar_page():
    """Short, permanent address for the QR code on the visiting card: forwards to the gallery with the AR layer open."""
    return render_template('ar.html')


@app.route('/conferences.html')
def conferences_page():
    misc = load_misc()
    footer = load_footer()
    conferences = load_conferences()
    # filter chips on the page: only the kinds of participation that actually occur, in the editor's order
    roles = [r for r in CONFERENCE_ROLES if any(r in c.roles for c in conferences)]
    return render_template('conferences.html', misc = misc, footer = footer, conferences = conferences, roles = roles)


@app.route('/code.html')
def code_page():
    misc = load_misc()
    footer = load_footer()
    repos = load_repos(only_visible=True)
    # filter chips: only categories that occur, in the order of the starter list (own labels after them)
    used = {r.category or "Other" for r in repos}
    categories = [c for c in REPO_CATEGORIES if c in used] + sorted(c for c in used if c not in REPO_CATEGORIES)
    tech_bar, repo_tech = code_tech_index(repos)
    stats = {"repos": len(repos), "stars": sum(r.stars for r in repos), "categories": len(categories)}
    return render_template('code.html', misc = misc, footer = footer, repos = repos, categories = categories, stats = stats,
                           tech_bar = tech_bar, repo_tech = repo_tech,
                           github_user = github_username(misc.github if misc else ''))


@app.route("/syncgithub", methods=["POST"])
def sync_github_route():
    try:
        sync_github_repos(request.form.get("username", ""))
    except ValueError as e:
        abort(400, str(e))
    return redirect("/edit")


@app.route("/addrepo", methods=["POST"])
def add_repo_route():
    try:
        add_github_repo(request.form.get("repo", ""))
    except ValueError as e:
        abort(400, str(e))
    return redirect("/edit")


@app.route("/submitrepo", methods=["POST"])
def store_repo_route():
    try:
        store_repo(request.form.get("id") or None, request.form.get("title", ""), request.form.get("description", ""),
                   request.form.get("category", ""),
                   request.form.get("pinned") is not None, request.form.get("hidden") is not None, request.form.get("stack", ""),
                   request.form.get("live", ""))
    except ValueError as e:
        abort(400, str(e))
    return redirect("/edit")


@app.route("/togglerepo", methods=["POST"])
def toggle_repo_route():
    try:
        toggle_repo(request.form.get("id"), request.form.get("field", ""))
    except ValueError as e:
        abort(400, str(e))
    return redirect("/edit")


@app.route("/submitreposorder", methods=["POST"])
def repo_order_submitted():
    ordered_json = request.form.get("ordered_repos")
    if ordered_json:
        store_order_in_repos(json.loads(ordered_json))
    return redirect("/edit")


@app.route("/deleterepo", methods=["POST"])
def delete_repo():
    delete_id_repo(request.form["delete_repo"])
    return redirect("/edit")


@app.route("/submitar", methods=["POST"])
def store_ar_route():
    try:
        store_ar_config(request.form, request.files.get("mind"), request.files.get("model"), app.config['UPLOAD_FOLDER'])
    except ValueError as e:
        abort(400, str(e))
    return redirect("/edit")


@app.route("/resetar", methods=["POST"])
def reset_ar_route():
    reset_ar_config(app.config['UPLOAD_FOLDER'])
    return redirect("/edit")


@app.route("/submitphoto", methods=["POST"])
def store_photo_route():
    try:
        if request.form.get("id"):
            store_photo(request.form["id"], request.form.get("caption", ""), request.form.get("taken", ""), request.form.get("category", ""),
                        request.files.get("photos"), app.config['UPLOAD_FOLDER'], request.form.get("insta", ""))
        else:
            add_photos(request.files.getlist("photos"), request.form.get("caption", ""), request.form.get("taken", ""),
                       request.form.get("category", ""), app.config['UPLOAD_FOLDER'], request.form.get("insta", ""))
    except ValueError as e:
        abort(400, str(e))
    return redirect("/edit")


@app.route("/submitphotosorder", methods=["POST"])
def photo_order_submitted():
    ordered_json = request.form.get("ordered_photos")
    if ordered_json:
        store_order_in_photos(json.loads(ordered_json))
    return redirect("/edit")


@app.route("/deletephoto", methods=["POST"])
def delete_photo():
    delete_id_photo(request.form["delete_photo"], app.config['UPLOAD_FOLDER'])
    return redirect("/edit")


@app.route("/submitcertification", methods=["POST"])
def store_certification_route():
    try:
        store_certification(request.form.get("title",""), request.form.get("company",""), request.form.get("credential",""),
                            request.form.get("issued",""), request.files.get("file"), app.config['UPLOAD_FOLDER'],
                            request.form.get("id") or None)
    except ValueError as e:
        abort(400, str(e))
    return redirect("/edit")


@app.route("/submitcertificationsorder", methods=["POST"])
def certification_order_submitted():
    ordered_json = request.form.get("ordered_certifications")
    if ordered_json:
        store_order_in_certifications(json.loads(ordered_json))
    return redirect("/edit")


@app.route("/deletecertification", methods=["POST"])
def delete_certification():
    delete_id_certification(request.form["delete_certification"], app.config['UPLOAD_FOLDER'])
    return redirect("/edit")


@app.route("/submitconference", methods=["POST"])
def store_conference_route():
    try:
        store_conference(request.form.get("name",""), request.form.getlist("roles") or request.form.getlist("role"), request.form.get("paper_title",""),
                         request.form.get("location",""), request.form.get("held_on",""), request.form.get("link",""),
                         request.form.get("id") or None)
    except ValueError as e:
        abort(400, str(e))
    return redirect("/edit")


@app.route("/submitconferencesorder", methods=["POST"])
def conference_order_submitted():
    ordered_json = request.form.get("ordered_conferences")
    if ordered_json:
        store_order_in_conferences(json.loads(ordered_json))
    return redirect("/edit")


@app.route("/deleteconference", methods=["POST"])
def delete_conference():
    delete_id_conference(request.form["delete_conference"])
    return redirect("/edit")


@app.route("/submitartifact", methods=["POST"])
def store_artifact_route():
    try:
        store_artifact(request.form.get("title",""), request.form.get("url",""), request.form.get("note",""))
    except ValueError as e:
        abort(400, str(e))
    return redirect("/edit")


@app.route("/submitartifactsorder", methods=["POST"])
def artifact_order_submitted():
    ordered_json = request.form.get("ordered_artifacts")
    if ordered_json:
        store_order_in_artifacts(json.loads(ordered_json))
    return redirect("/edit")


@app.route("/deleteartifact", methods=["POST"])
def delete_artifact():
    delete_id_artifact(request.form["delete_artifact"])
    return redirect("/edit")


@app.route('/writings.html')
def writing_detail():
    misc = load_misc()
    footer = load_footer()
    writings = load_writing()
    return render_template('writings.html', misc = misc, footer = footer, writings = writings)


@app.route("/static/uploads/html/<path:filename>")
def serve_portfolio_page(filename):
    return send_from_directory("static/uploads/html", filename)

@app.route('/projects/<id>.html')
def project_detail(id):
    project = get_project_by_slug(id)    
    if not project:
        abort(404)
    return render_template('projects.html', project = project)

@app.route("/deletedoi", methods = ["POST"])
def delete_doi():
    if request.method == "POST":
        doi = request.form["delete_doi"]
        print(doi)
        delete_Doi_pub(doi)
        return redirect("/edit")
    
@app.route("/deleteskill", methods = ["POST"])
def delete_skill():
    if request.method == "POST":
        id = request.form["delete_skill"]        
        delete_id_skill(id)
        return redirect("/edit")
    
@app.route("/deleteproj", methods = ["POST"])
def delete_proj():
    if request.method == "POST":
        id = request.form["delete_project"]        
        delete_id_proj(id)
        return redirect("/edit")
    
@app.route("/hideproj", methods = ["POST"])
def hide_proj():
    if request.method == "POST":
        id = request.form["hide_project"]        
        hide_id_proj(id)
        return redirect("/edit")
@app.route("/showproj", methods = ["POST"])
def show_proj():
    if request.method == "POST":
        id = request.form["show_project"]        
        show_id_proj(id)
        return redirect("/edit")
    
@app.route("/hidepub", methods = ["POST"])
def hide_pub():
    if request.method == "POST":
        id = request.form["hide_publication"]        
        hide_id_pub(id)
        return redirect("/edit")
@app.route("/showpub", methods = ["POST"])
def show_pub():
    if request.method == "POST":
        id = request.form["show_publication"]        
        show_id_pub(id)
        return redirect("/edit")
    
@app.route("/deletepage", methods = ["POST"])
def delete_page():
    if request.method == "POST":
        id = request.form["delete_page"]        
        delete_id_page(id)
        return redirect("/edit")
    
@app.route("/deletewriting", methods = ["POST"])
def delete_writing():
    if request.method == "POST":
        id = request.form["delete_writing"]        
        delete_id_writing(id)
        return redirect("/edit")
    
    
@app.route("/deleteeducation", methods = ["POST"])
def delete_education():
    if request.method == "POST":
        id = request.form["delete_education"]        
        delete_id_education(id)
        return redirect("/edit")
    
@app.route("/misc", methods = ["POST"])
def misc_section():
    if request.method == "POST":
        loader = request.files["loader"]
        logo = request.files["logo"]
        resume = request.files["resume"]   
        email = request.form["email"]
        linkedin = request.form["linkedin"]
        instagram = request.form["instagram"]
        topmate = request.form["topmate"]
        github = request.form["github"]
        update_misc(loader,logo,resume,email,linkedin, instagram, topmate, github,app.config['UPLOAD_FOLDER'])     
        return redirect("/edit")
    

@app.route("/footer", methods = ["POST"])
def footer_section():
    if request.method == "POST":
        logo = request.files["footer_logo"]
        banner = request.files["banner"]
        text = request.form["footer_text"]
        copyright = request.form["copyright_text"]        
        update_footer(logo, banner,text,copyright,app.config['UPLOAD_FOLDER'])        
        return redirect("/edit")


@app.route("/")
def startpoint():
    global load_pubs_flag
    about = load_about()
    misc  = load_misc()
    skills = load_skills()
    footer = load_footer()
    projects = visible(load_proj())
    education = load_educations()
    if about is not None: 
        if load_pubs_flag is True:
            pubs = visible(load_pubs())
            # each template (HCI & AR-VR / Tech for AR-VR / Educational Technology) only appears if it has an entry
            return render_template('index.html', about = about, pubs = pubs, misc = misc, skills = skills, footer = footer,
                                   projects = projects, education = education, certifications = load_certifications(),
                                   pub_groups = group_by_template(pubs), project_groups = group_by_template(projects),
                                   artifacts = all_artifacts(projects, pubs))
        else:
            return render_template('index.html', about = about)
    return "Hello World"


# ---------- /glance : build a "works at a glance" page ----------
@app.route("/glance")
def glance_constructor():
    return render_template('glance.html', pages = load_pages(), projects = load_proj(), pubs = load_pubs())


@app.route("/glance/save", methods=["POST"])
def glance_save():
    title = (request.form.get("title") or "").strip()
    page = request.files.get("page")          # sent as a file: pages with an embedded image are bigger than a form field may be
    if not title or page is None:
        abort(400, description="A title and the page HTML are required.")
    try:
        html_text = page.read().decode("utf-8")
    except UnicodeDecodeError:
        abort(400, description="The page must be UTF-8 text.")
    page_id = store_glance_page(title, html_text, app.config['UPLOAD_FOLDER'], request.form.get("replace_id") or None)
    return jsonify(ok=True, id=page_id)


if __name__ == "__main__":
    app.run()
    