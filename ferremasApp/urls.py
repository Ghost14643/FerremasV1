from django.urls import path
from ferremasApp import views

urlpatterns = [
    path('', views.home, name="Home"),
    path('servicios/', views.servicios, name="Servicios"),
    path('tienda/', views.tienda, name="Tienda"),
    path('reseñas/', views.reseñas, name="Reseñas"),
    path('contacto/', views.contacto, name="Contacto"),
    path('api/conversion/', views.api_conversion, name='api_conversion'),
]