# Data migration — correo institucional para administradores

from django.db import migrations


def migrar_email_admin_a_institucional(apps, schema_editor):
    Usuario = apps.get_model('administracion', 'Usuario')
    ConfiguracionInstitucional = apps.get_model('administracion', 'ConfiguracionInstitucional')

    config = ConfiguracionInstitucional.objects.first()
    dominio = (config.dominio_institucional if config else None) or 'apizaco.tecnm.mx'
    sufijo = f'@{dominio}'.lower()

    for usuario in Usuario.objects.filter(rol='ADMINISTRADOR'):
        email = (usuario.email or '').strip()
        institucional = (usuario.correo_institucional or '').strip()
        updates = {}

        if not institucional and email and email.lower().endswith(sufijo):
            updates['correo_institucional'] = email
            if usuario.email_verificado:
                updates['correo_institucional_verificado'] = True
            updates['email'] = ''
            updates['email_verificado'] = False

        if updates:
            Usuario.objects.filter(pk=usuario.pk).update(**updates)


class Migration(migrations.Migration):

    dependencies = [
        ('administracion', '0024_siget_fase0'),
    ]

    operations = [
        migrations.RunPython(migrar_email_admin_a_institucional, migrations.RunPython.noop),
    ]
