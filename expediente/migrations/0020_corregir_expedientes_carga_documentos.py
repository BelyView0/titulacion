# Corrige expedientes creados con estado incorrecto (certificado antes de documentos)

from django.db import migrations


def corregir_expedientes_prematuros(apps, schema_editor):
  Expediente = apps.get_model('expediente', 'Expediente')
  HistorialExpediente = apps.get_model('expediente', 'HistorialExpediente')
  Documento = apps.get_model('expediente', 'Documento')

  for exp in Expediente.objects.filter(estado='CERTIFICADO_PENDIENTE_CITA'):
    total_oblig = Documento.objects.filter(
      expediente=exp,
      tipo_documento__es_obligatorio=True,
    ).count()
    aprobados = Documento.objects.filter(
      expediente=exp,
      tipo_documento__es_obligatorio=True,
      estado='APROBADO',
    ).count()
    if total_oblig == 0 or aprobados < total_oblig:
      Expediente.objects.filter(pk=exp.pk).update(estado='CARGA_DOCUMENTOS')
      HistorialExpediente.objects.create(
        expediente_id=exp.pk,
        estado_anterior='CERTIFICADO_PENDIENTE_CITA',
        estado_nuevo='CARGA_DOCUMENTOS',
        descripcion='Corrección automática: el expediente debe cargar y revisar documentos antes del certificado.',
        realizado_por_id=None,
      )


class Migration(migrations.Migration):
  dependencies = [
    ('expediente', '0019_siget_data_migration'),
  ]

  operations = [
    migrations.RunPython(corregir_expedientes_prematuros, migrations.RunPython.noop),
  ]
