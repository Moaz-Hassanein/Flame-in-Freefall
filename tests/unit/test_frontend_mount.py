from fastapi import FastAPI
from fastapi.testclient import TestClient

from flame.api.frontend_mount import mount_frontend


def make_app(tmp_path, with_dist=True):
    if with_dist:
        (tmp_path / "assets").mkdir()
        (tmp_path / "index.html").write_text("<html>SPA</html>")
        (tmp_path / "assets" / "app.js").write_text("console.log(1)")
        (tmp_path / "favicon.txt").write_text("fav")
    app = FastAPI()

    @app.get("/api/v1/ping")
    def ping():
        return {"ok": True}

    mount_frontend(app, tmp_path)
    return TestClient(app)


def test_root_and_unknown_routes_serve_index(tmp_path):
    c = make_app(tmp_path)
    assert "SPA" in c.get("/").text
    assert "SPA" in c.get("/some/client/route").text


def test_static_assets_are_served(tmp_path):
    c = make_app(tmp_path)
    assert c.get("/assets/app.js").text == "console.log(1)"
    assert c.get("/favicon.txt").text == "fav"


def test_api_routes_are_not_shadowed(tmp_path):
    c = make_app(tmp_path)
    assert c.get("/api/v1/ping").json() == {"ok": True}
    r = c.get("/api/v1/does-not-exist")
    assert r.status_code == 404
    assert "SPA" not in r.text
    assert c.get("/api").status_code == 404


def test_path_traversal_does_not_leak_files(tmp_path):
    secret = tmp_path.parent / "secret.txt"
    secret.write_text("top secret")
    c = make_app(tmp_path)
    assert "top secret" not in c.get("/..%2Fsecret.txt").text


def test_nothing_mounted_when_dist_missing(tmp_path):
    c = make_app(tmp_path, with_dist=False)
    assert c.get("/").status_code == 404
    assert c.get("/api/v1/ping").status_code == 200
