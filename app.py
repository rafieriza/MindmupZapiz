import os
import json
import pymysql
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'mindmapiz-super-secret-key')

# Konfigurasi Koneksi Aiven MySQL
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'YOUR_AIVEN_HOST.aivencloud.com'),
    'port': int(os.environ.get('DB_PORT', 12345)),
    'user': os.environ.get('DB_USER', 'avnadmin'),
    'password': os.environ.get('DB_PASSWORD', 'YOUR_AIVEN_PASSWORD'),
    'database': os.environ.get('DB_NAME', 'defaultdb'),
    'cursorclass': pymysql.cursors.DictCursor
}

def get_db_connection():
    return pymysql.connect(**DB_CONFIG)

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('index.html', username=session.get('username'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json() or request.form
        username = data.get('username')
        password = data.get('password')

        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
            user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            return jsonify({'success': True, 'redirect': '/'})
        return jsonify({'success': False, 'message': 'Username atau password salah!'}), 400
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.get_json() or request.form
        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            return jsonify({'success': False, 'message': 'Data tidak lengkap'}), 400

        hashed_pw = generate_password_hash(password)
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("INSERT INTO users (username, password_hash) VALUES (%s, %s)", (username, hashed_pw))
            conn.commit()
            return jsonify({'success': True, 'redirect': '/login'})
        except pymysql.err.IntegrityError:
            return jsonify({'success': False, 'message': 'Username sudah terpakai!'}), 400
        finally:
            conn.close()

    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# API Endpoint CRUD Projek Mind Map
@app.route('/api/projects', methods=['GET'])
def get_projects():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT id, title, updated_at FROM mindmaps WHERE user_id = %s ORDER BY updated_at DESC", (session['user_id'],))
        projects = cursor.fetchall()
    conn.close()
    return jsonify({'projects': projects})

@app.route('/api/projects/<int:project_id>', methods=['GET'])
def get_project_detail(project_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM mindmaps WHERE id = %s AND user_id = %s", (project_id, session['user_id']))
        project = cursor.fetchone()
    conn.close()

    if not project:
        return jsonify({'error': 'Projek tidak ditemukan'}), 404

    project['data'] = json.loads(project['data'])
    return jsonify({'project': project})

@app.route('/api/projects/save', methods=['POST'])
def save_project():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    req_data = request.get_json()
    project_id = req_data.get('id')
    title = req_data.get('title', 'Projek Tanpa Nama')
    content_data = json.dumps(req_data.get('data'))

    conn = get_db_connection()
    with conn.cursor() as cursor:
        if project_id:
            cursor.execute("UPDATE mindmaps SET title = %s, data = %s WHERE id = %s AND user_id = %s", 
                           (title, content_data, project_id, session['user_id']))
        else:
            cursor.execute("INSERT INTO mindmaps (user_id, title, data) VALUES (%s, %s, %s)", 
                           (session['user_id'], title, content_data))
            project_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'project_id': project_id, 'message': 'Projek berhasil disimpan ke cloud!'})
