import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'titulacion.settings')
django.setup()

from administracion.models import Departamento, JefeDepartamento, Genero

def run():
    departamentos = Departamento.objects.all()
    if not departamentos.exists():
        print("No hay departamentos en la base de datos.")
        return

    for depto in departamentos:
        if hasattr(depto, 'jefe_asignado') and depto.jefe_asignado:
            print(f"[{depto.nombre}] ya tiene jefe asignado.")
            continue

        if 'Sistemas' in depto.nombre:
            nombre = 'Miquelina'
            ap_pat = 'Sánchez'
            ap_mat = 'Pulido'
            titulo = 'M.C.'
            genero = Genero.FEMENINO
        else:
            nombre = 'Jefe Provisional'
            ap_pat = 'Depto'
            ap_mat = depto.clave
            titulo = 'Ing.'
            genero = Genero.MASCULINO

        JefeDepartamento.objects.create(
            departamento=depto,
            titulo_academico=titulo,
            nombre=nombre,
            apellido_paterno=ap_pat,
            apellido_materno=ap_mat,
            genero=genero
        )
        print(f"Creado jefe provisional para: {depto.nombre}")

if __name__ == '__main__':
    run()
