import sqlite3
import io
import zipfile
from flask import Flask, render_template, jsonify, request, g, send_file

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
                installer_type TEXT NOT NULL,
                user_agent TEXT,
                ip_address TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS mod_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mod_name TEXT NOT NULL,
                bundle_id TEXT NOT NULL,
                author TEXT NOT NULL,
                mod_version TEXT NOT NULL,
                game_version TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        db.commit()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/v1/download/universal', methods=['POST'])
def record_download():
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO downloads (installer_type, user_agent, ip_address) VALUES (?, ?, ?)",
        ('universal', request.headers.get('User-Agent', 'Unknown'), request.remote_addr)
    )
    db.commit()
    return jsonify({
        "status": "success",
        "installer": "universal",
        "download_id": cursor.lastrowid,
        "download_url": "/static/builds/nekoloader-universal-installer.jar"
    }), 200

@app.route('/api/v1/template/generate', methods=['POST'])
def generate_template():
    data = request.get_json() or {}
    
    mod_name = data.get('mod_name', 'ExampleMod')
    bundle_id = data.get('bundle_id', 'com.example.mod')
    author = data.get('author', 'Anonymous')
    mod_version = data.get('mod_version', '1.0.0')
    game_version = data.get('game_version', '26.2')

    db = get_db()
    cursor = db.cursor()
    cursor.execute('''
        INSERT INTO mod_templates (mod_name, bundle_id, author, mod_version, game_version)
        VALUES (?, ?, ?, ?, ?)
    ''', (mod_name, bundle_id, author, mod_version, game_version))
    db.commit()

    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        mod_json = f'''{{
  "schemaVersion": 1,
  "id": "{bundle_id}",
  "version": "{mod_version}",
  "name": "{mod_name}",
  "authors": ["{author}"],
  "depends": {{
    "minecraft": "26.2",
    "nekoloader": ">=1.0.0"
  }}
}}'''
        build_gradle = f'''// NekoLoader Template - MC 26.2
plugins {{
    id 'nekoloader-gradle' version '1.0.0'
}}

group = '{bundle_id}'
version = '{mod_version}'

nekoloader {{
    gameVersion = '26.2'
}}
'''
        zf.writestr('nekoloader.mod.json', mod_json)
        zf.writestr('build.gradle', build_gradle)
        zf.writestr('src/main/java/Main.java', f'// Mod entry point for {mod_name}\npublic class Main {{}}')

    memory_file.seek(0)
    return send_file(
        memory_file,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'{mod_name}-template-{game_version}.zip'
    )

if __name__ == '__main__':
    init_db()
    print("NekoLoader web portal listening on http://0.0.0.0:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)