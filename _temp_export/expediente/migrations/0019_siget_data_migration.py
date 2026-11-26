# Data migration SIGET — roles y estados legados

from django.db import migrations

ROLE_MAP = {
    'ESCOLARES': 'OFICINA_TITULACION',
    'ACADEMICO': 'OFICINA_TITULACION',
    'JEFE_PROYECTO': 'JEFE_ACADEMIA',
}

ESTADO_MAP = {
    'BORRADOR': 'DATOS_EXPEDIENTE',
    'EN_REVISION_ACADEMICO': 'EN_REVISION',
    'RECHAZADO_ACADEMICO': 'EN_CORRECCION',
    'DOCUMENTOS_PENDIENTES': 'CARGA_DOCUMENTOS',
    'EN_REVISION_DOCUMENTOS': 'EN_REVISION',
    'LISTO_INTEGRACION': 'CARGA_DOCUMENTOS',
    'RECIBI_PAPEL_ORIGINAL': 'CARGA_DOCUMENTOS',
    'PAGO_EN_REVISION': 'PAGO_PENDIENTE',
    'ESPERANDO_CONSTANCIA': 'ADEUDOS_EN_REVISION',
    'CONSTANCIA_EN_REVISION': 'ADEUDOS_EN_REVISION',
    'INTEGRADO': 'DOCUMENTOS_OFICIALES_LISTOS',
    'EMPASTADO_PENDIENTE': 'JURADO_ASIGNADO',
    'EMPASTADO_RECIBIDO': 'JURADO_ASIGNADO',
    'ACTO_PROGRAMADO': 'PROTOCOLO_PROGRAMADO',
    'ACTA_EXENCION': 'ACTO_REALIZADO',
    'TRAMITE_DGP': 'ACTO_REALIZADO',
    'CEDULA_EN_REVISION': 'ACTO_REALIZADO',
    'CEDULA_RECHAZADA': 'ACTO_REALIZADO',
    'CITA_ENTREGA': 'ACTO_REALIZADO',
}


def migrate_roles_and_states(apps, schema_editor):
    Usuario = apps.get_model('administracion', 'Usuario')
    Expediente = apps.get_model('expediente', 'Expediente')
    TipoDocumento = apps.get_model('expediente', 'TipoDocumento')
    ValidacionDocumento = apps.get_model('expediente', 'ValidacionDocumento')

    for old, new in ROLE_MAP.items():
        Usuario.objects.filter(rol=old).update(rol=new)

    for exp in Expediente.objects.all():
        nuevo = ESTADO_MAP.get(exp.estado)
        if nuevo:
            Expediente.objects.filter(pk=exp.pk).update(estado=nuevo)

    for td in TipoDocumento.objects.all():
        formatos = []
        if td.es_fotografia:
            formatos = ['jpg', 'png']
        elif td.acepta_solo_pdf:
            formatos = ['pdf']
        else:
            formatos = ['pdf']
        TipoDocumento.objects.filter(pk=td.pk).update(
            formatos_admitidos=formatos,
            tamano_max_mb=2.5,
        )


class Migration(migrations.Migration):
    dependencies = [
        ('administracion', '0024_siget_fase0'),
        ('expediente', '0018_siget_fase0'),
    ]
    operations = [
        migrations.RunPython(migrate_roles_and_states, migrations.RunPython.noop),
    ]
