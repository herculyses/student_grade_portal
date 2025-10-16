import os
import sqlite3, io, csv, chardet, json
from flask import Flask, render_template, request, redirect, session, send_file, jsonify, url_for

# ---------------- CONFIG ----------------
app = Flask(__name__)
# Use environment variable for secret key (required in production)
app.secret_key = os.environ.get('SECRET_KEY', 'supersecretkey')

# Instructor code stored in environment variable
INSTRUCTOR_CODE = os.environ.get('INSTRUCTOR_CODE', '09468216044')

# Grade remarks and colors
GRADE_REMARKS = {
    1.00:'Excellent',1.25:'Excellent',1.50:'Very Good',1.75:'Very Good',
    2.00:'Above Average',2.25:'Above Average',2.50:'Average',2.75:'Average',
    3.00:'Passing',5.00:'Failed','INC':'Incomplete','W':'Withdrawn',
    'D/F':'Dropped with Failure','OD':'Officially Dropped'
}

GRADE_COLORS = {
    'Excellent':'#d4edda','Very Good':'#c3e6cb','Above Average':'#ffeeba',
    'Average':'#fff3cd','Passing':'#d1ecf1','Failed':'#f8d7da',
    'Incomplete':'#f5c6cb','Withdrawn':'#e2e3e5','Dropped with Failure':'#f8d7da',
    'Officially Dropped':'#d6d8d9'
}

# ---------------- DB helpers ----------------
DB_FILE = 'grades.db'

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT,
        student_id TEXT UNIQUE,
        student_name TEXT
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS grades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT,
        student_name TEXT,
        section TEXT,
        subject TEXT,
        midterm_score TEXT,
        midterm_grade TEXT,
        final_score TEXT,
        final_grade TEXT
    )''')
    conn.execute("INSERT OR IGNORE INTO users (username,password,role) VALUES ('admin','admin','instructor')")
    conn.commit()
    conn.close()

init_db()

# ---------------- AUTH ROUTES ----------------
# (Keep all your login, signup, change_password, logout routes here)
# In signup, replace the hardcoded code check:
# if instructor_code != '09468216044':
# → becomes:
# if instructor_code != INSTRUCTOR_CODE:
    error = 'Invalid instructor code'

# ---------------- DASHBOARD / SAVE / FILTER ----------------
# (Keep all dashboard, save_grades, filter_grades, CSV upload, etc.)
# No changes needed here besides environment-secure instructor code in signup

# ---------------- CSV TEMPLATE ----------------
# (Same as your current route)

# ---------------- RUN ----------------
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', '1') == '1'

    # Use Waitress on Windows for production-like local testing
    if os.name == 'nt':  # Windows
        from waitress import serve
        print(f"Running on Windows using Waitress on port {port}...")
        serve(app, host='0.0.0.0', port=port)
    else:
        # For Linux (Render), fallback to Flask dev server if testing; Render uses Gunicorn automatically
        print(f"Running on Linux on port {port}...")
        app.run(host='0.0.0.0', port=port, debug=debug)
