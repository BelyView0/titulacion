from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('expediente', '0020_corregir_expedientes_carga_documentos'),
    ]

    operations = [
        migrations.AddField(
            model_name='referenciapago',
            name='concepto',
            field=models.CharField(
                default='TRÁMITE DE TITULACIÓN NIVEL LICENCIATURA',
                max_length=200,
                verbose_name='Concepto de pago',
            ),
        ),
        migrations.AddField(
            model_name='referenciapago',
            name='referencia_bancaria',
            field=models.CharField(
                blank=True,
                max_length=30,
                verbose_name='Referencia alfanumérica bancaria',
            ),
        ),
    ]
