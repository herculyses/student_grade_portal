# app.py -- production-ready-ish version (improved from user's original)
import os
import io
import csv
import sqlite3
import chardet
from flask import (
    Flask, render_template, request, redirect, session,
    send_file, jsonify, url_for, flash
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# Basic config
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, os.environ.get('DB_NAME', 'grades.db'))

app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'please-change-me')
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5 MB upload limit
ALLOWED_EXTENSIONS = {'csv'}
INSTRUCTOR_CODE = os.environ.get('INSTRUCTOR_CODE', '09468216044')

# ---------- Grade config ----------
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
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
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
    # Create a default instructor account if not exists (admin/admin) - hashed
    cur = conn.execute("SELECT * FROM users WHERE username = ?", ('admin',))
    if not cur.fetchone():
        conn.execute(
            'INSERT INTO users (username,password,role) VALUES (?,?,?)',
            ('admin', generate_password_hash('admin'), 'instructor')
        )
    conn.commit()
    conn.close()

init_db()

# ---------------- util ----------------
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.',1)[1].lower() in ALLOWED_EXTENSIONS

# ---------------- AUTH ROUTES ----------------
@app.route('/', methods=['GET','POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        password = request.form.get('password','').strip()
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
        conn.close()
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['role'] = user['role']
            if user['role'] == 'student':
                session['student_id'] = user['student_id']
            return redirect(url_for('dashboard'))
        else:
            error = 'Invalid username or password'
    return render_template('login.html', error=error)

@app.route('/signup', methods=['GET','POST'])
def signup():
    error = None
    message = None
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        password = request.form.get('password','').strip()
        role = request.form.get('role','student')

        if not username or not password:
            error = 'Username and password required'
            return render_template('signup.html', error=error, message=None)

        conn = get_db_connection()
        try:
            if role == 'instructor':
                instructor_code = request.form.get('instructor_code','').strip()
                if instructor_code != INSTRUCTOR_CODE:
                    error = 'Invalid instructor code'
                    conn.close()
                    return render_template('signup.html', error=error, message=None)
                student_id = None
                student_name = None
            else:
                student_id = request.form.get('student_id','').strip()
                student_name = request.form.get('student_name','').strip()
                if not student_id or not student_name:
                    conn.close()
                    error = 'Student ID and Name are required for student registration'
                    return render_template('signup.html', error=error, message=None)

            hashed = generate_password_hash(password)
            conn.execute(
                'INSERT INTO users (username,password,role,student_id,student_name) VALUES (?,?,?,?,?)',
                (username, hashed, role, student_id, student_name)
            )
            conn.commit()

            if role == 'student':
                conn.execute('INSERT INTO grades (student_id, student_name, subject, midterm_score, midterm_grade, final_score, final_grade, section) VALUES (?,?,?,?,?,?,?,?)',
                             (student_id, student_name, '', '', '', '', '', ''))
                conn.commit()

            message = 'Account created successfully!'
        except sqlite3.IntegrityError as e:
            msg = str(e).lower()
            if 'username' in msg:
                error = 'Username already exists'
            elif 'student_id' in msg:
                error = 'Student ID already exists'
            else:
                error = 'Database error. Please try again.'
        finally:
            conn.close()

    return render_template('signup.html', error=error, message=message)

@app.route('/change_password', methods=['GET','POST'])
def change_password():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    message = None
    if request.method == 'POST':
        current = request.form.get('current_password','').strip()
        new_pw = request.form.get('new_password','').strip()
        confirm = request.form.get('confirm_password','').strip()
        if new_pw != confirm:
            message = 'New password and confirmation do not match'
        else:
            conn = get_db_connection()
            user = conn.execute('SELECT * FROM users WHERE id=?', (session['user_id'],)).fetchone()
            if user and check_password_hash(user['password'], current):
                conn.execute('UPDATE users SET password=? WHERE id=?', (generate_password_hash(new_pw), session['user_id']))
                conn.commit()
                message = 'Password changed successfully'
            else:
                message = 'Current password is incorrect'
            conn.close()
    return render_template('change_password.html', message=message)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ---------------- SAVE GRADES ----------------
@app.route('/save_grades', methods=['POST'])
def save_grades():
    if 'role' not in session or session['role'] != 'instructor':
        return jsonify({'status':'error','message':'Unauthorized'}), 403
    data = request.get_json()
    if not isinstance(data, list):
        return jsonify({'status':'error','message':'Invalid payload'}), 400
    conn = get_db_connection()
    for g in data:
        conn.execute('UPDATE grades SET student_id=?, student_name=?, section=?, subject=?, midterm_score=?, midterm_grade=?, final_score=?, final_grade=? WHERE id=?',
                     (g.get('student_id',''), g.get('student_name',''), g.get('section',''), g.get('subject',''),
                      g.get('midterm_score',''), g.get('midterm_grade',''), g.get('final_score',''), g.get('final_grade',''), g.get('id')))
    conn.commit()
    conn.close()

    updated = []
    for g in data:
        fg = (g.get('final_grade') or '').upper()
        try:
            remark = GRADE_REMARKS.get(float(fg) if fg.replace('.','',1).isdigit() else fg,'')
        except:
            remark = ''
        color = GRADE_COLORS.get(remark,'#fff')
        updated.append({'id': g.get('id'), 'remark': remark, 'color': color})
    return jsonify({'status':'success','updated': updated})

# ---------------- DASHBOARD ----------------
@app.route('/dashboard', methods=['GET','POST'])
def dashboard():
    if 'role' not in session:
        return redirect(url_for('login'))
    role = session['role']
    conn = get_db_connection()

    # CSV Upload (only for instructors)
    if request.method == 'POST' and 'csv_file' in request.files and role == 'instructor':
        file = request.files['csv_file']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            raw_bytes = file.read()
            detected = chardet.detect(raw_bytes)
            encoding = detected.get('encoding') or 'utf-8'
            decoded_file = io.StringIO(raw_bytes.decode(encoding, errors='replace'))
            reader = csv.DictReader(decoded_file)
            headers_map = {h.strip().lower(): h for h in (reader.fieldnames or [])}

            for row in reader:
                sid = row.get(headers_map.get('student id','student id'),'').strip()
                sname = row.get(headers_map.get('student name','student name'),'').strip()
                subj = row.get(headers_map.get('subject','subject'),'').strip()
                midscore = row.get(headers_map.get('midterm score','midterm score'),'').strip()
                midgrade = row.get(headers_map.get('midterm grade','midterm grade'),'').strip()
                finalscore = row.get(headers_map.get('final score','final score'),'').strip()
                finalgrade = row.get(headers_map.get('final grade','final grade'),'').strip()

                exists = conn.execute('SELECT * FROM grades WHERE student_id=? AND subject=?', (sid, subj)).fetchone()
                if exists:
                    conn.execute('UPDATE grades SET student_name=?, midterm_score=?, midterm_grade=?, final_score=?, final_grade=? WHERE id=?',
                                 (sname, midscore, midgrade, finalscore, finalgrade, exists['id']))
                else:
                    conn.execute('INSERT INTO grades (student_id, student_name, subject, midterm_score, midterm_grade, final_score, final_grade) VALUES (?,?,?,?,?,?,?)',
                                 (sid, sname, subj, midscore, midgrade, finalscore, finalgrade))
                # Auto-create student account with hashed password = student_id (change if desired)
                if sid:
                    user_exists = conn.execute('SELECT * FROM users WHERE student_id=?', (sid,)).fetchone()
                    if not user_exists:
                        conn.execute('INSERT INTO users (username,password,role,student_id,student_name) VALUES (?,?,?,?,?)',
                                     (sid, generate_password_hash(sid), 'student', sid, sname))
            conn.commit()
        else:
            flash('Invalid file or missing file (allowed: .csv)', 'danger')

    # Bulk delete (instructor only)
    if request.method == 'POST' and 'delete_ids' in request.form and role == 'instructor':
        ids = request.form.getlist('delete_ids')
        for did in ids:
            conn.execute('DELETE FROM grades WHERE id=?', (did,))
        conn.commit()

    selected_subject = request.args.get('subject','')
    student_id_filter = request.args.get('student_id','')
    student_name_filter = request.args.get('student_name','')

    q = 'SELECT * FROM grades WHERE 1=1'
    params = []

    if role=='student':
        q += ' AND student_id=?'
        params.append(session.get('student_id'))
    if selected_subject:
        q += ' AND subject=?'
        params.append(selected_subject)
    if student_id_filter:
        q += ' AND student_id LIKE ?'
        params.append(f"%{student_id_filter}%")
    if student_name_filter:
        q += ' AND student_name LIKE ?'
        params.append(f"%{student_name_filter}%")

    grades = conn.execute(q, params).fetchall()
    subjects = conn.execute('SELECT DISTINCT subject FROM grades').fetchall()

    grade_list = []
    for g in grades:
        gdict = dict(g)
        fg = (gdict.get('final_grade') or '').upper()
        try:
            gdict['remark'] = GRADE_REMARKS.get(float(fg) if fg.replace('.','',1).isdigit() else fg,'')
        except:
            gdict['remark'] = ''
        grade_list.append(gdict)

    conn.close()
    return render_template('dashboard.html',
                           grade_list=grade_list,
                           role=role,
                           grade_colors=GRADE_COLORS,
                           subjects=subjects,
                           selected_subject=selected_subject)

# ---------------- FILTER GRADES (AJAX) ----------------
@app.route('/filter_grades', methods=['GET'])
def filter_grades():
    if 'role' not in session or session['role'] != 'instructor':
        return jsonify({'grades': []})
    conn = get_db_connection()
    search = request.args.get('search','').strip()
    subject = request.args.get('subject','').strip()

    q = 'SELECT * FROM grades WHERE 1=1'
    params = []

    if search:
        q += ' AND (student_id LIKE ? OR student_name LIKE ?)'
        like_term = f"%{search}%"
        params.extend([like_term, like_term])
    if subject:
        q += ' AND subject=?'
        params.append(subject)

    grades = conn.execute(q, params).fetchall()
    conn.close()

    grade_list = []
    for g in grades:
        gdict = dict(g)
        fg = (gdict.get('final_grade') or '')
        try:
            gdict['remark'] = GRADE_REMARKS.get(float(fg) if fg.replace('.','',1).isdigit() else fg.upper(),'')
        except:
            gdict['remark'] = ''
        gdict['color'] = GRADE_COLORS.get(gdict['remark'],'#fff')
        grade_list.append(gdict)
    return jsonify({'grades': grade_list})

# ---------------- CSV TEMPLATE ----------------
@app.route('/download_template')
def download_template():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Student ID','Student Name','Section','Subject','Midterm Score','Midterm Grade','Final Score','Final Grade'])
    return send_file(io.BytesIO(output.getvalue().encode('utf-8')), mimetype='text/csv', as_attachment=True, download_name='grades_template.csv')

# ------------- Run -------------
if __name__ == '__main__':
    # for cloud hosting, use PORT env var and disable debug in production
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', '1') == '1'
    # ALWAYS set SECRET_KEY and INSTRUCTOR_CODE as environment variables in production
    app.run(host='0.0.0.0', port=port, debug=debug)
