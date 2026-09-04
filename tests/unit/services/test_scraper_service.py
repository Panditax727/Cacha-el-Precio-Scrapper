# tests/unit/services/test_scraper_service.py
"""
El servicio se prueba entero sin red y sin base de datos, usando el
repositorio en memoria y scrapers falsos.
"""

import pytest

from scraper.domain.product import Product
from scraper.infrastructure.database.repositories.product_repository import (
    RepositorioEnMemoria,
)
from scraper.services.scraper_service import ScraperService


def prod(external_id="A1", precio=79990, store="converse"):
    return Product(external_id=external_id, store=store, name="Zapatilla",
                   brand="Converse", price=precio, product_url=f"https://x/{external_id}")


class ScraperFalso:
    def __init__(self, por_url=None, revienta_en=None):
        self.por_url = por_url or {}
        self.revienta_en = revienta_en or set()

    def scrape(self, url):
        if url in self.revienta_en:
            raise RuntimeError("caida simulada")
        return self.por_url.get(url, [])


def test_barrido_normal():
    repo = RepositorioEnMemoria()
    s = ScraperService({"converse": ScraperFalso({"u1": [prod("A1")], "u2": [prod("A2")]})}, repo)
    r = s.ejecutar("converse", ["u1", "u2"])
    assert r.productos_extraidos == 2
    assert r.guardados == 2
    assert r.cambios_de_precio == 2      # primera vez, todo es cambio
    assert r.urls_fallidas == []
    assert len(repo) == 2


def test_una_url_rota_no_aborta_el_barrido():
    """Lo importante en un barrido nocturno de cientos de productos."""
    repo = RepositorioEnMemoria()
    sc = ScraperFalso({"ok1": [prod("A1")], "ok2": [prod("A2")]}, revienta_en={"malo"})
    s = ScraperService({"converse": sc}, repo)
    r = s.ejecutar("converse", ["ok1", "malo", "ok2"])
    assert r.guardados == 2
    assert r.urls_fallidas == ["malo"]
    assert r.urls_ok == 2


def test_url_sin_producto_no_es_un_fallo_de_descarga():
    """
    Descatalogado o sin precio publicado no es lo mismo que "no pude
    descargar". Mezclarlos oculta que la tienda cambio el maquetado
    detras de un monton de productos retirados.
    """
    repo = RepositorioEnMemoria()
    s = ScraperService({"converse": ScraperFalso({"vacia": []})}, repo)
    r = s.ejecutar("converse", ["vacia"])
    assert r.sin_producto == ["vacia"]
    assert r.urls_fallidas == []
    assert r.urls_ok == 1              # se descargo bien
    assert r.guardados == 0


def test_separa_los_dos_tipos_de_problema():
    repo = RepositorioEnMemoria()
    sc = ScraperFalso({"ok": [prod("A1")], "vacia": []}, revienta_en={"caida"})
    s = ScraperService({"converse": sc}, repo)
    r = s.ejecutar("converse", ["ok", "vacia", "caida"])
    assert r.guardados == 1
    assert r.sin_producto == ["vacia"]
    assert r.urls_fallidas == ["caida"]
    assert "1 sin producto" in r.resumen()
    assert "1 fallos de descarga" in r.resumen()


def test_segundo_barrido_sin_cambios_no_cuenta_cambios_de_precio():
    repo = RepositorioEnMemoria()
    sc = ScraperFalso({"u1": [prod("A1", 79990)]})
    s = ScraperService({"converse": sc}, repo)
    s.ejecutar("converse", ["u1"])
    r = s.ejecutar("converse", ["u1"])
    assert r.guardados == 1
    assert r.cambios_de_precio == 0
    assert len(repo.historial("converse", "A1")) == 1


def test_detecta_la_bajada_de_precio():
    repo = RepositorioEnMemoria()
    sc = ScraperFalso({"u1": [prod("A1", 79990)]})
    s = ScraperService({"converse": sc}, repo)
    s.ejecutar("converse", ["u1"])
    sc.por_url["u1"] = [prod("A1", 59990)]
    r = s.ejecutar("converse", ["u1"])
    assert r.cambios_de_precio == 1
    assert [o.price for o in repo.historial("converse", "A1")] == [59990, 79990]


def test_tienda_desconocida():
    s = ScraperService({}, RepositorioEnMemoria())
    with pytest.raises(KeyError, match="nike"):
        s.ejecutar("nike", ["u1"])


def test_el_resumen_es_legible():
    repo = RepositorioEnMemoria()
    s = ScraperService({"converse": ScraperFalso({"u1": [prod("A1")]})}, repo)
    r = s.ejecutar("converse", ["u1", "otra"])
    # "otra" se descarga bien pero no trae producto: cuenta como URL ok.
    assert "[converse]" in r.resumen()
    assert "2/2 URLs" in r.resumen()
    assert "1 sin producto" in r.resumen()
