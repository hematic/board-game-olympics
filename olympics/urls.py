from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("healthz/", views.health, name="health"),
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
