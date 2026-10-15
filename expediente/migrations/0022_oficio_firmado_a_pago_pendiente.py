from django.db import migrations


def avanzar_oficio_firmado_a_pago(apps, schema_editor):
    Expediente = apps.get_model('expediente', 'Expediente')
    Expediente.objects.filter(estado='OFICIO_FIRMADO').update(
        estado='PAGO_PENDIENTE',
        pago_validado='PENDIENTE',
    )


class Migration(migrations.Migration):

    dependencies = [
        ('expediente', '0021_referenciapago_preficha'),
    ]

    operations = [
        migrations.RunPython(avanzar_oficio_firmado_a_pago, migrations.RunPython.noop),
    ]
