# ferremas/ferremasApp/urls.py
from django.conf.urls.static import static
from django.urls import path
from . import views
from django.conf import settings

urlpatterns = [
    # --- Páginas Principales ---
    path('', views.home, name="home"),
    path('servicios/', views.servicios, name="servicios"),
    path('tienda/', views.tienda, name="tienda"), # Esta es la vista principal de productos
    path('reseñas/', views.reseñas, name="reseñas"),
    path('contacto/', views.contacto, name="contact"), # <--- ¡CAMBIO AQUÍ: de views.contact a views.contacto!

    # --- Autenticación (Login, Registro, Logout) ---
    path('login/', views.login_view, name='login'),
    path('registro/', views.registro_view, name='registro'),
    path('logout/', views.logout_view, name='logout'),
    path('logout_success/', views.logout_success_view, name='logout_success'),

    # --- API de Conversión ---
    path('api/conversion_dolar/', views.api_conversion, name='api_conversion'),

    # --- Gestión del Carrito de Compras ---
    path('carrito/', views.ver_carrito, name='carrito'),
    path('agregar_al_carrito/', views.agregar_al_carrito, name='agregar_al_carrito'),
    path('eliminar_del_carrito/<int:producto_id>/', views.eliminar_del_carrito, name='eliminar_del_carrito'),
    path('actualizar_cantidad/', views.actualizar_cantidad_carrito, name='actualizar_cantidad_carrito'),
    path('limpiar_carrito/', views.limpiar_carrito, name='limpiar_carrito'),
    path('get_cart_total/', views.get_cart_total, name='get_cart_total'), # Para actualizar contador en navbar
    path('get_cart_items/', views.get_cart_details_json, name='get_cart_items'), # Añadida para resolver NoReverseMatch

    # --- Proceso de Pago Transbank ---
    path('pago/iniciar/', views.iniciar_pago_transbank, name='iniciar_pago_transbank'),
    path('pago/redireccion_transbank/', views.redireccion_transbank, name='redireccion_transbank'),
    # Esta es la 'return_url' de Transbank, donde se hace el commit.
    path('pago/exito/', views.pago_exito, name='pago_exito'),
    path('pago/fallido/', views.pago_fallido, name='pago_fallido'),
    # NUEVA URL: Esta es la 'final_url' a la que tu aplicación redirige después del flujo completo de Transbank.
    # Aquí se mostrará la información de pago exitoso.
    path('pago/exitoso_final/', views.pago_exitoso_final_propia, name='pago_exitoso_final_propia'),

    # --- Otras Vistas ---
    path('enviar-reseña/', views.enviar_reseña, name='enviar_reseña'),
]

# Configuración para servir archivos de medios durante el desarrollo
# Esto solo debe usarse en DEBUG = True. En producción, se usan servidores web como Nginx/Apache.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)