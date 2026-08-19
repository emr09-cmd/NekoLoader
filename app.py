import os
import sqlite3
import io
import zipfile
import re
from flask import Flask, render_template, jsonify, request, g, send_file

app = Flask(__name__)

# Use /tmp on serverless environments like Vercel, or local file otherwise
if os.environ.get('VERCEL'):
    DATABASE = '/tmp/nekoloader.db'
else:
    DATABASE = 'nekoloader.db'

TEMPLATE_ZIP_PATH = 'example-nekomod.zip'

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
    try:
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
                java_version INTEGER NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        db.commit()
    except Exception as e:
        print(f"Database init warning: {e}")

@app.before_request
def ensure_db_loaded():
    init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/v1/download/universal', methods=['POST'])
def record_download():
    download_id = None
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO downloads (installer_type, user_agent, ip_address) VALUES (?, ?, ?)",
            ('universal', request.headers.get('User-Agent', 'Unknown'), request.remote_addr)
        )
        db.commit()
        download_id = cursor.lastrowid
    except Exception as e:
        print(f"Failed to record download: {e}")

    return jsonify({
        "status": "success",
        "installer": "universal",
        "download_id": download_id,
        "download_url": "/static/builds/nekoloader-universal-installer.jar"
    }), 200

@app.route('/api/v1/template/generate', methods=['POST'])
def generate_template():
    data = request.get_json() or {}
    
    mod_name = data.get('mod_name', 'ExampleMod')
    bundle_id = data.get('bundle_id', 'com.example.examplemod')
    author = data.get('author', 'Developer')
    mod_version = data.get('mod_version', '1.0.0')
    game_version = '26.2'
    java_version = 25

    # Safe DB Logging
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('''
            INSERT INTO mod_templates (mod_name, bundle_id, author, mod_version, game_version, java_version)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (mod_name, bundle_id, author, mod_version, game_version, java_version))
        db.commit()
    except Exception as e:
        print(f"Database write skipped: {e}")

    # Derived Class & Package details
    clean_mod_class = re.sub(r'[^a-zA-Z0-9]', '', mod_name.title()) or "ExampleMod"
    package_path = bundle_id.replace('.', '/')
    java_file_path = f"example-nekomod/src/main/java/{package_path}/{clean_mod_class}.java"

    out_buffer = io.BytesIO()

    # Modify existing template ZIP dynamically
    with zipfile.ZipFile(TEMPLATE_ZIP_PATH, 'r') as in_zip:
        with zipfile.ZipFile(out_buffer, 'w', zipfile.ZIP_DEFLATED) as out_zip:
            for item in in_zip.infolist():
                # Omit default Java main class to replace it with user package structure
                if item.filename.startswith("example-nekomod/src/main/java/") and item.filename.endswith(".java"):
                    continue

                content = in_zip.read(item.filename)

                # 1. Update neko.mod.json
                if item.filename == 'example-nekomod/src/main/resources/neko.mod.json':
                    mod_json = f'''{{
  "schemaVersion": 1,
  "id": "{bundle_id}",
  "version": "{mod_version}",
  "name": "{mod_name}",
  "authors": ["{author}"],
  "entrypoints": {{
    "main": [
      "{bundle_id}.{clean_mod_class}"
    ]
  }},
  "depends": {{
    "minecraft": "26.2",
    "java": ">=25",
    "nekoloader": ">=1.0.0"
  }}
}}'''
                    out_zip.writestr(item, mod_json)

                # 2. Update settings.gradle (Add plugin management repositories)
                elif item.filename == 'example-nekomod/settings.gradle':
                    settings_gradle = f'''pluginManagement {{
    repositories {{
        mavenLocal()
        mavenCentral()
        gradlePluginPortal()
        flatDir {{
            dirs 'libs'
        }}
    }}
}}

rootProject.name = '{mod_name.lower().replace(' ', '-')}'
'''
                    out_zip.writestr(item, settings_gradle)

                # 3. Update build.gradle (Define local jar fallback & repositories)
                elif item.filename == 'example-nekomod/build.gradle':
                    build_gradle = f'''// NekoLoader Template - MC 26.2 (Java 25)
plugins {{
    id 'java'
    id 'nekoloader-gradle' version '1.0.0' apply false
}}

try {{
    apply plugin: 'nekoloader-gradle'
}} catch (Exception e) {{
    logger.warn("nekoloader-gradle plugin not found on remote repositories. Falling back to local binaries.")
}}

group = '{bundle_id}'
version = '{mod_version}'

java {{
    toolchain {{
        languageVersion = JavaLanguageVersion.of(25)
    }}
}}

repositories {{
    mavenLocal()
    mavenCentral()
    flatDir {{
        dirs 'libs'
    }}
}}

dependencies {{
    implementation fileTree(dir: 'libs', include: ['*.jar'])
}}

try {{
    nekoloader {{
        gameVersion = '26.2'
    }}
}} catch (MissingPropertyException | Exception ignored) {{}}
'''
                    out_zip.writestr(item, build_gradle)

                # Copy all other binary/wrapper files as-is
                else:
                    out_zip.writestr(item, content)

            # Insert new custom Java entrypoint file matching user inputs
            java_code = f'''package {bundle_id};

public class {clean_mod_class} {{
    public void onInitialize() {{
        System.out.println("Initialized {mod_name} v{mod_version} by {author} (MC 26.2 - Java 25)");
    }}
}}
'''
            out_zip.writestr(java_file_path, java_code)

    out_buffer.seek(0)
    return send_file(
        out_buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'{mod_name.lower().replace(" ", "-")}-template-26.2.zip'
    )

if __name__ == '__main__':
    print("NekoLoader web portal listening on http://0.0.0.0:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)