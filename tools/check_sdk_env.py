"""Check that the LLM SDKs can be installed and used in a (QGIS) Python environment.

Run either in the OSGeo4W Shell::

    python tools\\check_sdk_env.py

or in the QGIS Python console (shows QGIS proxy settings too)::

    exec(open(r"C:\\polku\\kaavamaaraysavustaja\\tools\\check_sdk_env.py", encoding="utf-8").read())

Sends no API keys and no content: the connectivity check makes one unauthenticated HTTPS
request per provider and expects HTTP 401/404 (= reachable). Copy the output to
docs/vaihe0_kayttajan_tehtavat.md (section "Tulokset").
"""

import importlib
import os
import platform
import ssl
import sys
import urllib.error
import urllib.request

PACKAGES = [
    "anthropic",
    "mistralai",
    "httpx",
    "httpx2",
    "pydantic",
    "pydantic_core",
    "jiter",
    "yaml",
    "certifi",
]
ENDPOINTS = {
    "Claude": "https://api.anthropic.com/v1/models",
    "Mistral": "https://api.mistral.ai/v1/models",
    "Syke": "https://api.ymparisto.fi/ryhti/plan-public/api/Plan/Validate",
}


def report() -> None:
    print("Python:", sys.version.replace("\n", " "))
    print("Suoritettava:", sys.executable)
    print("Alusta:", platform.platform())
    print("OpenSSL:", ssl.OPENSSL_VERSION)
    try:
        from qgis.core import Qgis, QgsSettings

        print("QGIS:", Qgis.version())
        settings = QgsSettings()
        print(
            "QGIS-välityspalvelin:",
            settings.value("proxy/proxyEnabled"),
            settings.value("proxy/proxyType"),
            settings.value("proxy/proxyHost"),
            settings.value("proxy/proxyPort"),
        )
    except ImportError:
        print("QGIS: ei ladattu (ajettu QGISin ulkopuolella)")
    for name in ("HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY", "REQUESTS_CA_BUNDLE", "SSL_CERT_FILE"):
        value = os.environ.get(name) or os.environ.get(name.lower())
        print(f"{name}:", "asetettu" if value else "-")

    print("\nPaketit:")
    for name in PACKAGES:
        try:
            module = importlib.import_module(name)
            print(f"  {name}: {getattr(module, '__version__', '?')} ({getattr(module, '__file__', '')})")
        except Exception as exc:  # noqa: BLE001 - report every failure
            print(f"  {name}: EI ({type(exc).__name__}: {exc})")

    print("\nYhteydet (ilman avainta; 401/404/405 = palvelu tavoitettavissa):")
    for label, url in ENDPOINTS.items():
        try:
            with urllib.request.urlopen(url, timeout=20) as response:
                print(f"  {label}: HTTP {response.status}")
        except urllib.error.HTTPError as error:
            print(f"  {label}: HTTP {error.code}")
        except Exception as exc:  # noqa: BLE001
            print(f"  {label}: VIRHE {type(exc).__name__}: {exc}")

    try:
        import anthropic

        client = anthropic.Anthropic(api_key="sk-ant-invalid-test-key", max_retries=0)
        try:
            client.models.list()
        except anthropic.AuthenticationError:
            print("\nanthropic-SDK: yhteys toimii (odotettu 401 virheellisellä testiavaimella)")
        except Exception as exc:  # noqa: BLE001
            print(f"\nanthropic-SDK: VIRHE {type(exc).__name__}: {exc}")
    except ImportError:
        pass


report()
