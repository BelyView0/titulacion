import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'titulacion.settings')
django.setup()

from administracion.models import Profesor, Departamento

def crear_profesores():
    # Obtener o crear un departamento
    departamento, created = Departamento.objects.get_or_create(
        clave='SIST-01',
        defaults={'nombre': 'Sistemas y Computación'}
    )

    profesores_data = [
        {
            'first_name': 'JUAN',
            'last_name': 'PÉREZ',
            'apellido_materno': 'GARCÍA',
            'titulo_academico': 'Ingeniero en Sistemas Computacionales',
            'cedula': '12345678',
            'email': 'juan.perez@example.com',
            'departamento': departamento
        },
        {
            'first_name': 'MARÍA',
            'last_name': 'GÓMEZ',
            'apellido_materno': 'LÓPEZ',
            'titulo_academico': 'Maestra en Ciencias de la Computación',
            'cedula': '87654321',
            'email': 'belyersua24@gmail.com',
            'departamento': departamento
        },
        {
            'first_name': 'CARLOS',
            'last_name': 'RUIZ',
            'apellido_materno': 'SÁNCHEZ',
            'titulo_academico': 'Doctor en Tecnologías de la Información',
            'cedula': '11223344',
            'email': 'carlos.ruiz@example.com',
            'departamento': departamento
        },
        {
            'first_name': 'ANA',
            'last_name': 'MARTÍNEZ',
            'apellido_materno': 'DÍAZ',
            'titulo_academico': 'Ingeniera en Software',
            'cedula': '44332211',
            'email': 'ana.martinez@example.com',
            'departamento': departamento
        }
    ]

    for data in profesores_data:
        Profesor.objects.get_or_create(
            cedula=data['cedula'],
            defaults=data
        )
    print("Profesores creados con éxito.")

if __name__ == '__main__':
    crear_profesores()
