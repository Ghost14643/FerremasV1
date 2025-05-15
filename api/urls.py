from django.urls import path
from . import views

urlpatterns = [
    path('productos/', views.lista_productos),
    path('categorias/', views.lista_categorias),
]
