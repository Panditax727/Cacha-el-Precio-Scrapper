# src/scraper/services/scraper_service.py
"""
Orquesta un barrido: scrapear una tienda y persistir el resultado.

El servicio no sabe de HTML ni de SQL. Recibe scrapers y un repositorio
ya construidos y solo coordina. Eso es lo que permite ejecutarlo entero
en las pruebas sin red y sin base de datos.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

from scraper.domain.product import Product

log = logging.getLogger(__name__)


class Scraper(Protocol):
    def scrape(self, url: str) -> list[Product]: ...


class Repositorio(Protocol):
    def guardar(self, producto: Product) -> bool: ...


@dataclass
class ResultadoBarrido:
    """Lo que hay que poder mirar despues de un barrido nocturno."""

    tienda: str
    urls_pedidas: int = 0
    productos_extraidos: int = 0
    guardados: int = 0
    cambios_de_precio: int = 0
    urls_fallidas: list[str] = field(default_factory=list)   # no se pudo descargar
    sin_producto: list[str] = field(default_factory=list)    # bajo, pero no hay producto
    segundos: float = 0.0

    @property
    def urls_ok(self) -> int:
        """Descargadas correctamente, tengan producto o no."""
        return self.urls_pedidas - len(self.urls_fallidas)

    def resumen(self) -> str:
        return (
            f"[{self.tienda}] {self.urls_ok}/{self.urls_pedidas} URLs, "
            f"{self.guardados} guardados, {self.cambios_de_precio} cambios de precio, "
            f"{len(self.sin_producto)} sin producto, "
            f"{len(self.urls_fallidas)} fallos de descarga, {self.segundos:.1f}s"
        )


class ScraperService:
    # Mapping y no dict: dict es invariante en el valor, asi que un
    # dict[str, ConverseScraper] NO encajaria aqui aunque cumpla el
    # protocolo. Mapping si es covariante.
    def __init__(self, scrapers: Mapping[str, Scraper], repositorio: Repositorio) -> None:
        self._scrapers: Mapping[str, Scraper] = scrapers
        self._repo = repositorio

    def tiendas(self) -> list[str]:
        return sorted(self._scrapers)

    def ejecutar(self, tienda: str, urls: list[str]) -> ResultadoBarrido:
        """
        Barre una tienda. No lanza excepcion por una URL rota: la anota
        en urls_fallidas y sigue, porque un barrido nocturno de cientos
        de productos no puede morir por uno.
        """
        scraper = self._scrapers.get(tienda)
        if scraper is None:
            raise KeyError(f"no hay scraper registrado para la tienda {tienda!r}")

        res = ResultadoBarrido(tienda=tienda, urls_pedidas=len(urls))
        inicio = time.monotonic()

        for url in urls:
            try:
                productos = scraper.scrape(url)
            except Exception:
                # Incluye DescargaFallida y cualquier fallo inesperado del
                # scraper: en ambos casos la URL no dio datos por un
                # problema tecnico, no porque el producto no exista.
                log.warning("no se pudo procesar %s", url)
                res.urls_fallidas.append(url)
                continue

            if not productos:
                # Se descargo bien: el producto esta descatalogado o sin
                # precio. No es un fallo del scraper.
                res.sin_producto.append(url)
                continue

            res.productos_extraidos += len(productos)
            for producto in productos:
                try:
                    if self._repo.guardar(producto):
                        res.cambios_de_precio += 1
                    res.guardados += 1
                except Exception:
                    # Un fallo al guardar no debe perder el resto del barrido.
                    log.exception("no se pudo guardar %s/%s", producto.store, producto.external_id)

        res.segundos = time.monotonic() - inicio
        log.info("%s", res.resumen())
        return res
