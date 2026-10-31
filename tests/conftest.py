"""앱 시험 공통: GPU 토큰 파일을 기본적으로 없는 임시 경로로 둔다(실제 ~/.config 를 읽지 않음)."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolated_gpu_token(tmp_path, monkeypatch):
    monkeypatch.setenv("GPU_TOKEN_FILE", str(tmp_path / "no_gpu_token"))
