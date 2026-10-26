from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('clinicas', '0002_membro'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='membro',
            options={'ordering': ['clinica__nome', 'user__email'], 'verbose_name': 'Membro', 'verbose_name_plural': 'Membros'},
        ),
    ]
