from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import sqlite3
from datetime import datetime, date
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.secret_key = 'supersecretkey'
DB = 'database.db'

UPLOAD_FOLDER = 'static/ads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

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
        c.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)', ('admin', hashed, 'admin'))
    
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
            c.execute('INSERT INTO desks (name, status) VALUES (?, "Free")', (desk,))
    
    # Default system info
    c.execute('SELECT COUNT(*) FROM system_info')
    if c.fetchone()[0] == 0:
        c.execute('INSERT INTO system_info (id, name, location) VALUES (1, "My Queue System", "Main Branch")')
    
    conn.commit()
    conn.close()

init_db()

# -----------------------------
# Utilities
# -----------------------------
def get_db_connection():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def reset_daily_ticket():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT last_reset FROM system_settings WHERE id=1')
    last_reset = c.fetchone()['last_reset']
    today = date.today().isoformat()
    if last_reset != today:
        c.execute('UPDATE system_settings SET last_ticket=0, last_reset=?', (today,))
        c.execute('DELETE FROM customers')
        conn.commit()
    conn.close()

def get_next_ticket_number():
    reset_daily_ticket()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT last_ticket FROM system_settings WHERE id=1')
    last_ticket = c.fetchone()['last_ticket']
    next_ticket = last_ticket + 1
    c.execute('UPDATE system_settings SET last_ticket=? WHERE id=1', (next_ticket,))
    conn.commit()
    conn.close()
    return next_ticket

def assign_customers():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM desks WHERE status="Free"')
    free_desks = c.fetchall()
    for desk in free_desks:
        c.execute('SELECT * FROM customers WHERE status="Waiting" ORDER BY created_at LIMIT 1')
        customer = c.fetchone()
        if customer:
            c.execute('UPDATE customers SET status="Being Served", desk_id=? WHERE id=?', (desk['id'], customer['id']))
            c.execute('UPDATE desks SET status="Busy", current_customer_id=? WHERE id=?', (customer['id'], desk['id']))
    conn.commit()
    conn.close()

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
        conn.close()
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
# Customer & Queue
# -----------------------------
@app.route('/')
def customer_page():
    return render_template('customer.html')

@app.route('/now_serving')
def now_serving_page():
    return render_template('now_serving.html')

@app.route('/get_ticket', methods=['POST'])
def get_ticket():
    ticket_number = get_next_ticket_number()
    now = datetime.now().isoformat()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('INSERT INTO customers (ticket_number,status,created_at) VALUES (?, "Waiting", ?)', (ticket_number, now))
    c.execute('SELECT * FROM system_info WHERE id=1')
    sys_info = c.fetchone()
    conn.commit()
    conn.close()
    assign_customers()
    return jsonify({
        'ticket_number': ticket_number,
        'system_name': sys_info['name'],
        'system_location': sys_info['location']
    })

@app.route('/finish_service/<int:desk_id>', methods=['POST'])
def finish_service(desk_id):
    if 'role' not in session or session['role'] not in ['admin','staff']:
        return "Access Denied",403
    now = datetime.now().isoformat()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT current_customer_id FROM desks WHERE id=?', (desk_id,))
    row = c.fetchone()
    if row and row['current_customer_id']:
        customer_id = row['current_customer_id']
        c.execute('UPDATE customers SET status="Done", served_at=? WHERE id=?', (now, customer_id))
        c.execute('UPDATE desks SET status="Free", current_customer_id=NULL WHERE id=?', (desk_id,))
    conn.commit()
    conn.close()
    assign_customers()
    return jsonify({'status':'success'})

@app.route('/status')
def get_status():
    conn = get_db_connection()
    c = conn.cursor()

    # Get desks with current ticket numbers
    c.execute('''
        SELECT d.id, d.name, c.ticket_number
        FROM desks d
        LEFT JOIN customers c ON d.current_customer_id = c.id
    ''')
    desks = [dict(d) for d in c.fetchall()]

    # Get waiting tickets
    c.execute('SELECT ticket_number FROM customers WHERE status="Waiting" ORDER BY created_at')
    waiting = [row['ticket_number'] for row in c.fetchall()]

    conn.close()
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
    conn.close()
    return jsonify({'name':info['name'], 'location':info['location']})

@app.route('/update_system_info', methods=['POST'])
def update_system_info():
    if 'role' not in session or session['role']!='admin':
        return "Access Denied",403
    name = request.form['name']
    location = request.form['location']
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('UPDATE system_info SET name=?, location=? WHERE id=1', (name,location))
    conn.commit()
    conn.close()
    return jsonify({'status':'success'})

# -----------------------------
# User Management (Admin)
# -----------------------------
@app.route('/users')
def users():
    if 'role' not in session or session['role']!='admin':
        return "Access Denied",403
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT id,username,role FROM users WHERE role="staff"')
    users = [dict(r) for r in c.fetchall()]
    conn.close()
    return jsonify(users)

@app.route('/add_user', methods=['POST'])
def add_user():
    if 'role' not in session or session['role']!='admin':
        return "Access Denied",403
    username = request.form['username']
    password = request.form['password']
    hashed = generate_password_hash(password)
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('INSERT INTO users (username,password,role) VALUES (?, ?, "staff")', (username,hashed))
    conn.commit()
    conn.close()
    return jsonify({'status':'success'})

@app.route('/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if 'role' not in session or session['role']!='admin':
        return "Access Denied",403
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('DELETE FROM users WHERE id=?', (user_id,))
    conn.commit()
    conn.close()
    return jsonify({'status':'success'})

# -----------------------------
# Desk Management (Admin)
# -----------------------------
@app.route('/desks')
def get_desks():
    if 'role' not in session or session['role']!='admin':
        return "Access Denied",403
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM desks')
    desks = [dict(d) for d in c.fetchall()]
    conn.close()
    return jsonify(desks)

@app.route('/add_desk', methods=['POST'])
def add_desk():
    if 'role' not in session or session['role']!='admin':
        return "Access Denied",403
    name = request.form['name']
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('INSERT INTO desks (name,status) VALUES (?, "Free")', (name,))
    conn.commit()
    conn.close()
    return jsonify({'status':'success'})

@app.route('/delete_desk/<int:desk_id>', methods=['POST'])
def delete_desk(desk_id):
    if 'role' not in session or session['role']!='admin':
        return "Access Denied",403
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('DELETE FROM desks WHERE id=?', (desk_id,))
    conn.commit()
    conn.close()
    return jsonify({'status':'success'})

# -----------------------------
# Ads Management
# -----------------------------
@app.route('/upload_ad', methods=['POST'])
def upload_ad():
    if 'role' not in session or session['role']!='admin':
        return "Access Denied",403
    file = request.files['ad_video']
    if file:
        filepath = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(filepath)
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('INSERT INTO ads (filename,active) VALUES (?,0)', (file.filename,))
        conn.commit()
        conn.close()
        return jsonify({'status':'success'})
    return jsonify({'status':'error','message':'No file uploaded'})

@app.route('/set_active_ad/<int:ad_id>', methods=['POST'])
def set_active_ad(ad_id):
    if 'role' not in session or session['role']!='admin':
        return "Access Denied",403
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('UPDATE ads SET active=0')
    c.execute('UPDATE ads SET active=1 WHERE id=?', (ad_id,))
    conn.commit()
    conn.close()
    return jsonify({'status':'success'})

@app.route('/list_ads')
def list_ads():
    if 'role' not in session or session['role']!='admin':
        return "Access Denied",403
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM ads')
    ads = [dict(r) for r in c.fetchall()]
    conn.close()
    return jsonify(ads)

@app.route('/get_active_ad')
def get_active_ad():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT filename FROM ads WHERE active=1 LIMIT 1')
    row = c.fetchone()
    conn.close()
    if row:
        return jsonify({'filename': row['filename']})
    return jsonify({'filename': None})

# -----------------------------
# Analytics
# -----------------------------


@app.route('/analytics')
def analytics():
    if 'role' not in session or session['role'] != 'admin':
        return "Access Denied", 403

    conn = get_db_connection()
    c = conn.cursor()
    today = date.today().isoformat()

    # ----------------------
    # Total served today
    # ----------------------
    c.execute('SELECT COUNT(*) as total_served FROM customers WHERE status="Done" AND DATE(served_at)=?', (today,))
    total_served_today = c.fetchone()['total_served']

    # ----------------------
    # Average wait time overall
    # ----------------------
    c.execute('SELECT AVG(strftime("%s", served_at)-strftime("%s", created_at)) as avg_wait_seconds '
              'FROM customers WHERE status="Done" AND DATE(served_at)=?', (today,))
    avg_wait_seconds = c.fetchone()['avg_wait_seconds'] or 0

    # ----------------------
    # Per-desk analytics
    # ----------------------
    c.execute('''
        SELECT desks.name AS desk,
               AVG(strftime("%s", customers.served_at)-strftime("%s", customers.created_at)) AS avg_service_sec,
               AVG(strftime("%s", customers.served_at)-strftime("%s", customers.created_at)) AS avg_wait,
               COUNT(customers.id) AS total_served
        FROM customers
        JOIN desks ON customers.desk_id = desks.id
        WHERE customers.status="Done" AND DATE(customers.served_at)=?
        GROUP BY customers.desk_id
    ''', (today,))
    per_desk = [dict(r) for r in c.fetchall()]

    # ----------------------
    # Currently waiting per hour (0-23)
    # ----------------------
    hourly_waiting = []
    for hour in range(24):
        c.execute('''
            SELECT COUNT(*) as waiting_count
            FROM customers
            WHERE status="Waiting" 
              AND DATE(created_at)=? 
              AND strftime('%H', created_at)=?
        ''', (today, f'{hour:02d}'))
        hourly_waiting.append(c.fetchone()['waiting_count'])

    conn.close()

    return jsonify({
        'total_served_today': total_served_today,
        'avg_wait_seconds': avg_wait_seconds,
        'avg_service_per_desk': per_desk,
        'currently_waiting_hourly': hourly_waiting
    })

# -----------------------------
# Run
# -----------------------------
if __name__=='__main__':
    app.run(debug=True)
