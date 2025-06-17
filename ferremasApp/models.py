# ferremasApp/models.py
from django.db import models
from django.contrib.auth.models import User # Importar el modelo de usuario de Django
# Asegúrate de importar tu modelo Producto de la app 'api'
from api.models import Producto
from django.core.validators import MinValueValidator, MaxValueValidator

class Contacto(models.Model):
    nombre = models.CharField(max_length=100)
    email = models.EmailField()
    asunto = models.CharField(max_length=200)
    mensaje = models.TextField()
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Mensaje de Contacto"
        verbose_name_plural = "Mensajes de Contacto"
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f"Mensaje de {self.nombre} ({self.asunto})"

# --- NUEVOS MODELOS PARA LA GESTIÓN DE COMPRAS Y BOLETAS ---

class Boleta(models.Model):
    """
    Representa una compra o transacción completa.
    """
    # Si el usuario es anónimo o el usuario es eliminado, se establece en NULL
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                 verbose_name="Usuario Asociado")
    
    fecha_compra = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Compra")
    # Es más seguro usar DecimalField para montos monetarios en la base de datos
    total = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Monto Total") # Cambiado a DecimalField
    
    # Identificadores de Transbank para seguimiento
    buy_order = models.CharField(max_length=50, unique=True, verbose_name="Orden de Compra (Transbank)")
    transbank_token = models.CharField(max_length=100, verbose_name="Token de Transbank")
    
    # Estado del pago, útil para seguimiento interno
    ESTADO_PAGO_CHOICES = [
        ('PENDIENTE', 'Pendiente'),
        ('PAGADO', 'Pagado'),
        ('RECHAZADO', 'Rechazado'),
        ('ANULADO', 'Anulado'),
    ]
    estado_pago = models.CharField(max_length=20, choices=ESTADO_PAGO_CHOICES, default='PENDIENTE',
                                   verbose_name="Estado del Pago")

    # --- CAMPOS NUEVOS AÑADIDOS PARA TRANSBANK ---
    authorization_code = models.CharField(max_length=50, null=True, blank=True, verbose_name="Código de Autorización")
    card_last_digits = models.CharField(max_length=4, null=True, blank=True, verbose_name="Últimos 4 Dígitos Tarjeta")
    # ---------------------------------------------

    # Puedes añadir más campos aquí si los necesitas, por ejemplo:
    # direccion_envio = models.TextField(blank=True, null=True)
    # comuna_envio = models.CharField(max_length=100, blank=True, null=True)
    # rut_cliente = models.CharField(max_length=12, blank=True, null=True) # Para facturación

    class Meta:
        verbose_name = "Boleta de Compra"
        verbose_name_plural = "Boletas de Compra"
        ordering = ['-fecha_compra'] # Ordenar las boletas por fecha de compra descendente

    def __str__(self):
        return f"Boleta N°{self.id} - Orden: {self.buy_order} - Total: ${self.total}"

class DetalleBoleta(models.Model):
    """
    Representa cada producto individual dentro de una Boleta.
    """
    boleta = models.ForeignKey(Boleta, on_delete=models.CASCADE, related_name='detalles',
                               verbose_name="Boleta Asociada")
    # CAMBIO: Usar models.PROTECT para evitar eliminación accidental de productos vendidos
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, verbose_name="Producto")
    cantidad = models.IntegerField(verbose_name="Cantidad")
    # Guardamos el precio unitario en el momento de la compra para evitar inconsistencias
    # si el precio del producto cambia en el futuro.
    precio_unitario = models.IntegerField(verbose_name="Precio Unitario al Comprar")

    class Meta:
        verbose_name = "Detalle de Boleta"
        verbose_name_plural = "Detalles de Boleta"
        # Asegura que no haya duplicados de un mismo producto en una boleta, aunque la lógica del carrito ya lo maneja
        unique_together = ('boleta', 'producto') 

    def __str__(self):
        return f"{self.cantidad} x {self.producto.nombre} en Boleta {self.boleta.id}"
# --- MODELO PARA RESEÑAS ---

class Resena(models.Model):
    nombre = models.CharField(max_length=100, verbose_name="Nombre del Autor")
    comentario = models.TextField(verbose_name="Comentario de la Reseña")
    puntuacion = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name="Puntuación (1-5)"
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")

    class Meta:
        verbose_name = "Reseña"
        verbose_name_plural = "Reseñas"
        ordering = ['-fecha_creacion'] # Ordena las reseñas por las más recientes primero

    def __str__(self):
        return f"Reseña de {self.nombre} - {self.puntuacion} estrellas"