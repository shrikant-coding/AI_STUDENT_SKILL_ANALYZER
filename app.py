from pathlib import Path
import os
import json
import sqlite3
import uuid
import hmac
import pandas as pd
import plotly.express as px
from flask import Flask, render_template, request, redirect, url_for, session, flash, make_response
from analyzer import analyze_skills, load_career_data, profile_similarity, recommend_resources
from database import authenticate, create_account, get_history, init_db, save_assessment
from question_bank import QUESTION_BANK

BASE = Path(__file__).resolve().parent
CAREER_PATH = BASE / "data" / "career_skills.csv"
RESOURCE_PATH = BASE / "data" / "learning_resources.csv"
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-this-secret-before-deployment")
init_db()
career_df = load_career_data(CAREER_PATH)
resources_df = pd.read_csv(RESOURCE_PATH)
all_skills = sorted(career_df["skill"].unique())


DATA_DIR = Path(os.environ.get("DATA_DIR", str(BASE)))
DATA_DIR.mkdir(parents=True, exist_ok=True)

QUIZ_DB = DATA_DIR / "quiz_results.sqlite3"

def init_quiz_db():
    with sqlite3.connect(QUIZ_DB) as con:
        con.execute("""CREATE TABLE IF NOT EXISTS quiz_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT, student_email TEXT NOT NULL,
            category TEXT NOT NULL, score INTEGER NOT NULL, total INTEGER NOT NULL,
            percentage REAL NOT NULL, weak_topics TEXT NOT NULL,
            answers_json TEXT NOT NULL, taken_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")

def init_question_bank():
    """Create persistent editable question bank and seed it once from defaults."""
    with sqlite3.connect(QUIZ_DB) as con:
        con.execute("""CREATE TABLE IF NOT EXISTS questions (
            id TEXT PRIMARY KEY, category TEXT NOT NULL, topic TEXT NOT NULL,
            question TEXT NOT NULL, options_json TEXT NOT NULL, answer TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        # Seed each built-in question independently. This also repairs a partially
        # initialized database instead of leaving students with an empty test page.
        for category, items in QUESTION_BANK.items():
            for q in items:
                con.execute(
                    "INSERT OR IGNORE INTO questions(id,category,topic,question,options_json,answer) VALUES(?,?,?,?,?,?)",
                    (q["id"], category, q["topic"], q["question"], json.dumps(q["options"]), q["answer"])
                )


def get_question_bank():
    with sqlite3.connect(QUIZ_DB) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute("SELECT * FROM questions ORDER BY category, id").fetchall()
    bank = {}
    for row in rows:
        q = dict(row)
        q["options"] = json.loads(q.pop("options_json"))
        bank.setdefault(q["category"], []).append(q)
    return bank


def get_question(question_id):
    with sqlite3.connect(QUIZ_DB) as con:
        con.row_factory = sqlite3.Row
        row = con.execute("SELECT * FROM questions WHERE id=?", (question_id,)).fetchone()
    if not row:
        return None
    item = dict(row)
    item["options"] = json.loads(item.pop("options_json"))
    return item


init_quiz_db()
init_question_bank()

# Admin credentials can be changed through environment variables before sharing/deployment.
ADMIN_EMAIL = os.environ.get("SKILLPATH_ADMIN_EMAIL", "admin@skillpath.local").strip().lower()
ADMIN_PASSWORD = os.environ.get("SKILLPATH_ADMIN_PASSWORD", "Admin@12345")


def admin_required():
    if not session.get("is_admin"):
        flash("Please sign in with the administrator account.", "error")
        return False
    return True

def save_quiz_result(email, category, score, total, weak_topics, answers):
    import json
    with sqlite3.connect(QUIZ_DB) as con:
        cur = con.execute(
            "INSERT INTO quiz_results(student_email,category,score,total,percentage,weak_topics,answers_json) VALUES(?,?,?,?,?,?,?)",
            (email, category, score, total, round(score / total * 100, 1),
             ", ".join(weak_topics), json.dumps(answers))
        )
        return cur.lastrowid

def get_quiz_history(email):
    with sqlite3.connect(QUIZ_DB) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute("SELECT id, category, score, total, percentage, weak_topics, taken_at FROM quiz_results WHERE student_email=? ORDER BY id DESC", (email,)).fetchall()
        return [dict(row) for row in rows]

def get_quiz_result(result_id, email):
    with sqlite3.connect(QUIZ_DB) as con:
        con.row_factory = sqlite3.Row
        row = con.execute("SELECT * FROM quiz_results WHERE id=? AND student_email=?", (result_id, email)).fetchone()
        return dict(row) if row else None

def valid_email(email):
    parts = email.strip().rsplit("@", 1)
    return len(parts) == 2 and bool(parts[0]) and "." in parts[1]

def chart_html(fig):
    return fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False, "responsive": True})

@app.context_processor
def globals_for_templates():
    return {"student": session.get("student"), "is_admin": session.get("is_admin", False)}

@app.route("/")
def index():
    return redirect(url_for("home"))

@app.route("/home")
def home():
    return render_template("home.html", career_count=career_df["career"].nunique(),
        skill_count=len(all_skills), resource_count=len(resources_df),
        careers=sorted(career_df["career"].unique()))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email, password = request.form.get("email", "").strip(), request.form.get("password", "")
        if not valid_email(email) or not password:
            flash("Enter a valid email address and password.", "error")
        else:
            user = authenticate(email, password)
            if user:
                session["student"] = user
                session.pop("last_result", None)
                return redirect(url_for("home"))
            flash("Email or password is incorrect.", "error")
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        if not name: flash("Please enter your name.", "error")
        elif not valid_email(email): flash("Please enter a valid email address.", "error")
        elif len(password) < 8: flash("Choose a password with at least 8 characters.", "error")
        elif password != confirm: flash("The passwords do not match.", "error")
        else:
            try:
                sid = create_account(name, email, password)
                session["student"] = {"id": sid, "name": name, "email": email.lower().strip()}
                flash("Account created. You are now logged in.", "success")
                return redirect(url_for("home"))
            except ValueError as exc:
                flash(str(exc), "error")
    return render_template("register.html")

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if hmac.compare_digest(email, ADMIN_EMAIL) and hmac.compare_digest(password, ADMIN_PASSWORD):
            session.clear()
            session["is_admin"] = True
            session["admin_email"] = email
            flash("Administrator access granted.", "success")
            return redirect(url_for("admin_question_bank"))
        flash("Invalid administrator email or password.", "error")
    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    session.pop("admin_email", None)
    flash("Administrator signed out.", "success")
    return redirect(url_for("home"))

@app.route("/admin/question-bank")
def admin_question_bank():
    if not admin_required():
        return redirect(url_for("admin_login"))
    bank = get_question_bank()
    return render_template("admin_question_bank.html", bank=bank, total=sum(len(v) for v in bank.values()))

@app.route("/admin/question-bank/save", methods=["POST"])
def admin_save_question():
    if not admin_required():
        return redirect(url_for("admin_login"))
    category = request.form.get("category", "").strip()
    topic = request.form.get("topic", "").strip()
    question = request.form.get("question", "").strip()
    options = {key: request.form.get(f"option_{key}", "").strip() for key in "ABCD"}
    answer = request.form.get("answer", "").strip().upper()
    question_id = request.form.get("question_id", "").strip() or "q_" + uuid.uuid4().hex[:12]
    if not category or not topic or not question or not all(options.values()) or answer not in options:
        flash("Complete the subject, topic, question, all four options, and correct answer.", "error")
        return redirect(url_for("admin_question_bank"))
    with sqlite3.connect(QUIZ_DB) as con:
        con.execute("""INSERT INTO questions(id,category,topic,question,options_json,answer)
            VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET category=excluded.category,
            topic=excluded.topic, question=excluded.question, options_json=excluded.options_json,
            answer=excluded.answer""",
            (question_id, category, topic, question, json.dumps(options), answer))
    flash("Question saved to the question bank.", "success")
    return redirect(url_for("admin_question_bank"))

@app.route("/admin/question-bank/edit/<question_id>")
def admin_edit_question(question_id):
    if not admin_required():
        return redirect(url_for("admin_login"))
    q = get_question(question_id)
    if not q:
        flash("Question not found.", "error")
        return redirect(url_for("admin_question_bank"))
    return render_template("admin_edit_question.html", q=q)

@app.route("/admin/question-bank/delete/<question_id>", methods=["POST"])
def admin_delete_question(question_id):
    if not admin_required():
        return redirect(url_for("admin_login"))
    with sqlite3.connect(QUIZ_DB) as con:
        con.execute("DELETE FROM questions WHERE id=?", (question_id,))
    flash("Question deleted.", "success")
    return redirect(url_for("admin_question_bank"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/assessment", methods=["GET", "POST"])
def assessment():
    user = session.get("student")
    if not user:
        flash("Please log in to take the skill assessment.", "error")
        return redirect(url_for("login"))
    result = session.get("last_result")
    if result and result.get("student_id") != user.get("id"):
        result = None

    # Keep submitted slider values on validation errors and after a successful analysis.
    skill_values = {skill: 30 for skill in all_skills}
    selected_career = ""
    if request.method == "POST":
        selected_career = request.form.get("career", "").strip()
        try:
            skill_values = {
                skill: max(0, min(100, int(request.form.get(f"skill_{i}", 30))))
                for i, skill in enumerate(all_skills)
            }
        except (TypeError, ValueError):
            flash("Please enter valid skill ratings.", "error")
        else:
            if selected_career not in set(career_df["career"].unique()):
                flash("Please choose a target career from the list before analyzing.", "error")
            else:
                readiness, gaps = analyze_skills(selected_career, skill_values, career_df)
                similarity = profile_similarity(selected_career, skill_values, career_df)
                roadmap = recommend_resources(gaps, resources_df)
                aid = save_assessment(user["name"], user["email"], selected_career, readiness, similarity, gaps)
                top = [{"Career": selected_career, "Profile match": f"{similarity:.1f}%"}]
                result = {"student_id": user["id"], "assessment_id": aid, "career": selected_career,
                    "ranking": top, "readiness": float(readiness),
                    "similarity": float(similarity), "gap_rows": gaps.to_dict("records"),
                    "roadmap_rows": roadmap.to_dict("records")}
                session["last_result"] = result

    result_chart = None
    if result:
        chart_df = pd.DataFrame(result["gap_rows"]).sort_values("required_level", ascending=True)
        fig = px.bar(chart_df, x="skill", y=["student_level", "required_level"], barmode="group",
                     title="Your skills vs recommended career requirements",
                     labels={"value":"Skill level (0–100)", "variable":"Measure"})
        fig.update_yaxes(range=[0, 100])
        result_chart = chart_html(fig)
    bank = get_question_bank()
    quiz_categories = [{"name": name, "count": len(items), "minutes": max(5, len(items))}
                       for name, items in bank.items() if items]
    return render_template("assessment.html", skills=all_skills,
        careers=sorted(career_df["career"].unique()), result=result,
        result_chart=result_chart, quiz_categories=quiz_categories,
        skill_values=skill_values, selected_career=selected_career)

@app.route("/online-test")
def online_test():
    user = session.get("student")
    if not user:
        flash("Please log in to take an online test.", "error")
        return redirect(url_for("login"))
    bank = get_question_bank()
    categories = [{"name": name, "count": len(items), "minutes": max(5, len(items))} for name, items in bank.items()]
    return render_template("online_test.html", categories=categories)

@app.route("/quiz/<category>", methods=["GET"])
def take_quiz(category):
    user = session.get("student")
    if not user:
        flash("Please log in to take an online test.", "error")
        return redirect(url_for("login"))
    questions = get_question_bank().get(category)
    if not questions:
        flash("No questions are available for this subject yet. Please contact the administrator.", "error")
        return redirect(url_for("assessment"))
    safe_questions = [{"id": q["id"], "topic": q["topic"], "question": q["question"], "options": q["options"]} for q in questions]
    return render_template("quiz.html", category=category, questions=safe_questions, minutes=max(5, len(questions)))

@app.route("/quiz/submit", methods=["POST"])
def submit_quiz():
    user = session.get("student")
    if not user:
        flash("Please log in to submit a test.", "error")
        return redirect(url_for("login"))
    category = request.form.get("category", "")
    questions = get_question_bank().get(category)
    if not questions:
        flash("Invalid test category.", "error")
        return redirect(url_for("online_test"))
    score, answers, wrong_topics = 0, [], []
    for q in questions:
        selected = request.form.get(f"q_{q['id']}", "")
        correct = selected == q["answer"]
        score += int(correct)
        if not correct:
            wrong_topics.append(q["topic"])
        answers.append({"question": q["question"], "selected": q["options"].get(selected, "Not answered"),
                        "correct_answer": q["options"][q["answer"]], "correct": correct, "topic": q["topic"]})
    weak_topics = sorted(set(wrong_topics))
    rid = save_quiz_result(user["email"], category, score, len(questions), weak_topics, answers)
    return redirect(url_for("quiz_result", result_id=rid))

@app.route("/quiz/result/<int:result_id>")
def quiz_result(result_id):
    user = session.get("student")
    if not user:
        return redirect(url_for("login"))
    result = get_quiz_result(result_id, user["email"])
    if not result:
        flash("Test result not found.", "error")
        return redirect(url_for("online_test"))
    import json
    result["answers"] = json.loads(result["answers_json"])
    result["weak_topics_list"] = [x for x in result["weak_topics"].split(", ") if x]
    return render_template("quiz_result.html", result=result)

@app.route("/progress")
def progress():
    user = session.get("student")
    if not user:
        flash("Please log in to view your assessment history.", "error")
        return redirect(url_for("login"))
    history = [dict(row) for row in get_history(user["email"])]
    quiz_history = get_quiz_history(user["email"])
    chart = None
    if len(history) > 1:
        df = pd.DataFrame(history).sort_values("assessed_at")
        chart = chart_html(px.line(df, x="assessed_at", y="readiness", color="career",
                                   markers=True, title="Career readiness over time"))
    return render_template("progress.html", history=history, chart=chart, quiz_history=quiz_history)

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/download-report")
def download_report():
    result, user = session.get("last_result"), session.get("student")
    if not result or not user or result.get("student_id") != user.get("id"):
        flash("Complete an assessment before downloading a report.", "error")
        return redirect(url_for("assessment"))
    response = make_response(pd.DataFrame(result["gap_rows"]).to_csv(index=False).encode("utf-8"))
    response.headers["Content-Disposition"] = "attachment; filename=skill_gap_report.csv"
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    return response

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
