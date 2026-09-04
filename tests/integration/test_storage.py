# tests/integration/test_storage.py
"""
Reservado para el almacenamiento de imagenes en S3.

Todavia no hay implementacion: src/scraper/infrastructure/storage/
sigue vacio. Cuando exista, aqui van las pruebas contra un bucket real
o contra un doble local, siguiendo el mismo patron que
test_database.py: saltar si no hay credenciales.
"""

import pytest

pytest.skip("almacenamiento S3 aun no implementado", allow_module_level=True)
