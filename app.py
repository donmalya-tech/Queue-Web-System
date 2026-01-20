from flask import Flask, render_template, request, jsonify, redirect, url_for, session, g
import sqlite3
from datetime import datetime, date
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
from contextlib import contextmanager

app = Flask(__name__)
app.secret_key = 'supersecretkey'
DB = 'database.db'

UPLOAD_FOLDER = 'static/ads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# -----------------------------
# Database Connection & Transaction
# -----------------------------
def get_db_connection():
    """Per-request SQLite connection."""
    if 'db_conn' not in g:
        conn = sqlite3.connect(DB, detect_types=sqlite3.PARSE_DECLTYPES)
        conn.row_factory = sqlite3.Row
        g.db_conn = conn
    return g.db_conn

@app.teardown_appcontext
def close_db_connection(exception=None):
    """Close DB connection at request teardown."""
    conn = g.pop('db_conn', None)
    if conn is not None:
        conn.close()

@contextmanager
def db_transaction():
    """SQLite transaction context manager with BEGIN IMMEDIATE."""
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute('BEGIN IMMEDIATE')
        yield c
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e

# -----------------------------
# Database Initialization
# -----------------------------
def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    # Users
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT
    )''')

    # Desks
    c.execute('''CREATE TABLE IF NOT EXISTS desks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        status TEXT,
        current_customer_id INTEGER
    )''')

    # Customers
    c.execute('''CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_number INTEGER,
        status TEXT,
        desk_id INTEGER,
        created_at TEXT,
        served_at TEXT
    )''')

    # System info
    c.execute('''CREATE TABLE IF NOT EXISTS system_info (
        id INTEGER PRIMARY KEY,
        name TEXT,
        location TEXT
    )''')

    # System settings
    c.execute('''CREATE TABLE IF NOT EXISTS system_settings (
        id INTEGER PRIMARY KEY,
        last_ticket INTEGER,
        last_reset TEXT
    )''')

    # Ads
    c.execute('''CREATE TABLE IF NOT EXISTS ads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT,
        active INTEGER DEFAULT 0
    )''')

    # Default admin
    c.execute('SELECT COUNT(*) FROM users')
    if c.fetchone()[0] == 0:
        hashed = generate_password_hash('admin123')
        c.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)',
                  ('admin', hashed, 'admin'))

    # Default system settings
    c.execute('SELECT COUNT(*) FROM system_settings')
    if c.fetchone()[0] == 0:
        today = date.today().isoformat()
        c.execute('INSERT INTO system_settings (id, last_ticket, last_reset) VALUES (1, 0, ?)', (today,))

    # Default desks
    c.execute('SELECT COUNT(*) FROM desks')
    if c.fetchone()[0] == 0:
        desks = ['Desk 1', 'Desk 2', 'Desk 3']
        for desk in desks:
            c.execute('INSERT INTO desks (name,status) VALUES (?, "Free")', (desk,))

    # Default system info
    c.execute('SELECT COUNT(*) FROM system_info')
    if c.fetchone()[0] == 0:
        c.execute('INSERT INTO system_info (id, name, location) VALUES (1, "My Queue System", "Main Branch")')

    conn.commit()
    conn.close()

init_db()

# -----------------------------
# Queue Management
# -----------------------------
def assign_customers():
    """Assign waiting customers to free desks safely."""
    try:
        with db_transaction() as c:
            c.execute('SELECT id FROM desks WHERE status="Free" ORDER BY id')
            free_desks = [row['id'] for row in c.fetchall()]

            for desk_id in free_desks:
                c.execute('SELECT id FROM customers WHERE status="Waiting" ORDER BY created_at LIMIT 1')
                customer = c.fetchone()

                if customer:
                    c.execute(
                        'UPDATE customers SET status="Being Served", desk_id=? WHERE id=?',
                        (desk_id, customer['id'])
                    )
                    c.execute(
                        'UPDATE desks SET status="Busy", current_customer_id=? WHERE id=?',
                        (customer['id'], desk_id)
                    )
    except Exception as e:
        print("Error assigning customers:", e)

# -----------------------------
# Authentication
# -----------------------------
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method=='POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE username=?', (username,))
        user = c.fetchone()
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['role'] = user['role']
            if user['role']=='admin':
                return redirect(url_for('admin_page'))
            else:
                return redirect(url_for('staff_page'))
        return "Invalid credentials"
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# -----------------------------
# Admin Routes
# -----------------------------
@app.route('/admin')
def admin_page():
    if 'role' not in session or session['role']!='admin':
        return "Access Denied",403
    return render_template('admin.html')

# -----------------------------
# Staff Routes
# -----------------------------
@app.route('/staff')
def staff_page():
    if 'role' not in session or session['role']!='staff':
        return "Access Denied",403
    return render_template('staff.html')

# -----------------------------
# Customer / Ticket Routes
# -----------------------------
@app.route('/')
def customer_page():
    return render_template('customer.html')

@app.route('/now_serving')
def now_serving_page():
    return render_template('now_serving.html')

@app.route('/get_ticket', methods=['POST'])
def get_ticket():
    try:
        with db_transaction() as c:
            today = date.today().isoformat()
            c.execute('SELECT last_reset, last_ticket FROM system_settings WHERE id=1')
            settings = c.fetchone()

            if settings['last_reset'] != today:
                # Daily reset
                c.execute('UPDATE system_settings SET last_ticket=0, last_reset=? WHERE id=1', (today,))
                c.execute('DELETE FROM customers')
                c.execute('UPDATE desks SET status="Free", current_customer_id=NULL')
                last_ticket = 0
            else:
                last_ticket = settings['last_ticket']

            next_ticket = last_ticket + 1
            c.execute('UPDATE system_settings SET last_ticket=? WHERE id=1', (next_ticket,))

            now = datetime.now().isoformat()
            c.execute('INSERT INTO customers (ticket_number, status, created_at) VALUES (?, "Waiting", ?)',
                      (next_ticket, now))

            c.execute('SELECT * FROM system_info WHERE id=1')
            sys_info = c.fetchone()

        assign_customers()

        return jsonify({
            'ticket_number': next_ticket,
            'system_name': sys_info['name'],
            'system_location': sys_info['location']
        })
    except Exception as e:
        return jsonify({'status':'error', 'message': str(e)})

@app.route('/finish_service/<int:desk_id>', methods=['POST'])
def finish_service(desk_id):
    if 'role' not in session or session['role'] not in ['admin','staff']:
        return "Access Denied", 403
    try:
        with db_transaction() as c:
            now = datetime.now().isoformat()
            c.execute('SELECT current_customer_id FROM desks WHERE id=?', (desk_id,))
            row = c.fetchone()
            if row and row['current_customer_id']:
                customer_id = row['current_customer_id']
                c.execute('UPDATE customers SET status="Done", served_at=? WHERE id=?', (now, customer_id))
                c.execute('UPDATE desks SET status="Free", current_customer_id=NULL WHERE id=?', (desk_id,))
        assign_customers()
        return jsonify({'status':'success'})
    except Exception as e:
        return jsonify({'status':'error', 'message': str(e)})

@app.route('/status')
def get_status():
    conn = get_db_connection()
    c = conn.cursor()

    c.execute('''
        SELECT d.id, d.name, c.ticket_number
        FROM desks d
        LEFT JOIN customers c ON d.current_customer_id = c.id
    ''')
    desks = [dict(d) for d in c.fetchall()]

    c.execute('SELECT ticket_number FROM customers WHERE status="Waiting" ORDER BY created_at')
    waiting = [row['ticket_number'] for row in c.fetchall()]

    return jsonify({'desks': desks, 'waiting': waiting})

# -----------------------------
# System Info
# -----------------------------
@app.route('/system_info')
def system_info():
    if 'role' not in session or session['role']!='admin':
        return "Access Denied",403
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM system_info WHERE id=1')
    info = c.fetchone()
    return jsonify({'name':info['name'], 'location':info['location']})

@app.route('/update_system_info', methods=['POST'])
def update_system_info():
    if 'role' not in session or session['role']!='admin':
        return "Access Denied",403
    name = request.form['name']
    location = request.form['location']
    try:
        with db_transaction() as c:
            c.execute('UPDATE system_info SET name=?, location=? WHERE id=1', (name,location))
        return jsonify({'status':'success'})
    except Exception as e:
        return jsonify({'status':'error', 'message': str(e)})

# -----------------------------
# Users, Desks, Ads, Analytics
# -----------------------------
# All admin write operations should use db_transaction() for atomic updates
# All read operations can use get_db_connection() safely

# (Include your existing routes for users, desks, ads, analytics)
# Replace conn/cursor usage with get_db_connection() and db_transaction() for writes

# -----------------------------
# Run
# -----------------------------
if __name__=='__main__':
    app.run(debug=True)
