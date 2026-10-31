import contextlib
import os
import sys
import types
from pathlib import Path

# 실제 모델 로드를 막고 server를 import 한다.
os.environ["SUMEUNJIP_NO_LOAD"] = "1"

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# torch 가 없는 개발 기기(CPU 전용)에서도 엔드포인트 시험이 돌도록 최소 대역을 넣는다.
# 실제 GPU 서버(.venv 에 torch 있음)에서는 진짜 torch 를 쓴다.
try:  # pragma: no cover - 환경에 따라 다름
    import torch  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover
    fake = types.ModuleType("torch")
    fake.inference_mode = contextlib.nullcontext
    fake.cuda = types.SimpleNamespace(is_available=lambda: False)
    fake.nn = types.SimpleNamespace(Sigmoid=lambda: None)
    sys.modules["torch"] = fake
