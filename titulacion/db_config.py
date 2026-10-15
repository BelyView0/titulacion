"""
Configuración dinámica de base de datos para SIGET.
Lee/escribe config/database.json; por defecto SQLite en instalaciones nuevas.
"""
import json
from contextlib import contextmanager
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / 'config'
CONFIG_FILE = CONFIG_DIR / 'database.json'

MIGRATION_TARGET_ALIAS = 'migration_target'

DEFAULT_SQLITE = {
    'engine': 'sqlite',
    'name': str(BASE_DIR / 'db.sqlite3'),
}

# Claves relevantes para comparar configs (sin importar orden).
_CONFIG_KEYS = ('engine', 'name', 'user', 'password', 'host', 'port')


def load_database_config():
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data.get('engine'):
                    return data
        except (json.JSONDecodeError, OSError):
            pass
    return dict(DEFAULT_SQLITE)


def save_database_config(config):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def normalize_database_config(config):
    """Normaliza el dict de config para comparación y persistencia."""
    cfg = dict(config or {})
    engine = (cfg.get('engine') or 'sqlite').strip().lower()
    out = {'engine': engine}
    if engine == 'postgresql':
        out.update({
            'name': (cfg.get('name') or '').strip(),
            'user': (cfg.get('user') or '').strip(),
            'password': cfg.get('password') or '',
            'host': (cfg.get('host') or 'localhost').strip(),
            'port': str(cfg.get('port') or '5432').strip(),
        })
    else:
        name = (cfg.get('name') or '').strip()
        out['name'] = name or str(BASE_DIR / 'db.sqlite3')
    return out


def configs_equivalent(a, b):
    """True si ambas configs apuntan al mismo destino efectivo."""
    na = normalize_database_config(a)
    nb = normalize_database_config(b)
    if na.get('engine') != nb.get('engine'):
        return False
    if na['engine'] == 'postgresql':
        return all(na.get(k) == nb.get(k) for k in _CONFIG_KEYS)
    # SQLite: comparar rutas resueltas
    try:
        return Path(na['name']).resolve() == Path(nb['name']).resolve()
    except OSError:
        return na.get('name') == nb.get('name')


def build_django_database(config=None, alias='default'):
    """Construye el dict DATABASES para un alias (default o temporal)."""
    cfg = normalize_database_config(config or load_database_config())
    engine = cfg.get('engine', 'sqlite')
    if engine == 'postgresql':
        entry = {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': cfg.get('name', 'titulacion'),
            'USER': cfg.get('user', ''),
            'PASSWORD': cfg.get('password', ''),
            'HOST': cfg.get('host', 'localhost'),
            'PORT': cfg.get('port', '5432'),
        }
    else:
        entry = {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': cfg.get('name', str(BASE_DIR / 'db.sqlite3')),
        }
    return {alias: entry}


def register_database_alias(alias, config):
    """Registra (o reemplaza) un alias en settings.DATABASES sin tocar default."""
    from django.conf import settings
    from django.db import connections

    entry = build_django_database(config, alias=alias)[alias]
    settings.DATABASES[alias] = entry
    # Forzar recreación del wrapper de conexión si ya existía
    if alias in connections:
        try:
            connections[alias].close()
        except Exception:
            pass
        try:
            del connections[alias]
        except Exception:
            pass
    return entry


def unregister_database_alias(alias):
    """Cierra y elimina un alias temporal de settings.DATABASES."""
    from django.conf import settings
    from django.db import connections

    if alias in connections:
        try:
            connections[alias].close()
        except Exception:
            pass
        try:
            del connections[alias]
        except Exception:
            pass
    settings.DATABASES.pop(alias, None)


@contextmanager
def temporary_database_alias(alias, config):
    """Context manager: registra alias, cede control, limpia al salir."""
    register_database_alias(alias, config)
    try:
        yield alias
    finally:
        unregister_database_alias(alias)


def test_database_connection(config, alias=MIGRATION_TARGET_ALIAS):
    """
    Prueba la conexión sin persistir ni reemplazar `default`.
    Usa un alias temporal, ejecuta SELECT 1 y lo limpia.
    """
    from django.db import connections

    with temporary_database_alias(alias, config):
        conn = connections[alias]
        conn.ensure_connection()
        with conn.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
    return True


# Modelos usados para detectar si el destino ya tiene datos de la app.
CRITICAL_MODELS_FOR_EMPTY_CHECK = (
    ('administracion', 'Usuario'),
    ('administracion', 'Departamento'),
    ('expediente', 'Expediente'),
    ('expediente', 'PlanEstudios'),
)


def destination_looks_empty(alias=MIGRATION_TARGET_ALIAS):
    """
    True si el destino no tiene filas en tablas críticas de la app.
    Si las tablas aún no existen (BD fresca), se considera vacía.
    """
    from django.apps import apps
    from django.db import connections

    conn = connections[alias]
    # Si no hay tablas de Django, está vacía
    table_names = set(conn.introspection.table_names())
    if not table_names:
        return True

    for app_label, model_name in CRITICAL_MODELS_FOR_EMPTY_CHECK:
        try:
            model = apps.get_model(app_label, model_name)
        except LookupError:
            continue
        table = model._meta.db_table
        if table not in table_names:
            continue
        try:
            if model.objects.using(alias).exists():
                return False
        except Exception:
            # Tabla existe pero no se puede consultar → no asumir vacío seguro
            return False
    return True
