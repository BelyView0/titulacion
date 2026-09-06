from django.db import migrations, models


def cargar_contactos(apps, schema_editor):
    ContactoArea = apps.get_model('administracion', 'ContactoArea')
    ConfiguracionInstitucional = apps.get_model('administracion', 'ConfiguracionInstitucional')

    config = ConfiguracionInstitucional.objects.first()
    if config and not getattr(config, 'telefono_institucional', None):
        config.telefono_institucional = '2414172010'
        config.save(update_fields=['telefono_institucional'])

    datos = [
        {
            'area': 'FINANZAS',
            'nombre_responsable': 'Claudia Saavedra Hernández',
            'correo_departamento': 'financieros@apizaco.tecnm.mx',
            'extension': '119',
        },
        {
            'area': 'CENTRO_COMPUTO',
            'nombre_responsable': 'Marcial Molina Sarmiento',
            'correo_departamento': 'ccomputo@apizaco.tecnm.mx',
            'extension': '121',
        },
        {
            'area': 'CENTRO_INFORMACION',
            'nombre_responsable': 'Juvenal Ignacio Morales Cortés',
            'correo_departamento': 'cinformacion@apizaco.tecnm.mx',
            'extension': '143',
        },
        {
            'area': 'SERVICIOS_ESCOLARES',
            'nombre_responsable': 'Martín Rojas Ramírez',
            'correo_departamento': 'escolares@apizaco.tecnm.mx',
            'extension': '108',
        },
    ]
    for item in datos:
        ContactoArea.objects.update_or_create(
            area=item['area'],
            defaults={
                'nombre_responsable': item['nombre_responsable'],
                'correo_departamento': item['correo_departamento'],
                'extension': item['extension'],
                'activo': True,
            },
        )


def revertir_contactos(apps, schema_editor):
    ContactoArea = apps.get_model('administracion', 'ContactoArea')
    ContactoArea.objects.filter(
        area__in=['FINANZAS', 'CENTRO_COMPUTO', 'CENTRO_INFORMACION', 'SERVICIOS_ESCOLARES'],
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('administracion', '0027_logos_institucionales'),
    ]

    operations = [
        migrations.AddField(
            model_name='configuracioninstitucional',
            name='telefono_institucional',
            field=models.CharField(
                blank=True,
                default='2414172010',
                help_text='Número base del plantel. Las extensiones de cada área se configuran en Contactos de áreas.',
                max_length=20,
                verbose_name='Teléfono institucional (base)',
            ),
        ),
        migrations.CreateModel(
            name='ContactoArea',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('area', models.CharField(
                    choices=[
                        ('FINANZAS', 'Recursos Financieros'),
                        ('CENTRO_COMPUTO', 'Centro de Cómputo'),
                        ('CENTRO_INFORMACION', 'Centro de Información'),
                        ('SERVICIOS_ESCOLARES', 'Servicios Escolares'),
                    ],
                    max_length=30,
                    unique=True,
                    verbose_name='Área',
                )),
                ('nombre_responsable', models.CharField(max_length=200, verbose_name='Nombre del responsable')),
                ('correo_departamento', models.EmailField(
                    help_text='Correo institucional del área (solo para mostrar contacto).',
                    max_length=254,
                    verbose_name='Correo del departamento',
                )),
                ('correo_personal', models.EmailField(
                    blank=True,
                    help_text='Opcional. No se usa para envíos automáticos del sistema.',
                    max_length=254,
                    verbose_name='Correo personal del responsable',
                )),
                ('extension', models.CharField(blank=True, max_length=10, verbose_name='Extensión')),
                ('activo', models.BooleanField(default=True, verbose_name='Activo')),
            ],
            options={
                'verbose_name': 'Contacto de área',
                'verbose_name_plural': 'Contactos de áreas',
                'ordering': ['area'],
            },
        ),
        migrations.RunPython(cargar_contactos, revertir_contactos),
    ]
