# ferremas/ferremasApp/urls.py

from django.urls import path
from . import views # Importa las vistas de TU APLICACIÓN ferremasApp

urlpatterns = [
    # Páginas principales de ferremasApp
    path('', views.home, name="home"),
    path('servicios/', views.servicios, name="servicios"),
    path('tienda/', views.tienda, name="tienda"),
    path('reseñas/', views.reseñas, name="reseñas"),
    path('contacto/', views.contacto, name="contacto"),

    # Rutas de autenticación (Login, Registro, Logout) para ferremasApp
    path('login/', views.login_view, name='login'),
    path('registro/', views.registro_view, name='registro'),
    path('logout/', views.logout_view, name='logout'),
    # NUEVA URL para la página de éxito de logout con limpieza del carrito
    path('logout_success/', views.logout_success_view, name='logout_success'), # <-- AÑADIDA ESTA LÍNEA

    # API de Conversión (si esta vista pertenece a ferremasApp)
    path('api/conversion/', views.api_conversion, name='api_conversion'),

    # Carrito y proceso de pago
    path('carrito/', views.ver_carrito, name='carrito'),
    path('agregar/<int:producto_id>/', views.agregar_al_carrito, name='agregar_al_carrito'),
    path('eliminar/<int:producto_id>/', views.eliminar_del_carrito, name='eliminar_del_carrito'),
    path('actualizar_cantidad/', views.actualizar_cantidad_carrito, name='actualizar_cantidad_carrito'),
    path('limpiar_carrito/', views.limpiar_carrito, name='limpiar_carrito'),

    path('pago/transbank/', views.iniciar_pago_transbank, name='iniciar_pago_transbank'),
    # --- CAMBIO AQUÍ: 'pago_exitoso' a 'pago_exito' para consistencia con views.py ---
    path('pago/exito/', views.pago_exito, name='pago_exito'), 

    # Catálogo de productos (vista HTML)
    path('catalogo/', views.vista_productos_html, name='catalogo_productos'),

    # Formulario de contacto y envío de reseña
    path('enviar-reseña/', views.enviar_reseña, name='enviar_reseña'),
    path('enviar_contacto/', views.enviar_contacto, name='enviar_contacto'),
]