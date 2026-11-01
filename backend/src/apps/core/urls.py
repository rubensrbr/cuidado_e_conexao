from django.urls import path
from . import views

# app_name = "core"


urlpatterns = [
    path("", views.IndexView.as_view(), name="home"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("cadastro/", views.CadastroView.as_view(), name="cadastro"),
    path("esqueci-senha/", views.SenhaEsquecidaView.as_view(), name="senha_esquecida"),
    path(
        "esqueci-senha/enviado/",
        views.SenhaEsquecidaEnviadaView.as_view(),
        name="senha_esquecida_enviada",
    ),
    path(
        "redefinir-senha/<uidb64>/<token>/",
        views.SenhaRedefinirView.as_view(),
        name="senha_redefinir",
    ),
    path(
        "redefinir-senha/concluido/",
        views.SenhaRedefinidaView.as_view(),
        name="senha_redefinida",
    ),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("alterar-senha/", views.PasswordChangeView.as_view(), name="alterar_senha"),
]
