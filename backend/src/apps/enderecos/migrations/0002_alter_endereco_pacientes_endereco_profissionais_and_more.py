import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('enderecos', '0001_initial'),
        ('pacientes', '0001_initial'),
        ('profissionais', '0002_add_tipo_profissional_data'),
    ]

    operations = [
        migrations.AlterField(
            model_name='endereco',
            name='pacientes',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='enderecos', to='pacientes.paciente', verbose_name='pacientes'),
        ),
        migrations.AddField(
            model_name='endereco',
            name='profissionais',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='enderecos', to='profissionais.profissional', verbose_name='profissionais'),
        ),
        migrations.AddConstraint(
            model_name='endereco',
            constraint=models.CheckConstraint(condition=models.Q(models.Q(('pacientes__isnull', False), ('profissionais__isnull', True)), models.Q(('pacientes__isnull', True), ('profissionais__isnull', False)), _connector='OR'), name='endereco_com_um_unico_dono'),
        ),
    ]
