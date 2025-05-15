from django.contrib import admin
from django.urls import path, include
from ferremasApp import views

urlpatterns = [
    path('admin/', admin.site.urls),  # Asegúrate de tener acceso al admin si lo necesitas

    # Páginas principales
    path('', views.home, name="Home"),
    path('servicios/', views.servicios, name="Servicios"),
    path('tienda/', views.tienda, name="Tienda"),
    path('reseñas/', views.reseñas, name="Reseñas"),
    path('contacto/', views.contacto, name="Contacto"),

    # Conversión USD
    path('api/conversion/', views.api_conversion, name='api_conversion'),

    # Carrito y pago
    path('carrito/', views.carrito_view, name='carrito'),
    path('pago/transbank/', views.iniciar_pago_transbank, name='iniciar_pago_transbank'),
    path('pago/exito/', views.pago_exito, name='pago_exitoso'),

    # API productos y categorías
    path('api/', include('api.urls')),
]
