from django.db import migrations
from django.contrib.postgres.operations import UnaccentExtension

class Migration(migrations.Migration):

    dependencies = [
        ('administracion', '0011_passwordresetotp'),
    ]

    operations = [
        UnaccentExtension(),
    ]
