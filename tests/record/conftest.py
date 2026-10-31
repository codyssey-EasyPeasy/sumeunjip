"""기록용 시험 fixture. 도구 함수는 rec_helpers.py."""

from __future__ import annotations

import json
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from rec_helpers import ARTICLES, FIXTURE


@pytest.fixture
def articles_file(tmp_path, monkeypatch):
    p = tmp_path / "articles.jsonl"
    with p.open("w", encoding="utf-8") as f:
        for a in ARTICLES:
            f.write(json.dumps({**a, "exposable": True, "excerpt": None}, ensure_ascii=False) + "\n")
    monkeypatch.setenv("ARTICLES_PATH", str(p))
    return p


@pytest.fixture
def make_client(articles_file):
    @contextmanager
    def _make(transport, raise_server_exceptions=True, knowledge_path=str(FIXTURE)):
        from app.main import create_app

        app = create_app(knowledge_path=knowledge_path, transport=transport)
        with TestClient(app, raise_server_exceptions=raise_server_exceptions) as client:
            yield client

    return _make
