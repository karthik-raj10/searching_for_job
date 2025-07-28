from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
import os
import json
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from PyPDF2 import PdfReader

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

USERS_FILE = 'users.json'
JOBS_FILE = 'jobs.json'
APPLICATIONS_FILE = 'applications.json'

# Ensure upload folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Helper functions
def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, 'r') as f:
        return json.load(f)

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f)

def load_jobs():
    if not os.path.exists(JOBS_FILE):
        return []
    with open(JOBS_FILE, 'r') as f:
        lines = f.readlines()
        jobs = []
        for i, line in enumerate(lines):
            job = json.loads(line)
            job['id'] = i
            jobs.append(job)
        return jobs

def save_job(job_data):
    with open(JOBS_FILE, 'a') as f:
        f.write(json.dumps(job_data) + "\n")

def load_applications():
    if not os.path.exists(APPLICATIONS_FILE):
        return []
    with open(APPLICATIONS_FILE, 'r') as f:
        return [json.loads(line) for line in f.readlines()]

def save_application(application):
    with open(APPLICATIONS_FILE, 'a') as f:
        f.write(json.dumps(application) + "\n")

def analyze_resume(filepath, keywords):
    reader = PdfReader(filepath)
    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text.lower()

    total_keywords = len(keywords)
    matched_keywords = sum(1 for kw in keywords if kw.lower() in text)

    score = int((matched_keywords / total_keywords) * 100) if total_keywords > 0 else 0
    mistakes = []

    if score < 50:
        mistakes.append("Resume does not contain many relevant keywords.")
    if not text.strip():
        mistakes.append("Resume content is empty or unreadable.")

    return score, mistakes

# Routes

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/signup/<role>', methods=['GET', 'POST'])
def signup(role):
    if role not in ['hr', 'applicant']:
        return "Invalid role", 404

    if request.method == 'POST':
        email = request.form.get('email')
        username = request.form.get('username')
        password = request.form.get('password')

        users = load_users()
        if username in users:
            flash('Username already exists.', 'danger')
            return render_template('signup.html', role=role)

        users[username] = {
            'email': email,
            'password': generate_password_hash(password),
            'role': role
        }
        save_users(users)
        flash('Signup successful! Please login.', 'success')
        return redirect(url_for('login', role=role))

    return render_template('signup.html', role=role)

@app.route('/login/<role>', methods=['GET', 'POST'])
def login(role):
    if role not in ['hr', 'applicant']:
        return "Invalid role", 404

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        users = load_users()
        user = users.get(username)

        if user and user['role'] == role and check_password_hash(user['password'], password):
            session['user'] = username
            session['role'] = role
            flash('Login successful!', 'success')
            return redirect(url_for('hr_dashboard' if role == 'hr' else 'applicant_dashboard'))

        flash('Invalid credentials.', 'danger')

    return render_template('login.html', role=role)

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('home'))

@app.route('/hr/dashboard')
def hr_dashboard():
    if session.get('role') != 'hr':
        flash('Access denied.', 'danger')
        return redirect(url_for('login', role='hr'))

    jobs = load_jobs()
    return render_template('hr_dashboard.html', jobs=jobs)

@app.route('/hr/post_job', methods=['GET', 'POST'])
def post_job():
    if session.get('role') != 'hr':
        flash('Access denied.', 'danger')
        return redirect(url_for('login', role='hr'))

    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        keywords = [kw.strip() for kw in request.form.get('keywords', '').split(',') if kw.strip()]
        save_job({'title': title, 'description': description, 'keywords': keywords})
        flash('Job posted successfully.', 'success')
        return redirect(url_for('hr_dashboard'))

    return render_template('post_job.html')

@app.route('/hr/delete_job/<int:job_id>', methods=['POST'])
def delete_job(job_id):
    if session.get('role') != 'hr':
        flash('Access denied.', 'danger')
        return redirect(url_for('login', role='hr'))

    jobs = load_jobs()
    if 0 <= job_id < len(jobs):
        jobs.pop(job_id)
        with open(JOBS_FILE, 'w') as f:
            for job in jobs:
                f.write(json.dumps(job) + "\n")
        flash('Job deleted.', 'success')

    return redirect(url_for('hr_dashboard'))

@app.route('/hr/job/<int:job_id>/applicants')
def view_applicants(job_id):
    if session.get('role') != 'hr':
        flash('Access denied.', 'danger')
        return redirect(url_for('login', role='hr'))

    jobs = load_jobs()
    if not (0 <= job_id < len(jobs)):
        return "Invalid job ID", 404

    all_apps = load_applications()
    job_apps = [a for a in all_apps if a['job_id'] == job_id]

    return render_template('view_applicants.html', applicants=job_apps, job=jobs[job_id])

@app.route('/applicant/dashboard')
def applicant_dashboard():
    if session.get('role') != 'applicant':
        flash('Access denied.', 'danger')
        return redirect(url_for('login', role='applicant'))

    jobs = load_jobs()
    return render_template('applicant_dashboard.html', jobs=jobs)

@app.route('/applicant/apply_job/<int:job_id>', methods=['GET', 'POST'])
def apply_job(job_id):
    if session.get('role') != 'applicant':
        flash('Access denied.', 'danger')
        return redirect(url_for('login', role='applicant'))

    jobs = load_jobs()
    if not (0 <= job_id < len(jobs)):
        return "Invalid job ID", 404

    job = jobs[job_id]
    ats_score = None
    mistakes = []

    if request.method == 'POST':
        full_name = request.form.get('full_name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        f = request.files.get('resume')

        if not f or not f.filename.lower().endswith('.pdf'):
            flash('Please upload a valid PDF file.', 'danger')
            return render_template('apply_job.html', job=job)

        filename = secure_filename(f.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        f.save(filepath)

        ats_score, mistakes = analyze_resume(filepath, job['keywords'])

        save_application({
            'job_id': job_id,
            'applicant': session['user'],
            'full_name': full_name,
            'email': email,
            'phone': phone,
            'resume_filename': filename,
            'ats_score': ats_score,
            'mistakes': mistakes
        })

        flash('Application submitted!', 'success')
        return redirect(url_for('applicant_dashboard'))

    return render_template('apply_job.html', job=job)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=True)
