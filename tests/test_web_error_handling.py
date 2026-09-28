from __future__ import annotations

import logging
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

import web.routes as routes_module
from web.app import app


class _RaisingPipeline:
    def query(self, question: str):
        raise RuntimeError("boom: sensitive internal detail")


def test_ask_shows_generic_message_and_logs_server_side(monkeypatch, caplog):
    monkeypatch.setattr(routes_module, "_pipeline", _RaisingPipeline())
    client = TestClient(app)

    with caplog.at_level(logging.ERROR, logger="web.routes"):
        response = client.post("/ask", data={"question": "What does the Fool mean?"})

    assert response.status_code == 200
    assert "boom: sensitive internal detail" not in response.text
    assert "Не получилось получить интерпретацию" in response.text
    assert any("RAG query failed" in record.message for record in caplog.records)


def test_ask_debug_checkbox_still_reveals_technical_detail(monkeypatch):
    monkeypatch.setattr(routes_module, "_pipeline", _RaisingPipeline())
    client = TestClient(app)

    response = client.post(
        "/ask",
        data={"question": "What does the Fool mean?", "show_debug_context": "1"},
    )

    assert response.status_code == 200
    assert "RuntimeError" in response.text
