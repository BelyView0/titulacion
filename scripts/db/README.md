# Scripts de base de datos (ops / legado)

La **migración completa** al cambiar de motor (SQLite ↔ PostgreSQL) se hace desde el Admin:
**Configuración de base de datos** (usa `titulacion/db_migrate.py`).

Esta carpeta solo tiene utilidades offline:

- `migrar_desde_postgresql.py` — legado: copia selectiva de catálogos PG → SQLite (sin alumnos/expedientes).
- `restaurar_bd.bat` / `restaurar_bd.ps1` — restauran un `.dump` de PostgreSQL con `pg_restore`.
- `verify_db.py` — compara conteos contra `listado_completo_bd.txt` en la raíz del proyecto.

Coloque el archivo `.dump` en la **raíz del repositorio** (junto a `manage.py`) o en esta carpeta.
