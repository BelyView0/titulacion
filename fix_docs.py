import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'titulacion.settings')
django.setup()

from expediente.models import Modalidad, TipoDocumento, Expediente, Documento

def run():
    mod_fuente = Modalidad.objects.filter(nombre__icontains='2009').first()
    mod_destino = Modalidad.objects.filter(nombre__icontains='2004').first()

    if mod_fuente and mod_destino:
        for d in TipoDocumento.objects.filter(modalidad=mod_fuente):
            TipoDocumento.objects.get_or_create(
                modalidad=mod_destino, 
                nombre=d.nombre, 
                defaults={
                    'descripcion': d.descripcion, 
                    'es_obligatorio': d.es_obligatorio, 
                    'orden': d.orden, 
                    'formatos_permitidos': d.formatos_permitidos, 
                    'es_fotografia': d.es_fotografia
                }
            )
        print("Tipos de documento copiados a Plan 2004.")

    expediente = Expediente.objects.filter(alumno__username='22370001').first()
    if expediente:
        tipos = TipoDocumento.objects.filter(modalidad=expediente.modalidad).order_by('orden')
        for tipo in tipos:
            Documento.objects.get_or_create(
                expediente=expediente, 
                tipo_documento=tipo, 
                defaults={'estado': 'PENDIENTE'}
            )
        print("Documentos generados para el expediente del alumno.")

if __name__ == '__main__':
    run()
