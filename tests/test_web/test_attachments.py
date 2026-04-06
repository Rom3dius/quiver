"""Tests for file attachment upload and delivery."""

from __future__ import annotations

import io

from quiver.repositories import attachment_repo, inject_repo
from quiver.services import request_service


def test_inject_with_file_upload(client, seeded_db, web_teams, tmp_path):
    data = {
        "content": "Intel report with satellite imagery",
        "operator": "C2",
        "team_ids": [web_teams[0].id],
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
    injects = inject_repo.get_all(seeded_db)
    assert len(injects) >= 1
    attachments = attachment_repo.get_for_inject(seeded_db, injects[0].id)
    assert len(attachments) == 1
    assert attachments[0].filename == "satellite.png"


def test_inject_without_files(client, seeded_db, web_teams):
    resp = client.post(
        "/injects/",
        data={
            "content": "Text only inject",
            "operator": "C2",
            "team_ids": [web_teams[0].id],
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    assert b"sent to" in resp.data


def test_resolve_request_with_file(client, seeded_db, web_teams, tmp_path):
    team = web_teams[0]
    req = request_service.create_request(seeded_db, team.id, "Need intel on target")

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

    attachments = attachment_repo.get_for_request(seeded_db, req.id)
    assert len(attachments) == 1
    assert attachments[0].filename == "dossier.pdf"
