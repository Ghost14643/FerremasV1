# ferremas/ferremasApp/views.py

from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
import requests
import uuid
from .models import Producto
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q
from django.contrib import messages
from .models import Contacto

# --- ¡NUEVAS IMPORTACIONES NECESARIAS PARA AUTENTICACIÓN! ---
from django.contrib.auth.forms import AuthenticationForm # Solo necesitamos AuthenticationForm
from django.contrib.auth import login, logout # Asegúrate de importar logout
from .forms import CustomUserCreationForm # <--- IMPORTACIÓN DE TU FORMULARIO PERSONALIZADO
# --- FIN DE NUEVAS IMPORTACIONES ---

# API CMF
API_KEY_CMF = "793d989c2c3b0987eb56404ed529a24910086f80"
URL_BASE_CMF = "https://api.cmfchile.cl/api-sbifv3/recursos_api"

# Transbank configuración API REST
TBK_API_KEY_ID = '597055555532'
TBK_API_KEY_SECRET = '579B532A7440BB0C9079DED94D31EA1615BACEB56610332264630D42D0A36B1C'
TBK_API_BASE_URL = 'https://webpay3gint.transbank.cl/rswebpaytransaction/api/webpay/v1.2/transactions'


# Vistas principales
def home(request):
    return render(request, "ferremasApp/home.html")

def servicios(request):
    return render(request, "ferremasApp/servicios.html")

def tienda(request):
    return render(request, "ferremasApp/tienda.html")

def reseñas(request):
    return render(request, "ferremasApp/reseñas.html")

def contacto(request):
    # Esta función de 'contacto' parece estar duplicada al final del archivo.
    # Se recomienda mantener una sola y gestionarla aquí.
    # Si 'enviar_contacto' maneja el POST, esta solo mostraría el formulario GET.
    return render(request, "ferremasApp/contacto.html")

# La vista carrito_view es un placeholder, la lógica real del carrito está en ver_carrito
def carrito_view(request):
    return render(request, 'ferremasApp/carrito.html')

# --- VISTAS DE AUTENTICACIÓN ---
def registro_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST) # <--- Usando CustomUserCreationForm
        if form.is_valid():
            user = form.save()
            login(request, user) # Iniciar sesión al usuario después del registro
            messages.success(request, "¡Registro exitoso! Ahora puedes disfrutar de Ferremas.")
            return redirect('tienda') # Redirige a la página principal o a donde desees
        else:
            # Mostrar mensajes de error del formulario
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"Error en {field}: {error}")
    else:
        form = CustomUserCreationForm() # <--- Instanciando CustomUserCreationForm para GET
    return render(request, 'ferremasApp/registro.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user) # Iniciar sesión al usuario
            messages.success(request, f"¡Bienvenido de nuevo, {user.username}!")
            # Redirigir al usuario a la página anterior si vino de una, o a 'tienda' por defecto
            next_url = request.GET.get('next') or 'tienda'
            return redirect(next_url)
        else:
            messages.error(request, "Nombre de usuario o contraseña incorrectos. Por favor, inténtalo de nuevo.")
    else:
        form = AuthenticationForm()
    return render(request, 'ferremasApp/login.html', {'form': form})

def logout_view(request):
    logout(request) # Cerrar la sesión del usuario
    # Eliminamos el carrito del localStorage a través de la redirección a logout_success
    messages.info(request, "Has cerrado sesión correctamente.")
    return redirect('logout_success') # CAMBIO CLAVE: Redirige a la nueva vista

# NUEVA VISTA: Para manejar el éxito del logout y limpiar el carrito del navegador
def logout_success_view(request):
    return render(request, 'ferremasApp/logout_success.html')
# --- FIN DE VISTAS DE AUTENTICACIÓN ---


# API de conversión dólar
def obtener_valor_dolar_cmf():
    url = f"{URL_BASE_CMF}/dolar?apikey={API_KEY_CMF}&formato=json"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        if data and "Dolares" in data and len(data["Dolares"]) > 0 and "Valor" in data["Dolares"][0]:
            valor = data["Dolares"][0]["Valor"].replace(',', '.')
            return float(valor)
        else:
            print("Respuesta de la CMF inesperada.")
            return None
    except Exception as e:
        print(f"Error al obtener dólar: {e}")
        return None

def api_conversion(request):
    valor = obtener_valor_dolar_cmf()
    if valor is not None:
        return JsonResponse({"valor": valor})
    else:
        return JsonResponse({"error": "No se pudo obtener el valor del dólar desde la CMF"})


@csrf_exempt
def iniciar_pago_transbank(request):
    if request.method == 'POST':
        total = request.POST.get('total')
        if not total:
            return HttpResponse("Total no recibido", status=400)

        try:
            amount = int(float(total))  # WebPay requiere enteros en CLP
        except ValueError:
            return HttpResponse("Total inválido", status=400)

        buy_order = str(uuid.uuid4())[:12]
        session_id = str(uuid.uuid4())
        return_url = request.build_absolute_uri('/pago/exito/')

        headers = {
            'Tbk-Api-Key-Id': TBK_API_KEY_ID,
            'Tbk-Api-Key-Secret': TBK_API_KEY_SECRET,
            'Content-Type': 'application/json'
        }

        data = {
            "buy_order": buy_order,
            "session_id": session_id,
            "amount": amount,
            "return_url": return_url
        }

        try:
            response = requests.post(TBK_API_BASE_URL, headers=headers, json=data)
            if response.status_code == 200:
                respuesta = response.json()
                return render(request, 'ferremasApp/redireccion_transbank.html', {
                    'url': respuesta['url'],
                    'token': respuesta['token']
                })
            else:
                print(f"Error al crear la transacción: {response.text}")
                return HttpResponse("Error al crear la transacción", status=response.status_code)
        except Exception as e:
            print(f"Error en conexión con Transbank: {e}")
            return HttpResponse("Error en la conexión con Transbank", status=500)

    return redirect('carrito') # Redirige a 'carrito' si la petición no es POST


@csrf_exempt
def pago_exito(request):
    token = request.POST.get("token_ws")
    if not token:
        return HttpResponse("Transacción fallida", status=400)

    headers = {
        'Tbk-Api-Key-Id': TBK_API_KEY_ID,
        'Tbk-Api-Key-Secret': TBK_API_KEY_SECRET,
        'Content-Type': 'application/json'
    }
    url_commit = f"{TBK_API_BASE_URL}/{token}"

    try:
        response = requests.put(url_commit, headers=headers)
        if response.status_code == 200:
            resultado = response.json()
            # Vaciar carrito tras pago exitoso - IMPORTANTE: Esto solo borra el carrito de la sesión de Django.
            # La limpieza del localStorage (carrito del lado del cliente) se debe hacer en el frontend.
            if 'carrito' in request.session:
                del request.session['carrito']
            return render(request, 'ferremasApp/pago_exito.html', {
                'response': resultado
            })
        else:
            print(f"Error al confirmar la transacción: {response.text}")
            return HttpResponse("Error al confirmar la transacción", status=response.status_code)
    except Exception as e:
        print(f"Error al confirmar transacción: {e}")
        return HttpResponse("Error al procesar pago", status=500)


def enviar_contacto(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        email = request.POST.get('email')
        asunto = request.POST.get('asunto')
        mensaje = request.POST.get('mensaje')

        # Guardar si tienes modelo
        if nombre and email and asunto and mensaje: # Simple validación para guardar
            try:
                Contacto.objects.create(nombre=nombre, email=email, asunto=asunto, mensaje=mensaje)
                messages.success(request, "¡Gracias por contactarnos! Responderemos a la brevedad.")
            except Exception as e:
                messages.error(request, f"Ocurrió un error al guardar tu mensaje: {e}")
        else:
            messages.error(request, "Por favor, completa todos los campos del formulario de contacto.")
        return redirect('contacto') # Redirige de nuevo a la página de contacto

    return redirect('contacto') # Si se accede por GET, simplemente redirige


# Catálogo HTML
def vista_productos_html(request):
    return render(request, 'ferremasApp/productos.html')

def enviar_reseña(request):
    if request.method == 'POST':
        # manejar envío del formulario (aquí iría tu lógica para guardar la reseña)
        messages.success(request, "¡Gracias por tu reseña!") # Ejemplo de mensaje
        pass
    return redirect('reseñas')

# Carrito
def agregar_al_carrito(request, producto_id):
    try:
        producto = Producto.objects.get(id=producto_id)
        if producto.stock <= 0:
            messages.error(request, "Producto sin stock disponible.")
            return redirect('tienda')

        carrito = request.session.get('carrito', {})
        # Asegúrate de que la cantidad en el carrito no exceda el stock disponible
        cantidad_actual_en_carrito = carrito.get(str(producto_id), 0)
        if cantidad_actual_en_carrito + 1 > producto.stock:
            messages.error(request, f"No hay suficiente stock de {producto.nombre}. Cantidad disponible: {producto.stock - cantidad_actual_en_carrito}.")
            return redirect('tienda')

        carrito[str(producto_id)] = cantidad_actual_en_carrito + 1
        request.session['carrito'] = carrito
        messages.success(request, f"{producto.nombre} agregado al carrito.")
        return redirect('tienda')
    except Producto.DoesNotExist:
        messages.error(request, "Producto no encontrado.")
        return redirect('tienda')
    except Exception as e:
        messages.error(request, f"Error al agregar producto al carrito: {e}")
        return redirect('tienda')


def eliminar_del_carrito(request, producto_id):
    carrito = request.session.get('carrito', {})
    producto_id_str = str(producto_id)
    if producto_id_str in carrito:
        del carrito[producto_id_str]
    request.session['carrito'] = carrito
    messages.info(request, "Producto eliminado del carrito.")
    return redirect('ver_carrito')

def actualizar_cantidad_carrito(request):
    if request.method == 'POST':
        producto_id = request.POST.get('producto_id')
        cantidad = request.POST.get('cantidad')

        if producto_id and cantidad:
            try:
                producto = Producto.objects.get(id=producto_id)
                cantidad = int(cantidad)

                if cantidad <= 0:
                    messages.error(request, "La cantidad debe ser al menos 1. Para eliminar, usa el botón de eliminar.")
                    return redirect('ver_carrito')

                if cantidad > producto.stock:
                    messages.error(request, f"No hay suficiente stock de {producto.nombre}. Cantidad disponible: {producto.stock}.")
                    return redirect('ver_carrito')

                carrito = request.session.get('carrito', {})
                carrito[str(producto_id)] = cantidad
                request.session['carrito'] = carrito
                messages.success(request, "Cantidad actualizada.")
            except Producto.DoesNotExist:
                messages.error(request, "Producto no encontrado.")
            except ValueError:
                messages.error(request, "Cantidad inválida.")
            except Exception as e:
                messages.error(request, f"Error al actualizar cantidad: {e}")
    return redirect('ver_carrito')


def limpiar_carrito(request):
    if 'carrito' in request.session:
        del request.session['carrito']
        messages.info(request, "El carrito ha sido vaciado.")
    return redirect('tienda')


def ver_carrito(request):
    carrito = request.session.get('carrito', {})
    productos_en_carrito = []
    total = 0

    # Obtener los IDs de los productos en el carrito
    producto_ids_en_carrito = [int(p_id) for p_id in carrito.keys()]

    if producto_ids_en_carrito:
        # Recuperar todos los productos en una sola consulta
        productos_db = Producto.objects.filter(id__in=producto_ids_en_carrito)

        # Crear un diccionario para un acceso más rápido por ID
        productos_dict = {p.id: p for p in productos_db}

        for producto_id_str, cantidad in carrito.items():
            producto_id = int(producto_id_str)
            producto = productos_dict.get(producto_id)
            if producto:
                subtotal = producto.precio * cantidad
                total += subtotal
                productos_en_carrito.append({
                    'producto': producto,
                    'cantidad': cantidad,
                    'subtotal': subtotal,
                })
            else:
                # Si el producto no se encuentra en la DB, eliminarlo del carrito de la sesión
                del carrito[producto_id_str]
                request.session['carrito'] = carrito # Actualizar la sesión si se eliminó un producto

    return render(request, 'ferremasApp/carrito.html', {
        'carrito_items': productos_en_carrito,
        'total': total
    })

# Vista de búsqueda
def busqueda_productos(request):
    query = request.GET.get('q')
    productos = []
    if query:
        # Buscar en nombre y descripción del producto
        productos = Producto.objects.filter(
            Q(nombre__icontains=query) | Q(descripcion__icontains=query)
        ).distinct()
        messages.info(request, f"Resultados para: '{query}'")
    else:
        messages.warning(request, "Por favor, ingresa un término de búsqueda.")

    return render(request, 'ferremasApp/busqueda_resultados.html', {'query': query, 'productos': productos})