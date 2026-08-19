import io
import zipfile

import app as app_module


def setup_test_database(tmp_path):
    db_path = tmp_path / "test.db"
    app_module.DATABASE = str(db_path)

    with app_module.app.app_context():
        app_module.init_db()


def test_app_starts(tmp_path):
    setup_test_database(tmp_path)

    client = app_module.app.test_client()

    response = client.get("/")

    assert response.status_code == 200


def test_record_download(tmp_path):
    setup_test_database(tmp_path)

    client = app_module.app.test_client()

    response = client.post("/api/v1/download/universal")

    assert response.status_code == 200

    data = response.get_json()

    assert data["status"] == "success"
    assert data["installer"] == "universal"
    assert data["download_id"] == 1
    assert data["download_url"] == (
        "/static/builds/nekoloader-universal-installer.jar"
    )


def test_generate_template(tmp_path):
    setup_test_database(tmp_path)

    client = app_module.app.test_client()

    response = client.post(
        "/api/v1/template/generate",
        json={
            "mod_name": "TestMod",
            "bundle_id": "com.test.mod",
            "author": "Test Author",
            "mod_version": "1.0.0",
            "game_version": "26.2",
        },
    )

    assert response.status_code == 200
    assert response.mimetype == "application/zip"

    zip_file = zipfile.ZipFile(
        io.BytesIO(response.data)
    )

    assert "nekoloader.mod.json" in zip_file.namelist()
    assert "build.gradle" in zip_file.namelist()
    assert "src/main/java/Main.java" in zip_file.namelist()
