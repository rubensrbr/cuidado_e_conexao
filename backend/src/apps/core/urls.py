from django.urls import path
from . import views

# app_name = "core"


urlpatterns = [
    path("", views.IndexView.as_view(), name="home"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("cadastro/", views.CadastroView.as_view(), name="cadastro"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("alterar-senha/", views.PasswordChangeView.as_view(), name="alterar_senha"),
]
