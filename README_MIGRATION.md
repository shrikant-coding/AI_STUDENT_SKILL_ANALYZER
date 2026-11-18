# SkillPath AI — Student Skill Gap Analyzer

A Flask + HTML/CSS student skill analyzer with timed subject tests and an administrator-managed MCQ question bank.

## 1. Run the app on Windows (easy method)

1. Extract the ZIP to a normal folder (do not run it from inside the ZIP).
2. Install Python 3.10 or newer. During installation, enable **Add Python to PATH**.
3. Double-click **`START_APP.bat`**.
4. On the first run, the BAT file creates a virtual environment and installs all packages from `requirements.txt`. This can take a few minutes and requires internet access.
5. It starts the Flask server and opens `http://127.0.0.1:5000` in your browser.
6. Keep the black command window open while using the app. Close it to stop the server.

Every later launch: double-click `START_APP.bat` again. It reuses the virtual environment and checks/installs requirements.

## 2. Student use

- Create an account from **Create Account**, then sign in.
- Open **Skill Assessment Test**.
- Choose a subject card (Python, SQL, HTML, or Machine Learning) to take a timed MCQ test. The score and weak topics are saved in the student's progress.
- Or choose a target career and complete the manual skill-rating assessment to see career readiness, skill gaps, and learning resources.
- **My Progress** shows saved career assessments and MCQ test history.

## 3. Admin Question Bank

Open **Admin Login** from the home page, or visit `http://127.0.0.1:5000/admin/login`.

Default local demo credentials:
- Email: `admin@skillpath.local`
- Password: `Admin@12345`

From **Question Bank**, an admin can:
- View all questions grouped by subject.
- Add a question with four options and its correct answer.
- Edit an existing question.
- Delete a question.
- Add a new subject by entering its name in the Subject field.

Question bank records are stored in `quiz_results.sqlite3`. The built-in questions are inserted automatically on the first launch only. Changes persist across restarts.

**Before sharing outside a classroom demo:** change the default admin password and Flask secret. In `START_APP.bat`, edit the two `set` lines for `SKILLPATH_ADMIN_EMAIL` and `SKILLPATH_ADMIN_PASSWORD`, and set a long random `FLASK_SECRET_KEY`. Give the admin credentials only to the person managing questions. Do not expose Flask's development server directly to the public internet.

## 4. Sharing with another Windows user

Share the complete extracted project folder (or the ZIP) containing `app.py`, `analyzer.py`, `database.py`, `question_bank.py`, `data`, `templates`, `static`, `requirements.txt`, and `START_APP.bat`. The recipient needs Python 3.10+ and internet access for the first package installation. They do not need to install Flask or the other Python packages manually.

The app creates these local SQLite databases automatically beside the project files:
- `skill_analyzer.db` — student accounts and manual assessment history.
- `quiz_results.sqlite3` — editable question bank and MCQ test history.

Keep both database files if you want to preserve student accounts, question-bank edits, and test history. Back them up before moving or replacing the project folder.

## 5. Open from a phone on the same Wi-Fi

Run `ipconfig` on the computer and find its IPv4 address. On a phone connected to the same Wi-Fi, open `http://COMPUTER_IPV4:5000`. Allow Python through Windows Firewall for private networks if prompted. This is for local network demonstrations, not public hosting.

## Project structure

```text
Student_Skill_Gap_Analyzer_Web/
├── app.py
├── analyzer.py
├── database.py
├── question_bank.py
├── requirements.txt
├── START_APP.bat
├── data/
│   ├── career_skills.csv
│   └── learning_resources.csv
├── templates/
│   ├── base.html
│   ├── home.html
│   ├── login.html
│   ├── register.html
│   ├── assessment.html
│   ├── online_test.html
│   ├── quiz.html
│   ├── quiz_result.html
│   ├── progress.html
│   ├── about.html
│   ├── admin_login.html
│   ├── admin_question_bank.html
│   └── admin_edit_question.html
└── static/
    ├── css/style.css
    └── js/main.js
```
