"""API key storage in the QGIS authentication database (QgsAuthManager).

Draft (phase 0): not testable without QGIS. Manual test instructions are in
``docs/vaihe0_kayttajan_tehtavat.md`` (section "QgsAuthManager-avainten testi").

Design (ADR-0004):

* Each provider key (Claude, Mistral, Syke) is one ``APIHeader`` auth configuration in the
  encrypted QGIS auth database, protected by the QGIS master password.
* Only the auth configuration *id* (not secret) is stored in ``QgsSettings``.
* Keys are never written to project files, logs, ``QgsSettings`` or conversion projects.
* For development, ``env_var`` (e.g. ``ANTHROPIC_API_KEY``) is used when no stored key exists.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from qgis.core import QgsApplication, QgsAuthMethodConfig, QgsSettings

SETTINGS_PREFIX = "kaavamaaraysavustaja/authcfg/"
AUTH_METHOD = "APIHeader"


@dataclass(frozen=True)
class KeySpec:
    provider: str  # settings key, e.g. "claude"
    display_name: str  # shown in the QGIS authentication manager
    header: str  # header name stored in the APIHeader config
    env_var: str  # developer fallback


KEYS = {
    "claude": KeySpec("claude", "Kaavamääräysavustaja – Claude API", "x-api-key", "ANTHROPIC_API_KEY"),
    "mistral": KeySpec("mistral", "Kaavamääräysavustaja – Mistral API", "Authorization", "MISTRAL_API_KEY"),
    "syke": KeySpec(
        "syke", "Kaavamääräysavustaja – Syke Ryhti", "Ocp-Apim-Subscription-Key", "RYHTI_API_KEY"
    ),
}


class AuthError(RuntimeError):
    pass


def _ok(result) -> bool:
    # Depending on the QGIS/SIP version the bindings return either a bool or a tuple
    # whose first item is the bool.
    return bool(result[0] if isinstance(result, tuple) else result)


def _auth_manager():
    manager = QgsApplication.authManager()
    if manager.isDisabled():
        raise AuthError(f"QGISin tunnistetietovarasto ei ole käytössä: {manager.disabledMessage()}")
    # Asks for the master password if it has not been given in this session.
    if not manager.setMasterPassword(True):
        raise AuthError("QGISin pääsalasanaa ei annettu.")
    return manager


def stored_authcfg_id(provider: str) -> str:
    return QgsSettings().value(SETTINGS_PREFIX + provider, "", type=str)


def store_api_key(provider: str, api_key: str) -> str:
    """Store or replace the provider key; returns the auth configuration id."""
    spec = KEYS[provider]
    manager = _auth_manager()
    config = QgsAuthMethodConfig(AUTH_METHOD)
    config.setName(spec.display_name)
    config.setConfig(spec.header, api_key)

    existing_id = stored_authcfg_id(provider)
    if existing_id and existing_id in manager.configIds():
        config.setId(existing_id)
        if not _ok(manager.updateAuthenticationConfig(config)):
            raise AuthError("Avaimen päivitys tunnistetietovarastoon epäonnistui.")
    else:
        result = manager.storeAuthenticationConfig(config)
        if isinstance(result, tuple) and len(result) > 1 and hasattr(result[1], "id"):
            config = result[1]
        if not _ok(result) or not config.id():
            raise AuthError("Avaimen tallennus tunnistetietovarastoon epäonnistui.")
    QgsSettings().setValue(SETTINGS_PREFIX + provider, config.id())
    return config.id()


def load_api_key(provider: str) -> str | None:
    """Return the stored key, or the developer environment variable, or None."""
    spec = KEYS[provider]
    authcfg = stored_authcfg_id(provider)
    if authcfg:
        manager = _auth_manager()
        config = QgsAuthMethodConfig()
        result = manager.loadAuthenticationConfig(authcfg, config, True)
        if isinstance(result, tuple) and len(result) > 1 and hasattr(result[1], "config"):
            config = result[1]
        if _ok(result):
            value = config.config(spec.header)
            if value:
                return value
    return os.environ.get(spec.env_var) or None


def remove_api_key(provider: str) -> None:
    authcfg = stored_authcfg_id(provider)
    if authcfg:
        _auth_manager().removeAuthenticationConfig(authcfg)
    QgsSettings().remove(SETTINGS_PREFIX + provider)
