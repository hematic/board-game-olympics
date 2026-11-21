from django.contrib.auth import views as auth
from django.urls import path, reverse_lazy

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("healthz/", views.health, name="health"),
    path("login/", auth.LoginView.as_view(template_name="olympics/login.html"), name="login"),
    path("logout/", auth.LogoutView.as_view(), name="logout"),
    path("accounts/", views.accounts, name="accounts"),
    path("accounts/new/", views.create_account, name="create-account"),
    path("accounts/<int:pk>/password/", views.reset_account_password, name="reset-account-password"),
    path("password/", auth.PasswordChangeView.as_view(
        template_name="olympics/form.html",
        extra_context={"title": "Change password"},
        success_url=reverse_lazy("home"),
    ), name="password-change"),
    path("editions/new/", views.create_edition, name="create-edition"),
    path("editions/<int:year>/", views.edition_page, name="edition"),
    path("editions/<int:year>/ballot/", views.ballot, name="ballot"),
    path("editions/<int:year>/manage/<slug:action>/", views.manage_edition, name="manage-edition"),
    path("editions/<int:year>/game/<int:pk>/<slug:action>/", views.manage_game, name="manage-game"),
    path("games/", views.catalog, name="catalog"),
    path("games/new/", views.edit_game, name="create-game"),
    path("games/search/", views.bgg_search, name="bgg-search"),
    path("games/<int:pk>/", views.game_detail, name="game"),
    path("games/<int:pk>/edit/", views.edit_game, name="edit-game"),
]
