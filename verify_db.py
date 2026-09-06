import os
import django
import codecs
import re

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'titulacion.settings')
django.setup()

from django.apps import apps
from administracion.models import Usuario

def verify_counts():
    with codecs.open('listado_completo_bd.txt', 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    print("--- VERIFICACION DE BASE DE DATOS ---")
    
    # Check total users
    for line in lines:
        if line.startswith('Total de usuarios:'):
            expected = int(line.split(':')[1].strip())
            actual = Usuario.objects.count()
            status = 'OK' if expected == actual else f'FALLO (Real: {actual})'
            print(f"Usuarios: Esperado {expected} | {status}")
            break
            
    # Check models
    pattern = re.compile(r'\[(.*?)\] (.*?) \((\d+) registros\)')
    for line in lines:
        match = pattern.search(line)
        if match:
            app_label = match.group(1).lower()
            model_name = match.group(2)
            expected_count = int(match.group(3))
            
            try:
                model = apps.get_model(app_label, model_name)
                actual_count = model.objects.count()
                status = 'OK' if expected_count == actual_count else f'FALLO (Real: {actual_count})'
                print(f"{app_label}.{model_name}: Esperado {expected_count} | {status}")
            except Exception as e:
                print(f"Error al verificar {app_label}.{model_name}: {e}")

if __name__ == '__main__':
    verify_counts()
