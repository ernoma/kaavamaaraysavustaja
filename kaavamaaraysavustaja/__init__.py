"""Kaavamääräysavustaja.

The package root is also the QGIS plugin directory. ``classFactory`` is the QGIS entry
point; it imports the QGIS-dependent ``plugin`` subpackage lazily so that the pure Python
``core``, ``knowledge``, ``exporters`` and ``validation`` subpackages can be imported and
tested without QGIS.
"""

__version__ = "0.3.2"


def classFactory(iface):  # noqa: N802 (QGIS API name)
    from kaavamaaraysavustaja.plugin.plugin import KaavamaaraysavustajaPlugin

    return KaavamaaraysavustajaPlugin(iface)
