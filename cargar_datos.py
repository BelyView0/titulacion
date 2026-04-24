import os
import django
from django.core.management import call_command

def run():
    print("==================================================")
    print("Iniciando restauración de la base de datos...")
    print("==================================================")
    
    # 1. Configurar el entorno de Django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'titulacion.settings')
    django.setup()
    
    json_file = 'datos_iniciales.json'
    
    if not os.path.exists(json_file):
        print(f"Error: No se encontró el archivo '{json_file}'.")
        print("Asegúrate de que el archivo JSON está en la misma carpeta que este script.")
        return

    try:
        # 2. Ejecutar las migraciones por si el compañero tiene una base de datos vacía
        print("\n[1/2] Aplicando migraciones necesarias...")
        call_command('migrate', interactive=False)
        
        # 3. Cargar los datos desde el JSON
        print("\n[2/2] Cargando datos desde", json_file, "...")
        call_command('loaddata', json_file)
        
        print("\n==================================================")
        print("¡Éxito! Todos los datos fueron registrados correctamente.")
        print("Tus compañeros ahora tienen los mismos usuarios, expedientes y configuración.")
        print("==================================================")
    except Exception as e:
        print(f"\nOcurrió un error al cargar los datos: {e}")

if __name__ == '__main__':
    run()
