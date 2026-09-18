"""
Migración de datos entre motores de BD (SQLite ↔ PostgreSQL).

Solo persiste la nueva config cuando:
1) hay conexión segura al destino,
2) el destino está vacío de datos de aplicación,
3) dump + migrate + load + verificación terminan bien.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from django.apps import apps
from django.core.management import call_command
from django.db import connections

from titulacion.db_config import (
    MIGRATION_TARGET_ALIAS,
    configs_equivalent,
    destination_looks_empty,
    load_database_config,
    normalize_database_config,
    save_database_config,
    temporary_database_alias,
    test_database_connection,
)

# Apps de negocio a volcar (más contenttypes/auth vía natural keys implícitas en FKs).
DUMP_APPS = (
    'contenttypes',
    'auth',
    'administracion',
    'expediente',
    'alumnos',
    'oficina_titulacion',
    'finanzas',
    'centro_computo',
    'centro_informacion',
)

DUMP_EXCLUDE = (
    'sessions.session',
    'admin.logentry',
)

# Modelos para verificar que la carga preservó los datos.
VERIFY_MODELS = (
    ('administracion', 'Usuario'),
    ('administracion', 'Departamento'),
    ('administracion', 'Carrera'),
    ('administracion', 'Profesor'),
    ('expediente', 'PlanEstudios'),
    ('expediente', 'Modalidad'),
    ('expediente', 'TipoDocumento'),
    ('expediente', 'Expediente'),
    ('expediente', 'Documento'),
    ('alumnos', 'PerfilAlumno'),
    ('alumnos', 'Notificacion'),
)


class DatabaseMigrationError(Exception):
    """Error controlado durante la migración de BD."""


def _count_models(using: str) -> dict[str, int]:
    counts = {}
    for app_label, model_name in VERIFY_MODELS:
        try:
            model = apps.get_model(app_label, model_name)
        except LookupError:
            continue
        key = f'{app_label}.{model_name}'
        try:
            counts[key] = model.objects.using(using).count()
        except Exception:
            counts[key] = -1
    return counts


def _dump_source_fixture(path: Path, source_alias: str = 'default') -> None:
    """Exporta fixture JSON desde la BD activa (source_alias)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as out:
        call_command(
            'dumpdata',
            *DUMP_APPS,
            database=source_alias,
            exclude=list(DUMP_EXCLUDE),
            natural_foreign=True,
            natural_primary=True,
            indent=2,
            stdout=out,
            verbosity=0,
        )


def _ensure_destination_empty(alias: str) -> None:
    if not destination_looks_empty(alias):
        raise DatabaseMigrationError(
            'La base de datos destino ya contiene datos de la aplicación. '
            'Use una BD vacía para no sobrescribir otra instalación.'
        )


def migrate_database_data(target_config, source_alias: str = 'default') -> dict:
    """
    Migra todos los datos de `source_alias` hacia la BD descrita por `target_config`.

    No guarda la config. El llamador debe llamar save_database_config solo si OK.

    Returns:
        dict con resumen (counts_before, counts_after, fixture_bytes).
    """
    target_config = normalize_database_config(target_config)
    current = normalize_database_config(load_database_config())

    if configs_equivalent(current, target_config):
        return {
            'skipped': True,
            'reason': 'equivalent',
            'message': 'La configuración es la misma; no hay nada que migrar.',
        }

    # 1) Conexión segura al destino (falla temprano, sin tocar JSON).
    try:
        test_database_connection(target_config, alias=MIGRATION_TARGET_ALIAS)
    except Exception as exc:
        raise DatabaseMigrationError(
            f'No se pudo establecer conexión segura con la nueva base de datos: {exc}'
        ) from exc

    counts_before = _count_models(source_alias)
    fixture_path = None

    with temporary_database_alias(MIGRATION_TARGET_ALIAS, target_config):
        # 2) Destino vacío (antes de migrate: si ya hay tablas con datos, abortar).
        _ensure_destination_empty(MIGRATION_TARGET_ALIAS)

        # 3) Dump desde origen
        tmp = tempfile.NamedTemporaryFile(
            prefix='siget_db_migrate_',
            suffix='.json',
            delete=False,
        )
        fixture_path = Path(tmp.name)
        tmp.close()
        try:
            _dump_source_fixture(fixture_path, source_alias=source_alias)
            if fixture_path.stat().st_size < 3:
                raise DatabaseMigrationError('El volcado de datos quedó vacío; se abortó la migración.')

            # 4) Schema en destino
            call_command(
                'migrate',
                database=MIGRATION_TARGET_ALIAS,
                interactive=False,
                verbosity=0,
            )

            # Tras migrate, Django puede haber creado contenttypes/permissions.
            # Vaciar datos de app otra vez por si migrate dejó algo inesperado
            # en tablas críticas (no debería), y cargar fixture limpio.
            # flush borra datos manteniendo schema — necesario para loaddata limpio.
            call_command(
                'flush',
                database=MIGRATION_TARGET_ALIAS,
                interactive=False,
                verbosity=0,
            )

            # 5) Cargar datos
            call_command(
                'loaddata',
                str(fixture_path),
                database=MIGRATION_TARGET_ALIAS,
                verbosity=0,
            )

            # 6) Verificar conteos
            counts_after = _count_models(MIGRATION_TARGET_ALIAS)
            mismatches = []
            for key, before in counts_before.items():
                after = counts_after.get(key, -1)
                if before < 0 or after < 0:
                    mismatches.append(f'{key}: no se pudo contar')
                elif before != after:
                    mismatches.append(f'{key}: origen={before}, destino={after}')
            if mismatches:
                raise DatabaseMigrationError(
                    'La verificación de datos falló tras la carga:\n- '
                    + '\n- '.join(mismatches)
                )

            return {
                'skipped': False,
                'counts_before': counts_before,
                'counts_after': counts_after,
                'fixture_bytes': fixture_path.stat().st_size,
                'message': 'Datos migrados correctamente a la nueva base de datos.',
            }
        finally:
            if fixture_path is not None:
                try:
                    fixture_path.unlink(missing_ok=True)
                except OSError:
                    pass


def apply_database_config_change(new_config) -> dict:
    """
    Punto de entrada para la vista admin.

    - Si la config es equivalente: guarda (idempotente) y no migra.
    - Si cambia: migra solo tras conexión OK; guarda JSON solo al final.
    - Si falla: no modifica database.json.
    """
    new_config = normalize_database_config(new_config)
    current = normalize_database_config(load_database_config())

    if configs_equivalent(current, new_config):
        save_database_config(new_config)
        return {
            'ok': True,
            'migrated': False,
            'message': 'La configuración de base de datos no cambió.',
        }

    try:
        result = migrate_database_data(new_config)
    except DatabaseMigrationError:
        raise
    except Exception as exc:
        raise DatabaseMigrationError(
            f'Error inesperado durante la migración: {exc}'
        ) from exc

    # Solo aquí se persiste la nueva config
    save_database_config(new_config)
    return {
        'ok': True,
        'migrated': not result.get('skipped'),
        'message': (
            result.get('message')
            or 'Configuración guardada. Reinicie el servicio del sistema para aplicar los cambios.'
        ),
        'details': result,
    }
