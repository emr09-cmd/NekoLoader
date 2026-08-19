import sqlite3
from datetime import datetime
from flask import Flask, render_template, jsonify, request, g

app = Flask(__name__)
DATABASE = 'nekoloader.db'

def get_db():
    """Connects to the SQLite database."""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    """Closes the database connection at the end of the request."""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    """Initializes the database schema."""
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS downloads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version TEXT NOT NULL,
                user_agent TEXT,
                ip_address TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        db.commit()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/v1/download/26.2', methods=['POST'])
def record_download():
    """Records download metadata directly into the database."""
    db = get_db()
    cursor = db.cursor()
    
    user_agent = request.headers.get('User-Agent', 'Unknown')
    ip_addr = request.remote_addr
    
    cursor.execute(
        "INSERT INTO downloads (version, user_agent, ip_address) VALUES (?, ?, ?)",
        ('26.2', user_agent, ip_addr)
    )
    db.commit()
    
    download_id = cursor.lastrowid
    
    return jsonify({
        "status": "success",
        "message": "NekoLoader 26.2 build fetch initiated.",
        "download_id": download_id,
        "download_url": "/static/builds/nekoloader-26.2-installer.jar"
    }), 200

if __name__ == '__main__':
    init_db()
    print("NekoLoader web portal listening on http://0.0.0.0:5000")
    # Bind to 0.0.0.0 to listen on all public/network interfaces
    app.run(host='0.0.0.0', port=5000, debug=True)