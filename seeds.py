"""One-time starter entries added to a portfolio database the first time the app starts after an update.

Each seed runs once (it is recorded in the SeedLog table), so editing or deleting the entry later is safe:
it will not come back.
"""

# Mitra - from the ET-606 (Educational Technology Tools Lab) end-semester project report.
MITRA_PROJECT = {
    "title": "Mitra: An Embodied Tangible Environment for Spatial Reasoning",
    "icon": "mitra_icon.png",
    "role": "Designer & developer",
    "timeline": "ET-606 Tools Lab · Nov 2026",
    "tech_stack": "Unity 6.3, BBC Micro:bit, 3D printing, LA-Reflect, Google AI Studio",
    "resources": "Source code (GitHub) | https://github.com/gaurishgarg/Project_Mitra",

    "target_learners": "Upper elementary school students",
    "curriculum": "Spatial reasoning: object orientation, mental rotation and spatial projections",
    "ss1": "mitra_activity1_maze.jpg",
    "ss2": "mitra_activity2_orientation.jpg",
    "ss3": "mitra_activity3_projection.jpg",
    "sess1": "mitra_session1_maze.png",
    "sess2": "mitra_session2_orientation.png",
    "sess3": "mitra_session3_projection.png",
    "bb1": "mitra_la_reflect.png",
    "bb2": "mitra_dashboard.png",
    "bb3": "mitra_replay.png",
}

# Condensed wording (the page had too much text).
MITRA_TEXT_SHORT = {'activity_design': '<p><b>1. Maze:</b> tilt the Micro:bit to guide a ball to the exit.</p><p><b>2. Match '
                    'the orientation:</b> rotate an object to a target orientation.</p><p><b>3. '
                    "Predict-Observe-Explain:</b> predict a 3D object's projection, observe it, then explain "
                    'aloud.</p>',
 'assessment': '<p>Pre/post test (items from the Spatial Reasoning Instrument, built with LA-Reflect) and a '
               'CSV interaction log, with a Unity replay mode and an HTML dashboard.</p>',
 'deployment': '<p>A working prototype from ET-606 (Tools Lab, CET, IIT Bombay), with no formal user study '
               'yet. <b>Next:</b> a study with upper elementary students on usability, engagement and '
               'spatial reasoning.</p>',
 'learning_objectives': '<p>Learners practise the bodily actions of spatial orientation, mentally rotate '
                        'objects to match a target, and predict, observe and explain 3D projections.</p>',
 'learning_problem': '<p>Spatial reasoning is underemphasised in upper elementary education and mostly '
                     'taught through static textbook methods, yet it is inherently embodied. Mitra asks '
                     'whether physically enacting spatial transformations helps.</p>',
 'pedagogy': '<p>Embodied cognition, a spiral curriculum (from bodily orientation to abstract projections), '
             'constructivism and pair discussion.</p>',
 'tangible_design': '<p>A BBC Micro:bit in a 3D-printed case is the controller: turning it turns a virtual '
                    '3D object in Unity. It is an interface, not a replica, so one controller stands in for '
                    'many objects and logs every rotation.</p>'}
MITRA_PROJECT.update(MITRA_TEXT_SHORT)

# The first, longer wording. A database that still holds it unedited is switched to the short one once;
# any field the owner has changed is left alone.
MITRA_TEXT_LONG = {'activity_design': '<p><b>1. Maze:</b> rotate the Micro:bit to tilt a virtual maze and guide a ball to the '
                    'exit.</p><p><b>2. Match the orientation:</b> rotate the Micro:bit to turn a virtual '
                    'object until it aligns with a given target orientation.</p><p><b>3. '
                    'Predict-Observe-Explain:</b> predict the projection of a 3D object, rotate the '
                    'Micro:bit to observe the projections, then explain the reasoning aloud.</p>',
 'assessment': '<p><b>Pre- and post-assessment:</b> questions based on selected items from the Spatial '
               'Reasoning Instrument, designed with LA-Reflect and Google AI Studio.</p><p><b>Interaction '
               'log:</b> timestamps, activity states, object and camera positions and rotations, and task '
               'completion are recorded as CSV. A Unity replay mode reconstructs recorded sessions, and a '
               'standalone HTML dashboard visualises the data (see Components).</p>',
 'deployment': '<p>Mitra is a developed prototype, built as the end-semester project for ET-606 (Educational '
               'Technology Tools Lab) at the Centre for Educational Technology, IIT Bombay. Its '
               'effectiveness in improving spatial reasoning has not yet been established through a formal '
               'user study.</p><p><b>Next:</b> a structured evaluation with upper elementary school students '
               'to examine usability, engagement and potential to support spatial reasoning, with the '
               'activities refined for an appropriate level of cognitive challenge and the assessment items '
               'reviewed for age appropriateness.</p>',
 'learning_objectives': '<p>Explore how embodied interaction with tangible artefacts can support the '
                        'development of spatial reasoning in upper elementary school students. '
                        'Learners:</p><p>1. learn the bodily actions associated with spatial '
                        'orientation;</p><p>2. mentally rotate objects to match a target orientation; '
                        'and</p><p>3. predict, observe and explain the projections of 3D objects.</p>',
 'learning_problem': '<p>Spatial reasoning, which covers mental rotation, spatial visualisation and spatial '
                     'perspective taking, is underemphasised in upper elementary education. It is often '
                     'taught through non-interactive textbook methods, which have yielded limited '
                     'results.</p><p>Spatial reasoning is also inherently embodied: it involves imagining '
                     'movement, transformation and perspective in space. Mitra asks whether physically '
                     'enacting those transformations can help.</p>',
 'pedagogy': '<p><b>Embodied cognition:</b> physical actions are aligned with the spatial concepts through '
             'embodied manipulation.</p><p><b>Spiral curriculum:</b> three activity sets move from bodily '
             'actions of orientation to abstract concepts such as projections.</p><p><b>Constructivism:</b> '
             'learners explore, make predictions, observe outcomes and reflect on their '
             'understanding.</p><p><b>Social learning:</b> every learner interacts individually, while pair '
             'discussions let them compare predictions and express their reasoning.</p>',
 'tangible_design': '<p>Mitra stands for <i>Micro:bit-enabled Interactive Tangible spatial-Reasoning '
                    'Activities</i>. A BBC Micro:bit in a 3D-printed case is the tangible controller: its '
                    'orientation is mapped to the rotation of virtual 3D objects in a Unity environment, so '
                    'learners physically turn the controller to turn the object.</p><p>The Micro:bit is '
                    'deliberately an interface, not a physical replica. One controller can stand in for many '
                    'representations (a house, an aeroplane, a cube and so on), while the virtual side '
                    'offers consistent starting orientations, repeatable transformations and dynamic '
                    'visualisation of projections. It also lets educators collect log data of the rotations '
                    'learners perform.</p>'}

# files in static/uploads this seed refers to - the seed waits until they are all there
MITRA_FILES = ["mitra_icon.png", "mitra_activity1_maze.jpg", "mitra_activity2_orientation.jpg", "mitra_activity3_projection.jpg",
               "mitra_la_reflect.png", "mitra_dashboard.png", "mitra_replay.png",
               "mitra_session1_maze.png", "mitra_session2_orientation.png", "mitra_session3_projection.png"]

# Added in a later update: for databases that already have the Mitra entry, these in-session screenshots
# (AR camera feed replaced with a black background) are filled into its empty slots once.
MITRA_SESSION_SHOTS = {
    "sess1": "mitra_session1_maze.png",
    "sess2": "mitra_session2_orientation.png",
    "sess3": "mitra_session3_projection.png",
}



# ---------------------------------------------------------------------------
# The portfolio constructor itself, listed as a "Tech for AR-VR" (tech template) project.
# Inserted once on the first start after this update; edit / hide / delete it like any other project
# (a deleted one does not come back).
# ---------------------------------------------------------------------------
CONSTRUCTOR_FILES = ["constructor_icon.png", "constructor_architecture.png"]
CONSTRUCTOR_TITLE = "Portfolio Constructor: an editor that publishes a static research portfolio"
CONSTRUCTOR_PROJECT = {
    "title": CONSTRUCTOR_TITLE,
    "icon": "constructor_icon.png",
    "role": "Designer & developer (solo)",
    "timeline": "2025 - 2026",
    "tech_stack": "Python, Flask, Jinja2, SQLite, Frozen-Flask, Bootstrap 5, JavaScript, GitHub Pages",
    "platforms": "Any modern browser (desktop and phone)",
    "resources": "Source code (GitHub) | https://github.com/gaurishgarg/portfolio-constructor\n"
                 "Live site (built with it) | https://gaurishgarg.github.io",
    "problem_motivation": '<p>A research portfolio keeps changing: new papers, projects, certificates, conferences, code. Hand-editing HTML '
                          'for every change is slow and error-prone, while hosted site builders are rigid and cost money. I wanted to add an '
                          'entry by filling in a form and have a fast, free, static site come out at the end.</p>',
    "technical_challenge": '<p>Keep the editing experience dynamic while the published site stays fully static (GitHub Pages has no server). '
                            'Every new kind of content also had to be addable without breaking existing data, and different kinds of work '
                            '(HCI case study, systems write-up, learning-design write-up) need different page structures.</p>',
    "objectives": '<ul><li>Edit everything from a browser form, locally.</li><li>Publish as plain static files.</li>'
                  '<li>Add fields and sections without database migrations.</li><li>Look consistent whatever the content.</li></ul>',
    "architecture_image": "constructor_architecture.png",
    "system_overview": '<p>A Flask app is the editor and a live preview. Content lives in SQLite and an uploads folder. '
                        '<b>Frozen-Flask</b> renders every public page to plain HTML in <code>build/</code>, which is pushed to GitHub Pages. '
                        'Visitors never touch Flask or the database.</p>',
    "implementation": '<ul>'
                      '<li><b>Template schema:</b> one <code>schema.py</code> describes the fields of each project / publication template '
                      '(HCI &amp; AR-VR, Tech for AR-VR, Educational Technology). The add form, the edit form and the detail page are all '
                      'generated from it, and extra fields are stored as JSON, so a new field needs no migration.</li>'
                      '<li><b>Publications:</b> paste a DOI and the title, authors and year are filled in from Crossref.</li>'
                      '<li><b>Content types:</b> projects, publications, scholastics, skills, certifications (certificate files are viewed on '
                      'the site itself), conferences, writing, indie projects, and a visual page builder for &ldquo;At a Glance&rdquo; pages.</li>'
                      '<li><b>Code page:</b> repositories are synced from the GitHub API, then hidden, pinned, renamed and categorised by hand; '
                      'a tech-stack bar filters them and READMEs open in a preview on the page.</li>'
                      '<li><b>Safe upgrades:</b> tables are created on start and only ever gain columns, so an existing database and its uploads keep working.</li>'
                      '</ul>',
    "insight1": '<p><b>0 servers</b> needed to host the published site.</p>',
    "insight2": '<p><b>3 templates</b> and one schema drive every project and publication page.</p>',
    "limitations": '<p>The editor is single-user and has no login (it is meant to run on my own computer, never to be hosted). '
                   'Writing and indie-project entries cannot yet be edited in place, and the GitHub sync needs a manual run before each build.</p>',
}
