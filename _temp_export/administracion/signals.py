from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone

from expediente.models import Expediente, Documento, ActoProtocolario
from alumnos.models import Notificacion
from administracion.models import ConfiguracionInstitucional, Carrera, Departamento, Profesor

def actualizar_timestamp_global(sender, **kwargs):
    """
    Actualiza el timestamp global de ConfiguracionInstitucional
    cuando ocurre un cambio importante en la BD.
    """
    now_timestamp = timezone.now().timestamp()
    ConfiguracionInstitucional.objects.filter(id=1).update(ultima_actualizacion=now_timestamp)

# Modelos que al cambiar, deberían disparar una recarga o actualización global
MODELOS_CLAVE = [
    Expediente, 
    Documento, 
    ActoProtocolario, 
    Notificacion,
    Carrera,
    Departamento,
    Profesor
]

for modelo in MODELOS_CLAVE:
    post_save.connect(actualizar_timestamp_global, sender=modelo)
    post_delete.connect(actualizar_timestamp_global, sender=modelo)
