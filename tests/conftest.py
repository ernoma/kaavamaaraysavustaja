import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session")
def root() -> Path:
    return ROOT


@pytest.fixture(scope="session")
def index():
    from kaavamaaraysavustaja.knowledge import CodelistIndex

    return CodelistIndex.load()


@pytest.fixture(scope="session")
def build_result():
    pytest.importorskip("openpyxl")
    from tools.build_knowledge import build

    return build(ROOT)


@pytest.fixture(scope="session")
def kb():
    from kaavamaaraysavustaja.knowledge.base import KnowledgeBase

    return KnowledgeBase.load()


@pytest.fixture(scope="session")
def policies():
    from kaavamaaraysavustaja.core.policy import PolicyLibrary

    return PolicyLibrary.load()
