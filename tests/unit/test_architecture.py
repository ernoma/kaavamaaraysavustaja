"""Architecture rule A1: the core never imports QGIS; optional SDKs are imported lazily."""

import ast
import subprocess
import sys
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[2] / "kaavamaaraysavustaja"
QGIS_FREE = ["core", "knowledge", "exporters", "validation"]
# PDF libraries are development tools only (tools/extract_pdf_text.py, ADR-0009).
PDF_LIBRARIES = {"pypdf", "PyPDF2", "fitz", "pymupdf", "pdfminer", "pdfplumber"}
FORBIDDEN_ANYWHERE = {"qgis", "PyQt5", "PyQt6", "sip", "openpyxl"} | PDF_LIBRARIES
LAZY_ONLY = {"anthropic", "mistralai"}


def modules():
    for sub in QGIS_FREE:
        yield from sorted((PACKAGE / sub).rglob("*.py"))


def imported(node):
    if isinstance(node, ast.Import):
        return [alias.name.split(".")[0] for alias in node.names]
    if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
        return [node.module.split(".")[0]]
    return []


@pytest.mark.parametrize("path", list(modules()), ids=lambda p: p.relative_to(PACKAGE).as_posix())
def test_no_forbidden_imports(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        for name in imported(node):
            assert name not in FORBIDDEN_ANYWHERE, f"{path.name}: import {name}"
    for node in tree.body:  # module level only
        for name in imported(node):
            assert name not in LAZY_ONLY, f"{path.name}: {name} must be imported inside a function"


def test_core_imports_with_qgis_and_sdks_blocked():
    blocked = sorted(FORBIDDEN_ANYWHERE | LAZY_ONLY)
    modules_to_import = [
        ".".join(p.relative_to(PACKAGE.parent).with_suffix("").parts).removesuffix(".__init__")
        for p in modules()
    ]
    code = f"""
import sys
class Block:
    def find_spec(self, name, path=None, target=None):
        if name.split('.')[0] in {blocked!r}:
            raise ImportError('blocked: ' + name)
sys.meta_path.insert(0, Block())
import importlib
for m in {modules_to_import!r}:
    importlib.import_module(m)
"""
    result = subprocess.run([sys.executable, "-c", code], cwd=PACKAGE.parent, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_plugin_entry_point_is_lazy():
    tree = ast.parse((PACKAGE / "__init__.py").read_text(encoding="utf-8"))
    for node in tree.body:
        assert not imported(node), "package __init__ must not import at module level"
