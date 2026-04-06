"""Tests for file attachment upload and delivery."""

from __future__ import annotations

import io

import pytest

from quiver.config import Config
from quiver.db.connection import get_connection
from quiver.repositories import attachment_repo, team_repo
from quiver.services import request_service
from quiver.web.app import create_app


@pytest.fixture
def app(tmp_path):
    db_path = tmp_path / "test.db"
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    config = Config(
        discord_token="test-token",
        bot_command_prefix="!",
        database_path=db_path,
        uploads_path=uploads,
        flask_host="127.0.0.1",
        flask_port=5000,
    )
    app = create_app(config)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db(app):
    conn = get_connection(app.config["DATABASE_PATH"])
    yield conn
    conn.close()


def test_inject_with_file_upload(client, db, tmp_path):
    teams = team_repo.get_all(db)

    data = {
        "content": "Intel report with satellite imagery",
        "operator": "C2",
        "team_ids": [teams[0].id],
    }
    data["attachments"] = (io.BytesIO(b"fake image data"), "satellite.png")

    resp = client.post(
        "/injects/",
        data=data,
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    assert b"1 file" in resp.data

    # Verify attachment in DB
    from quiver.repositories import inject_repo

    injects = inject_repo.get_all(db)
    assert len(injects) >= 1
    attachments = attachment_repo.get_for_inject(db, injects[0].id)
    assert len(attachments) == 1
    assert attachments[0].filename == "satellite.png"


def test_inject_without_files(client, db):
    teams = team_repo.get_all(db)
    resp = client.post(
        "/injects/",
        data={
            "content": "Text only inject",
            "operator": "C2",
            "team_ids": [teams[0].id],
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    assert b"sent to" in resp.data


def test_resolve_request_with_file(client, db, tmp_path):
    team = team_repo.get_by_name(db, "CIA")
    req = request_service.create_request(db, team.id, "Need intel on target")

    data = {
        "status": "approved",
        "response": "Here is the dossier",
        "attachments": (io.BytesIO(b"%PDF-fake"), "dossier.pdf"),
    }
    resp = client.post(
        f"/requests/{req.id}/resolve",
        data=data,
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    assert b"APPROVED" in resp.data
    assert b"1 file" in resp.data

    attachments = attachment_repo.get_for_request(db, req.id)
    assert len(attachments) == 1
    assert attachments[0].filename == "dossier.pdf"
