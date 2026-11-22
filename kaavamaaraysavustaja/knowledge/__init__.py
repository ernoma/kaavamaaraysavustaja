"""Knowledge base (tietopohja) loading, integrity checks and lookups.

The knowledge base is versioned data in the repository folder ``knowledge/`` (ADR-0003).
It is built by ``tools/build_knowledge.py``; this package only reads it and needs nothing
beyond the standard library and PyYAML (bundled with QGIS).
"""

from kaavamaaraysavustaja.knowledge.codelists import Code, CodelistIndex
from kaavamaaraysavustaja.knowledge.manifest import (
    KnowledgeIntegrityError,
    knowledge_dir,
    load_manifest,
    verify_manifest,
)

__all__ = [
    "Code",
    "CodelistIndex",
    "KnowledgeIntegrityError",
    "knowledge_dir",
    "load_manifest",
    "verify_manifest",
]
