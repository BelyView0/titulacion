#!/usr/bin/env python
"""
Migra catálogos y usuarios operativos desde PostgreSQL (titulacion_2026) a SQLite.

Incluye: departamentos, carreras, profesores, jefes de departamento,
planes, modalidades, tipos de documento y usuarios de roles operativos.

Excluye: alumnos, administrador, expedientes y documentos de alumnos.

Uso:
    python migrar_desde_postgresql.py
"""
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / 'config' / 'database.json'
SQLITE_DB = BASE_DIR / 'db.sqlite3'
FIXTURE_FILE = BASE_DIR / 'fixtures' / 'migracion_catalogos.json'

PG_CONFIG = {
    'engine': 'postgresql',
    'name': os.environ.get('PG_NAME', 'titulacion_2026'),
    'user': os.environ.get('PG_USER', 'belyview'),
    'password': os.environ.get('PGPASSWORD', ''),
    'host': os.environ.get('PG_HOST', 'localhost'),
    'port': os.environ.get('PG_PORT', '5432'),
}

ROLES_EXCLUIDOS = {'ALUMNO', 'ADMIN'}
ROLE_MAP = {
    'ESCOLARES': 'OFICINA_TITULACION',
    'ACADEMICO': 'OFICINA_TITULACION',
    'JEFE_PROYECTO': 'JEFE_ACADEMIA',
}

EXPORT_ORDER = [
    ('administracion', 'Departamento'),
    ('administracion', 'Carrera'),
    ('expediente', 'PlanEstudios'),
    ('expediente', 'Modalidad'),
    ('expediente', 'TipoDocumento'),
    ('administracion', 'Profesor'),
    ('administracion', 'ConfiguracionInstitucional'),
    ('administracion', 'JefeDepartamento'),
]


def run(cmd, **kwargs):
    print('\n>>', ' '.join(str(c) for c in cmd))
    result = subprocess.run(cmd, cwd=BASE_DIR, **kwargs)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def write_db_config(config):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def remove_db_config():
    if CONFIG_FILE.exists():
        CONFIG_FILE.unlink()


def backup_sqlite():
    if SQLITE_DB.exists():
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup = BASE_DIR / f'db.sqlite3.backup_{stamp}'
        shutil.copy2(SQLITE_DB, backup)
        print(f'Respaldo SQLite: {backup.name}')


def exportar_catalogos_desde_pg():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'titulacion.settings')
    write_db_config(PG_CONFIG)

    import django
    from django.apps import apps
    from django.core import serializers

    django.setup()

    objetos = []
    for app_label, model_name in EXPORT_ORDER:
        model = apps.get_model(app_label, model_name)
        qs = model.objects.all().order_by('pk')
        objetos.extend(qs)
        print(f'  {app_label}.{model_name}: {qs.count()}')

    Usuario = apps.get_model('administracion', 'Usuario')
    usuarios = list(
        Usuario.objects.exclude(rol__in=ROLES_EXCLUIDOS).order_by('pk')
    )
    for usuario in usuarios:
        usuario.rol = ROLE_MAP.get(usuario.rol, usuario.rol)
    objetos.extend(usuarios)
    print(f'  administracion.Usuario (operativos): {len(usuarios)}')

    FIXTURE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with FIXTURE_FILE.open('w', encoding='utf-8') as stream:
        serializers.serialize(
            'json',
            objetos,
            indent=2,
            use_natural_foreign_keys=True,
            use_natural_primary_keys=True,
            stream=stream,
        )

    size_kb = FIXTURE_FILE.stat().st_size / 1024
    print(f'Exportación: {FIXTURE_FILE.name} ({size_kb:.1f} KB)')


def main():
    print('=' * 60)
    print('  MIGRACIÓN SELECTIVA PostgreSQL -> SQLite')
    print('=' * 60)

    print('\n[1/4] Exportando catálogos y usuarios operativos desde PostgreSQL...')
    exportar_catalogos_desde_pg()

    print('\n[2/4] Preparando SQLite local...')
    backup_sqlite()
    if SQLITE_DB.exists():
        SQLITE_DB.unlink()
    remove_db_config()
    run([sys.executable, 'manage.py', 'migrate', '--noinput'])

    print('\n[3/4] Importando datos selectivos...')
    run([sys.executable, 'manage.py', 'loaddata', str(FIXTURE_FILE)])

    print('\n[4/4] Verificando conteos...')
    subprocess.run(
        [sys.executable, '-c', '''
import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "titulacion.settings")
django.setup()
from administracion.models import Usuario, Carrera, Departamento, Profesor
from expediente.models import PlanEstudios, Modalidad, TipoDocumento, Expediente, Documento
from django.db import connection
print("  Motor:", connection.settings_dict["ENGINE"])
print("  Usuarios operativos:", Usuario.objects.exclude(rol__in=["ALUMNO", "ADMIN"]).count())
print("  Alumnos:", Usuario.objects.filter(rol="ALUMNO").count(), "(debe ser 0)")
print("  Admins:", Usuario.objects.filter(rol="ADMIN").count(), "(solo adminITA)")
print("  Departamentos:", Departamento.objects.count())
print("  Carreras:", Carrera.objects.count())
print("  Profesores:", Profesor.objects.count())
print("  Planes:", PlanEstudios.objects.count())
print("  Modalidades:", Modalidad.objects.count())
print("  Tipos documento:", TipoDocumento.objects.count())
print("  Expedientes:", Expediente.objects.count(), "(debe ser 0)")
print("  Documentos alumno:", Documento.objects.count(), "(debe ser 0)")
for u in Usuario.objects.exclude(rol__in=["ALUMNO", "ADMIN"]).order_by("username"):
    print(f"    - {u.username} ({u.rol})")
'''],
        cwd=BASE_DIR,
    )

    print('\n' + '=' * 60)
    print('  MIGRACIÓN SELECTIVA COMPLETADA')
    print('=' * 60)
    print('Reinicie el servidor Django para aplicar los cambios.')


if __name__ == '__main__':
    main()
