from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('administracion', '0029_periodos_semestres_y_docs_12'),
    ]

    operations = [
        migrations.AddField(
            model_name='passwordresetotp',
            name='intentos_fallidos',
            field=models.PositiveSmallIntegerField(
                default=0, verbose_name='Intentos fallidos'
            ),
        ),
    ]
