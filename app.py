import sqlite3
from flask import Flask, render_template, jsonify, request, g

app = Flask(__name__)
DATABASE = 'nekoloader.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
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

@app.route('/api/v1/download/<version>', methods=['POST'])
def record_download(version):
    """Records download metadata for the selected version into the database."""
    db = get_db()
    cursor = db.cursor()
    
    user_agent = request.headers.get('User-Agent', 'Unknown')
    ip_addr = request.remote_addr
    
    cursor.execute(
        "INSERT INTO downloads (version, user_agent, ip_address) VALUES (?, ?, ?)",
        (version, user_agent, ip_addr)
    )
    db.commit()
    
    download_id = cursor.lastrowid
    
    return jsonify({
        "status": "success",
        "version": version,
        "message": f"NekoLoader {version} build fetch initiated.",
        "download_id": download_id,
        "download_url": f"/static/builds/nekoloader-{version}-installer.jar"
    }), 200

if __name__ == '__main__':
    init_db()
    print("NekoLoader web portal listening on http://0.0.0.0:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)