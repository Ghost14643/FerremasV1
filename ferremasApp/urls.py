from ferremasApp import views
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('', views.home, name="Home"),
    path('servicios/', views.servicios, name="Servicios"),
    path('tienda/', views.tienda, name="Tienda"),
    path('reseñas/', views.reseñas, name="Reseñas"),
    path('contacto/', views.contacto, name="Contacto"),
    path('api/conversion/', views.api_conversion, name='api_conversion'),

    # Incluir las URLs de la app api para productos y categorias
    path('api/', include('api.urls')),  
]
