"""Manifest (``knowledge/manifest.yaml``) loading and checksum verification."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

import yaml

ENV_KNOWLEDGE_DIR = "KMA_KNOWLEDGE_DIR"
MANIFEST_NAME = "manifest.yaml"


class KnowledgeIntegrityError(RuntimeError):
    """A knowledge base file is missing or its checksum does not match the manifest."""


def knowledge_dir() -> Path:
    """Return the active knowledge directory.

    ``KMA_KNOWLEDGE_DIR`` overrides the default, which is the ``knowledge/`` folder next to
    the package (repository layout; the plugin is installed as a link to the package).
    """
    override = os.environ.get(ENV_KNOWLEDGE_DIR)
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2] / "knowledge"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(directory: Path | None = None, *, verify: bool = True) -> dict[str, Any]:
    directory = directory or knowledge_dir()
    path = directory / MANIFEST_NAME
    if not path.exists():
        raise KnowledgeIntegrityError(f"Tietopohjan manifestia ei löydy: {path}")
    with path.open(encoding="utf-8") as handle:
        manifest = yaml.safe_load(handle)
    if verify:
        problems = verify_manifest(manifest, directory)
        if problems:
            raise KnowledgeIntegrityError("Tietopohjan eheystarkistus epäonnistui:\n" + "\n".join(problems))
    return manifest


def verify_manifest(manifest: dict[str, Any], directory: Path | None = None) -> list[str]:
    """Check every file listed in ``tiedostot`` against its sha256; return problems."""
    directory = directory or knowledge_dir()
    problems = []
    for relative, expected in (manifest.get("tiedostot") or {}).items():
        path = directory / relative
        if not path.exists():
            problems.append(f"puuttuu: {relative}")
        elif sha256_file(path) != expected:
            problems.append(f"tarkistussumma ei täsmää: {relative}")
    return problems
