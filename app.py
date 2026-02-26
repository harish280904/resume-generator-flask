from flask import Flask, request, render_template, session, redirect
from flask_mysqldb import MySQL
from flask_bcrypt import Bcrypt
import MySQLdb.cursors
from flask import send_file
import pdfkit
from flask import make_response
from flask import jsonify
app = Flask(__name__)
app.secret_key = "resume_secret_key"

# =======================
# MySQL Configuration
# =======================
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'root1234'
app.config['MYSQL_DB'] = 'resume_db'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

mysql = MySQL(app)
bcrypt = Bcrypt(app)

# =======================
# HOME
# =======================
@app.route("/")
def home():
    return render_template("index.html")

# =======================
# SIGNUP
# =======================
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        full_name = request.form["full_name"]
        email = request.form["email"]
        password = request.form["password"]
        phone = request.form["phone"]

        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
        if cursor.fetchone():
            return render_template("signup.html", error="Email already exists")

        hashed_password = bcrypt.generate_password_hash(password).decode("utf-8")

        cursor.execute("""
            INSERT INTO users (full_name, email, password, phone)
            VALUES (%s, %s, %s, %s)
        """, (full_name, email, hashed_password, phone))

        mysql.connection.commit()
        cursor.close()

        return redirect("/login")

    return render_template("signup.html")

# =======================
# LOGIN
# =======================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cursor.fetchone()
        cursor.close()

        if user and bcrypt.check_password_hash(user["password"], password):
            session["user_id"] = user["user_id"]
            session["user_name"] = user["full_name"]
            session.pop("resume_id", None)
            return redirect("/dashboard")

        return render_template("login.html", error="Invalid credentials")

    return render_template("login.html")
# =======================
# ADMIN LOGIN
# =======================
@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():

    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM admin WHERE email=%s", (email,))
        admin = cursor.fetchone()
        cursor.close()

        if admin and admin["password"] == password:
            session["admin"] = admin["admin_id"]
            return redirect("/admin-dashboard")

        return "Invalid Admin Credentials"

    return render_template("admin_login.html")
# =======================
# ADMIN DASHBOARD
# =======================
@app.route("/admin-dashboard")
def admin_dashboard():

    if "admin" not in session:
        return redirect("/admin-login")

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # ✅ Total Users
    cursor.execute("SELECT COUNT(*) AS total_users FROM users")
    total_users = cursor.fetchone()["total_users"]

    # ✅ Total Resumes
    cursor.execute("SELECT COUNT(*) AS total_resumes FROM resume")
    total_resumes = cursor.fetchone()["total_resumes"]

    # ✅ Fetch resumes with username
    cursor.execute("""
        SELECT resume.resume_id,
               resume.created_at,
               users.full_name AS user_name
        FROM resume
        JOIN users ON resume.user_id = users.user_id
        ORDER BY resume.created_at DESC
    """)

    resumes = cursor.fetchall()

    cursor.close()

    return render_template(
        "admin_dashboard.html",
        total_users=total_users,
        total_resumes=total_resumes,
        resumes=resumes
    )
@app.route("/admin-delete/<int:resume_id>")
def admin_delete(resume_id):

    if "admin" not in session:
        return redirect("/admin-login")

    cursor = mysql.connection.cursor()

    # Delete child tables first
    cursor.execute("DELETE FROM personal_details WHERE resume_id=%s", (resume_id,))
    cursor.execute("DELETE FROM education WHERE resume_id=%s", (resume_id,))
    cursor.execute("DELETE FROM experience WHERE resume_id=%s", (resume_id,))
    cursor.execute("DELETE FROM projects WHERE resume_id=%s", (resume_id,))
    cursor.execute("DELETE FROM skills WHERE resume_id=%s", (resume_id,))

    # Then delete resume
    cursor.execute("DELETE FROM resume WHERE resume_id=%s", (resume_id,))

    mysql.connection.commit()
    cursor.close()

    return redirect("/admin-dashboard")

@app.route("/admin-logout")
def admin_logout():
    session.pop("admin", None)
    return redirect("/admin-login")
# =======================
# DASHBOARD
# =======================
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")
    return render_template("dashboard.html")

# =======================
# CREATE RESUME
# =======================
@app.route("/create-resume")
def create_resume():

    if "user_id" not in session:
        return redirect("/login")

    cursor = mysql.connection.cursor()

    # Create empty resume with default template
    cursor.execute("""
        INSERT INTO resume (user_id, template_selected)
        VALUES (%s, %s)
    """, (session["user_id"], "classic"))

    mysql.connection.commit()
    resume_id = cursor.lastrowid
    cursor.close()

    return redirect(f"/choose_template/{resume_id}")
# =======================
# TEMPLATE SELECTION
# =======================


@app.route("/start-option")
def start_option():
    if "user_id" not in session:
        return redirect("/login")

    session["selected_template"] = request.args.get("template", "classic")
    session.pop("resume_id", None)
    return redirect("/builder/personal")

# =======================
# BUILDER
# =======================
@app.route("/builder/<step>")
def builder(step):

    # ================= SECURITY =================
    if "user_id" not in session:
        return redirect("/login")

    allowed_steps = ["personal", "education", "experience", "projects", "skills", "review"]

    if step not in allowed_steps:
        return redirect("/builder/personal")

    # ================= DEFAULT VALUES =================
    personal = None
    education = []
    experience = []
    projects = []
    skills = []
    template = "classic"

    # ================= IF RESUME EXISTS =================
    if "resume_id" in session:

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        # ✅ Get template from DB (BEST PRACTICE)
        cursor.execute(
            "SELECT template_selected FROM resume WHERE resume_id=%s",
            (session["resume_id"],)
        )
        resume_data = cursor.fetchone()

        if resume_data:
            template = resume_data["template_selected"]
            session["selected_template"] = template  # keep session synced

        # ================= FETCH ALL DATA =================
        cursor.execute(
            "SELECT * FROM personal_details WHERE resume_id=%s",
            (session["resume_id"],)
        )
        personal = cursor.fetchone()

        cursor.execute(
            "SELECT * FROM education WHERE resume_id=%s",
            (session["resume_id"],)
        )
        education = cursor.fetchall()

        cursor.execute(
            "SELECT * FROM experience WHERE resume_id=%s",
            (session["resume_id"],)
        )
        experience = cursor.fetchall()

        cursor.execute(
            "SELECT * FROM projects WHERE resume_id=%s",
            (session["resume_id"],)
        )
        projects = cursor.fetchall()

        cursor.execute(
            "SELECT * FROM skills WHERE resume_id=%s",
            (session["resume_id"],)
        )
        skills = cursor.fetchall()

        cursor.close()

    else:
        # If resume_id not found, create fresh default template session
        template = session.get("selected_template", "classic")

    # ================= RENDER PAGE =================
    return render_template(
        "builder.html",
        step=step,
        personal=personal,
        education=education,
        experience=experience,
        projects=projects,
        skills=skills,
        template=template
    )
# =======================
# SAVE RESUME (CREATE + EDIT)
# =======================
@app.route("/save-resume", methods=["POST"])
def save_resume():

    if "user_id" not in session:
        return redirect("/login")

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # ================= CREATE RESUME FIRST TIME =================
    if "resume_id" not in session:
        cursor.execute("""
            INSERT INTO resume (user_id, template_selected)
            VALUES (%s, %s)
        """, (session["user_id"], "classic"))
        mysql.connection.commit()
        session["resume_id"] = cursor.lastrowid

    resume_id = session["resume_id"]

    # ================= PERSONAL =================
    if request.form.get("full_name"):

        cursor.execute("DELETE FROM personal_details WHERE resume_id=%s", (resume_id,))

        cursor.execute("""
            INSERT INTO personal_details
            (resume_id, full_name, job_title, email, phone, objective)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            resume_id,
            request.form.get("full_name"),
            request.form.get("job_title"),
            request.form.get("email"),
            request.form.get("phone"),
            request.form.get("summary")
        ))

        mysql.connection.commit()
        cursor.close()
        return redirect("/builder/education")

    # ================= EDUCATION =================
    if request.form.get("degree_1"):

        cursor.execute("DELETE FROM education WHERE resume_id=%s", (resume_id,))

        i = 1
        while True:
            degree = request.form.get(f"degree_{i}")
            university = request.form.get(f"university_{i}")
            year = request.form.get(f"year_{i}")
            percentage = request.form.get(f"percentage_{i}")

            if not degree:
                break

            cursor.execute("""
                INSERT INTO education
                (resume_id, level, institution, year_of_passing, percentage)
                VALUES (%s, %s, %s, %s, %s)
            """, (resume_id, degree, university, year, percentage))

            i += 1

        mysql.connection.commit()
        cursor.close()
        return redirect("/builder/experience")

    # ================= EXPERIENCE =================
    if request.form.get("job_title_1"):

        cursor.execute("DELETE FROM experience WHERE resume_id=%s", (resume_id,))

        i = 1
        while True:
            job_title = request.form.get(f"job_title_{i}")
            company = request.form.get(f"company_{i}")
            duration = request.form.get(f"duration_{i}")
            description = request.form.get(f"description_{i}")

            if not job_title:
                break

            cursor.execute("""
                INSERT INTO experience
                (resume_id, job_title, company, duration, description)
                VALUES (%s, %s, %s, %s, %s)
            """, (resume_id, job_title, company, duration, description))

            i += 1

        mysql.connection.commit()
        cursor.close()
        return redirect("/builder/projects")

    # ================= PROJECTS =================
    if request.form.get("project_title_1"):

        cursor.execute("DELETE FROM projects WHERE resume_id=%s", (resume_id,))

        i = 1
        while True:
            title = request.form.get(f"project_title_{i}")
            tech = request.form.get(f"technologies_{i}")
            github = request.form.get(f"github_{i}")
            description = request.form.get(f"project_description_{i}")

            if not title:
                break

            cursor.execute("""
                INSERT INTO projects
                (resume_id, project_title, technologies_used, github_link, description)
                VALUES (%s, %s, %s, %s, %s)
            """, (resume_id, title, tech, github, description))

            i += 1

        mysql.connection.commit()
        cursor.close()
        return redirect("/builder/skills")

    # ================= SKILLS =================
    if request.form.get("skills"):
        cursor.execute("DELETE FROM skills WHERE resume_id=%s", (resume_id,))

        skills = request.form.get("skills").split()
        for skill in skills:
            cursor.execute("""
                INSERT INTO skills (resume_id, skill_name)
                VALUES (%s, %s)
            """, (resume_id, skill.strip()))

        mysql.connection.commit()
        cursor.close()
        return redirect("/builder/review")

    cursor.close()
    return redirect(f"/review/{resume_id}")
@app.route("/generate-summary", methods=["POST"])
def generate_summary():

    role = request.form.get("role")
    experience = request.form.get("experience")
    skills = request.form.get("skills")

    if not role:
        return jsonify({"summary": "Please enter job title first."})

    summary = f"""
    Results-driven {role} with {experience}.
    Skilled in {skills}.
    Strong ability to design, develop and optimize scalable applications.
    Committed to delivering high-quality solutions and continuous improvement.
    """

    return jsonify({"summary": summary.strip()})
# =======================
# MY RESUMES PAGE
# =======================
@app.route("/my-resumes")
def my_resumes():

    if "user_id" not in session:
        return redirect("/login")

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cursor.execute("""
        SELECT resume_id, created_at
        FROM resume
        WHERE user_id=%s
        ORDER BY resume_id DESC
    """, (session["user_id"],))

    resumes = cursor.fetchall()
    cursor.close()

    return render_template("my_resumes.html", resumes=resumes)
# =======================
# CREATE RESUME
# =======================
# =======================
# CHOOSE TEMPLATE
# =======================

# =======================
# EDIT RESUME
# =======================
@app.route("/edit/<int:resume_id>")
def edit_resume(resume_id):

    if "user_id" not in session:
        return redirect("/login")

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Security check
    cursor.execute(
        "SELECT * FROM resume WHERE resume_id=%s AND user_id=%s",
        (resume_id, session["user_id"])
    )
    resume = cursor.fetchone()

    if not resume:
        cursor.close()
        return "Unauthorized Access"

    # ✅ Store resume id
    session["resume_id"] = resume_id


    cursor.close()

    return redirect("/builder/personal")
# =======================
# DELETE RESUME
# =======================
@app.route("/delete-resume/<int:resume_id>")
def delete_resume(resume_id):

    if "user_id" not in session:
        return redirect("/login")

    cursor = mysql.connection.cursor()

    # Security check
    cursor.execute(
        "SELECT * FROM resume WHERE resume_id=%s AND user_id=%s",
        (resume_id, session["user_id"])
    )
    resume = cursor.fetchone()

    if resume:

        # Delete child tables first (IMPORTANT)
        cursor.execute("DELETE FROM personal_details WHERE resume_id=%s", (resume_id,))
        cursor.execute("DELETE FROM education WHERE resume_id=%s", (resume_id,))
        cursor.execute("DELETE FROM experience WHERE resume_id=%s", (resume_id,))
        cursor.execute("DELETE FROM projects WHERE resume_id=%s", (resume_id,))
        cursor.execute("DELETE FROM skills WHERE resume_id=%s", (resume_id,))

        # Then delete main resume
        cursor.execute("DELETE FROM resume WHERE resume_id=%s", (resume_id,))

        mysql.connection.commit()

    cursor.close()

    return redirect("/my-resumes")
 # =======================
# REVIEW PAGE
# =======================
@app.route("/review/<int:resume_id>")
def review_resume(resume_id):

    # 1️⃣ Check login
    if "user_id" not in session:
        return redirect("/login")

    # 2️⃣ Save resume id in session
    session["resume_id"] = resume_id

    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        # 3️⃣ Fetch resume data
        cursor.execute("SELECT * FROM personal_details WHERE resume_id=%s", (resume_id,))
        personal = cursor.fetchone()

        cursor.execute("SELECT * FROM education WHERE resume_id=%s", (resume_id,))
        education = cursor.fetchall()

        cursor.execute("SELECT * FROM experience WHERE resume_id=%s", (resume_id,))
        experience = cursor.fetchall()

        cursor.execute("SELECT * FROM projects WHERE resume_id=%s", (resume_id,))
        projects = cursor.fetchall()

        cursor.execute("SELECT * FROM skills WHERE resume_id=%s", (resume_id,))
        skills = cursor.fetchall()

        cursor.execute("SELECT template_selected FROM resume WHERE resume_id=%s", (resume_id,))
        template_data = cursor.fetchone()

        cursor.close()

    except Exception as e:
        print("ERROR:", e)
        return "Something went wrong while loading resume."

    # 4️⃣ Safe template handling
    template_name = "classic"

    if template_data and template_data.get("template_selected"):
        template_name = template_data["template_selected"]

    print("Selected Template:", template_name)

    # 5️⃣ Template mapping
    template_map = {
        "classic": "preview_classic.html",
        "modern": "preview_modern.html",
        "professional": "preview_professional.html",
        "creative": "preview_creative.html",
        "minimal": "preview_minimal.html",
        "ats": "preview_ats.html"
    }

    template_file = template_map.get(template_name, "preview_classic.html")

    # 6️⃣ Render correct preview template
    return render_template(
        template_file,
        personal=personal or {},
        education=education or [],
        experience=experience or [],
        projects=projects or [],
        skills=skills or []
    )
# =======================
# CHOOSE TEMPLATE
# =======================
@app.route("/choose_template/<int:resume_id>")
def choose_template(resume_id):

    if "user_id" not in session:
        return redirect("/login")

    return render_template("choose_template.html",
                           resume_id=resume_id)
# =======================
# SELECT TEMPLATE
# =======================
# =======================
# SELECT TEMPLATE
# =======================
@app.route("/select-template/<template>/<int:resume_id>")
def select_template(template, resume_id):

    # ================= SECURITY CHECK =================
    if "user_id" not in session:
        return redirect("/login")

    # ================= VALID TEMPLATE CHECK =================
    allowed_templates = ["classic", "modern", "professional", "creative", "minimal", "ats"]

    if template not in allowed_templates:
        return redirect("/dashboard")

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # ================= OWNERSHIP CHECK =================
    cursor.execute(
        "SELECT * FROM resume WHERE resume_id=%s AND user_id=%s",
        (resume_id, session["user_id"])
    )
    resume = cursor.fetchone()

    if not resume:
        cursor.close()
        return "Unauthorized Access", 403

    # ================= UPDATE TEMPLATE =================
    cursor.execute(
        "UPDATE resume SET template_selected=%s WHERE resume_id=%s",
        (template, resume_id)
    )

    mysql.connection.commit()
    cursor.close()

    # ================= SESSION SYNC =================
    session["resume_id"] = resume_id
    session["selected_template"] = template

    # ================= REDIRECT TO BUILDER =================
    return redirect("/builder/personal")
@app.route("/analyze-resume", methods=["POST"])
def analyze_resume():

    data = request.get_json()
    resume_id = data.get("resume_id")

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cursor.execute("SELECT * FROM personal_details WHERE resume_id=%s", (resume_id,))
    personal = cursor.fetchone()

    cursor.execute("SELECT * FROM skills WHERE resume_id=%s", (resume_id,))
    skills = cursor.fetchall()

    cursor.close()

    score = 50
    feedback = []

    if personal and personal.get("objective"):
        score += 20
    else:
        feedback.append("Add professional summary.")

    if skills and len(skills) >= 3:
        score += 20
    else:
        feedback.append("Add more skills.")

    if score > 100:
        score = 100

    return jsonify({
        "score": score,
        "feedback": feedback
    })
# ======================
# DOWNLOAD PDF
# =======================
@app.route("/download/<int:resume_id>")
def download_resume(resume_id):

    if "user_id" not in session:
        return redirect("/login")

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Fetch Data
    cursor.execute("SELECT * FROM personal_details WHERE resume_id=%s", (resume_id,))
    personal = cursor.fetchone()

    cursor.execute("SELECT * FROM education WHERE resume_id=%s", (resume_id,))
    education = cursor.fetchall()

    cursor.execute("SELECT * FROM experience WHERE resume_id=%s", (resume_id,))
    experience = cursor.fetchall()

    cursor.execute("SELECT * FROM projects WHERE resume_id=%s", (resume_id,))
    projects = cursor.fetchall()

    cursor.execute("SELECT * FROM skills WHERE resume_id=%s", (resume_id,))
    skills = cursor.fetchall()

    cursor.execute("SELECT template_selected FROM resume WHERE resume_id=%s", (resume_id,))
    template_data = cursor.fetchone()

    cursor.close()

    if not template_data:
        return "Template not found", 404

    # Template Mapping
    template_map = {
        "classic": "preview_classic.html",
        "modern": "preview_modern.html",
        "professional": "preview_professional.html",
        "creative": "preview_creative.html",
        "minimal": "preview_minimal.html",
        "ats": "preview_ats.html"
    }

    template_name = template_data.get("template_selected", "classic")
    template_file = template_map.get(template_name, "preview_classic.html")

    # Render Template (IMPORTANT: pdf_mode=True hides button)
    rendered_html = render_template(
        template_file,
        personal=personal,
        education=education,
        experience=experience,
        projects=projects,
        skills=skills,
        pdf_mode=True   # 🔥 THIS FIXES BUTTON ISSUE
    )

    # wkhtmltopdf Path
    config = pdfkit.configuration(
        wkhtmltopdf=r"C:\Program Files\wkhtmltox\bin\wkhtmltopdf.exe"
    )

    options = {
        "enable-local-file-access": None,
        "quiet": ""
    }

    # Generate PDF
    pdf = pdfkit.from_string(
        rendered_html,
        False,
        configuration=config,
        options=options
    )

    response = make_response(pdf)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f"attachment; filename=resume_{resume_id}.pdf"

    return response
# =======================
# LOGOUT
# =======================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# =======================
# RUN
# =======================
if __name__ == "__main__":
    app.run(debug=True)
    