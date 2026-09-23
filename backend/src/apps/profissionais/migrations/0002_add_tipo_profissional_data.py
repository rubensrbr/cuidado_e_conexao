from django.db import migrations

PROFISSOES = [
    "Biomédico",
    "Cirurgião-Dentista",
    "Educador Físico",
    "Enfermeiro",
    "Farmacêutico",
    "Fisioterapeuta",
    "Fonoaudiólogo",
    "Nutricionista",
    "Psicólogo",
    "Terapeuta Ocupacional",
    # Especialidades médicas
    "Alergia e Imunologia",
    "Anestesiologia",
    "Angiologia",
    "Cancerologia",
    "Cardiologia",
    "Cirurgia Cardiovascular",
    "Cirurgia da Mão",
    "Cirurgia de Cabeça e Pescoço",
    "Cirurgia do Aparelho Digestivo",
    "Cirurgia Geral",
    "Cirurgia Pediátrica",
    "Cirurgia Plástica",
    "Cirurgia Torácica",
    "Cirurgia Vascular",
    "Clínica Médica",
    "Coloproctologia",
    "Dermatologia",
    "Endocrinologia e Metabologia",
    "Endoscopia",
    "Gastroenterologia",
    "Genética Médica",
    "Geriatria",
    "Ginecologia e Obstetrícia",
    "Hematologia e Hemoterapia",
    "Homeopatia",
    "Infectologia",
    "Mastologia",
    "Medicina de Emergência",
    "Medicina de Família e Comunidade",
    "Medicina do Trabalho",
    "Medicina Esportiva",
    "Medicina Física e Reabilitação",
    "Medicina Intensiva",
    "Medicina Legal e Perícia Médica",
    "Medicina Nuclear",
    "Medicina Preventiva e Social",
    "Nefrologia",
    "Neurocirurgia",
    "Neurologia",
    "Nutrologia",
    "Oftalmologia",
    "Ortopedia e Traumatologia",
    "Otorrinolaringologia",
    "Patologia",
    "Patologia Clínica/Medicina Laboratorial",
    "Pediatria",
    "Pneumologia",
    "Psiquiatria",
    "Radiologia e Diagnóstico por Imagem",
    "Radioterapia",
    "Reumatologia",
    "Urologia",
]


def create_profissoes(apps, schema_editor):
    TipoProfissional = apps.get_model("seu_app", "TipoProfissional")

    for descricao in PROFISSOES:
        TipoProfissional.objects.get_or_create(
            descricao=descricao,
        )


def remove_profissoes(apps, schema_editor):
    TipoProfissional = apps.get_model("seu_app", "TipoProfissional")

    TipoProfissional.objects.filter(descricao__in=PROFISSOES).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("seu_app", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            create_profissoes,
            remove_profissoes,
        ),
    ]
