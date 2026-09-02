"""
Configuración dinámica de base de datos para SIGET.
Lee/escribe config/database.json; por defecto SQLite en instalaciones nuevas.
"""
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / 'config'
CONFIG_FILE = CONFIG_DIR / 'database.json'

DEFAULT_SQLITE = {
    'engine': 'sqlite',
    'name': str(BASE_DIR / 'db.sqlite3'),
}


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


def build_django_database(config=None):
    cfg = config or load_database_config()
    engine = cfg.get('engine', 'sqlite')
    if engine == 'postgresql':
        return {
            'default': {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': cfg.get('name', 'titulacion'),
                'USER': cfg.get('user', ''),
                'PASSWORD': cfg.get('password', ''),
                'HOST': cfg.get('host', 'localhost'),
                'PORT': cfg.get('port', '5432'),
            }
        }
    return {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': cfg.get('name', str(BASE_DIR / 'db.sqlite3')),
        }
    }


def test_database_connection(config):
    """Prueba la conexión sin persistir."""
    from django.db import connections
    from django.conf import settings
    import django

    databases = build_django_database(config)
    settings.DATABASES = databases
    connections.close_all()
    conn = connections['default']
    conn.ensure_connection()
    return True
