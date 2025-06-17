import logging
import json
import datetime
import uuid # Necesario para generar IDs únicos
import decimal

from .models import Contacto, Boleta, DetalleBoleta, Resena
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
import requests # Necesario para la API de CMF
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q, F
from django.contrib import messages
from django.urls import reverse
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login, logout
from .forms import CustomUserCreationForm # Asegúrate de que esta forma exista
from api.models import Producto, Categoria # Asegúrate de que estos modelos existan en tu app 'api'
from .models import Contacto, Boleta, DetalleBoleta # Asegúrate de que estos modelos existan en tu app 'ferremasApp'
from django.conf import settings
from django.views.decorators.http import require_POST

# --- Importaciones del SDK de Transbank ---
from transbank.webpay.webpay_plus.transaction import Transaction
from transbank.common.integration_type import IntegrationType
from transbank.common.options import WebpayOptions
# ------------------------------------------

logger = logging.getLogger(__name__)

# ====================================================================
# Funciones de Vistas Principales y Autenticación
# ====================================================================

def home(request):
    productos_destacados = Producto.objects.all().order_by('-id')[:4]
    context = {'productos_destacados': productos_destacados}
    return render(request, "ferremasApp/home.html", context)

def servicios(request):
    return render(request, "ferremasApp/servicios.html")

def reseñas(request):
    return render(request, "ferremasApp/reseñas.html")

def contacto(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        email = request.POST.get('email')
        asunto = request.POST.get('asunto')
        mensaje = request.POST.get('mensaje')

        if not all([nombre, email, asunto, mensaje]):
            messages.error(request, 'Por favor, rellene todos los campos del formulario.')
            return render(request, 'ferremasApp/contacto.html', {'nombre': nombre, 'email': email, 'asunto': asunto, 'mensaje': mensaje})
        try:
            Contacto.objects.create(nombre=nombre, email=email, asunto=asunto, mensaje=mensaje)
            messages.success(request, 'Tu mensaje ha sido enviado correctamente. Nos pondremos en contacto contigo pronto.')
            return redirect('contacto')
        except Exception as e:
            messages.error(request, f'Ocurrió un error al enviar tu mensaje: {e}')
    return render(request, 'ferremasApp/contacto.html')

def registro_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "¡Registro exitoso! Ahora puedes disfrutar de Ferremas.")
            return redirect('tienda')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"Error en {field}: {error}")
    else:
        form = CustomUserCreationForm()
    return render(request, 'ferremasApp/registro.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"¡Bienvenido de nuevo, {user.username}!")
            next_url = request.GET.get('next') or 'tienda'
            return redirect(next_url)
        else:
            messages.error(request, "Nombre de usuario o contraseña incorrectos. Por favor, inténtalo de nuevo.")
    else:
        form = AuthenticationForm()
    return render(request, 'ferremasApp/login.html', {'form': form})

def logout_view(request):
    logout(request)
    messages.info(request, "Has cerrado sesión correctamente.")
    return redirect('logout_success')

def logout_success_view(request):
    # Asegura que el carrito se vacíe al cerrar sesión
    if 'carrito' in request.session:
        del request.session['carrito']
        request.session.modified = True
    return render(request, 'ferremasApp/logout_success.html')

# ====================================================================
# Funciones de API y Transbank
# ====================================================================

def obtener_valor_dolar_cmf():
    """
    Obtiene el valor del dólar actual desde la API de la CMF.
    """
    fecha_actual = datetime.datetime.now()
    anio = fecha_actual.strftime("%Y")
    mes = fecha_actual.strftime("%m")
    dia = fecha_actual.strftime("%d")

    url = f"{settings.URL_BASE_CMF}/dolar/{anio}/{mes}/dias/{dia}?apikey={settings.API_KEY_CMF}&formato=json"
    
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        if data and "Dolares" in data and len(data["Dolares"]) > 0 and "Valor" in data["Dolares"][0]:
            valor = data["Dolares"][0]["Valor"].replace(',', '.')
            return float(valor)
        else:
            logger.warning(f"Respuesta de la CMF inesperada o sin datos de dólar. URL: {url}, Data: {data}")
            return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Error al obtener valor del dólar desde CMF (RequestException): {e}. URL: {url}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Error al decodificar JSON de CMF: {e}. Respuesta: {response.text if 'response' in locals() else 'No hay respuesta HTTP para decodificar.'}")
        return None
    except Exception as e:
        logger.error(f"Error inesperado en obtener_valor_dolar_cmf: {e}")
        return None

def api_conversion(request):
    """
    Vista API para devolver el valor del dólar.
    """
    valor = obtener_valor_dolar_cmf()
    if valor is not None:
        return JsonResponse({"valor": valor})
    else:
        return JsonResponse({"error": "No se pudo obtener el valor del dólar desde la CMF"}, status=500)

def iniciar_pago_transbank(request):
    """
    Inicia una transacción con Transbank Webpay Plus.
    """
    if request.method == 'POST':
        total_str = request.POST.get('total', '0.00')

        carrito_actual = request.session.get('carrito', {})
        if not carrito_actual:
            messages.error(request, "El carrito está vacío. No se puede iniciar el pago.")
            return redirect('carrito')

        try:
            total_clp = int(decimal.Decimal(total_str).quantize(decimal.Decimal('1.')))
            if total_clp <= 0:
                messages.error(request, "El monto del pago debe ser positivo.")
                return redirect('carrito')
        except (decimal.InvalidOperation, TypeError):
            messages.error(request, "Monto total inválido. Por favor, revise su carrito.")
            return redirect('carrito')

        buy_order = f"FERRE-{uuid.uuid4().hex[:10].upper()}"
        session_id = request.session.session_key or uuid.uuid4().hex
        
        # IMPORTANTE: La return_url es la URL a la que Transbank DEVOLVERÁ la petición para que tu servidor la procese.
        # En esta vista (pago_exito), se hará el transaction.commit().
        return_url = request.build_absolute_uri(reverse('pago_exito'))

        logger.info(f"Iniciando pago Transbank con SDK:")
        logger.info(f"  Buy Order: {buy_order}")
        logger.info(f"  Session ID: {session_id}")
        logger.info(f"  Amount: {total_clp}")
        logger.info(f"  Return URL: {return_url}")
        logger.info(f"  TBK_ENVIRONMENT: {settings.TBK_ENVIRONMENT}")
        logger.info(f"  TBK_API_KEY_ID (parcial): {settings.TBK_API_KEY_ID[:5]}...")
        logger.info(f"  TBK_API_KEY_SECRET (parcial): {settings.TBK_API_KEY_SECRET[:5]}...")

        try:
            if settings.TBK_ENVIRONMENT == 'INTEGRATION':
                integration_type = IntegrationType.TEST
            elif settings.TBK_ENVIRONMENT == 'PRODUCTION':
                integration_type = IntegrationType.LIVE
            else:
                raise ValueError(f"TBK_ENVIRONMENT '{settings.TBK_ENVIRONMENT}' inválido en settings.py. Debe ser 'INTEGRATION' o 'PRODUCTION'.")

            options = WebpayOptions(settings.TBK_API_KEY_ID, settings.TBK_API_KEY_SECRET, integration_type)
            transaction = Transaction(options)

            tbk_response = transaction.create(
                buy_order=buy_order,
                session_id=session_id,
                amount=total_clp,
                return_url=return_url
            )

            # Intentamos acceder como atributo; si falla (porque es un dict), accedemos como dict.
            # El SDK de Transbank para Python normalmente devuelve un objeto con atributos.
            token_ws = None
            url_transbank = None

            if isinstance(tbk_response, dict): # Caso de fallback si devuelve dict
                token_ws = tbk_response.get('token')
                url_transbank = tbk_response.get('url')
            elif hasattr(tbk_response, 'token') and hasattr(tbk_response, 'url'): # Caso normal (objeto)
                token_ws = tbk_response.token
                url_transbank = tbk_response.url

            if token_ws and url_transbank:
                logger.info(f"Transacción creada exitosamente por SDK. Token: {token_ws}")
                logger.info(f"URL de pago Transbank: {url_transbank}")

                request.session['transbank_data'] = {
                    'buy_order': buy_order,
                    'amount': str(total_clp), # Guardar como string para evitar problemas de serialización de Decimal
                    'token_ws': token_ws,
                    'url_transbank': url_transbank,
                    'carrito_antes_pago': carrito_actual
                }
                request.session.modified = True

                # Redirige a una vista auxiliar que renderiza un HTML para hacer el POST a Transbank
                return render(request, 'ferremasApp/redireccion_transbank.html', {
                    'url': url_transbank,
                    'token': token_ws
                })
            else:
                error_msg = f"El SDK de Transbank devolvió una respuesta inesperada o incompleta. Respuesta: {tbk_response}"
                logger.error(error_msg)
                messages.error(request, error_msg)
                return redirect('carrito')

        except Exception as e:
            error_msg = f"Error al iniciar el pago con Transbank (SDK): {e}"
            logger.error(error_msg, exc_info=True)
            messages.error(request, f"No se pudo iniciar el pago con Transbank. Por favor, intente más tarde. Detalles: {e}")
            return redirect('carrito')
    else:
        messages.warning(request, "Acceso inválido. Por favor, use el formulario de pago.")
        return redirect('carrito')

def redireccion_transbank(request):
    """
    Vista auxiliar para renderizar el HTML que redirige a Transbank via POST.
    """
    transbank_session_data = request.session.get('transbank_data', {})
    token_ws = transbank_session_data.get('token_ws')
    url_transbank = transbank_session_data.get('url_transbank')

    if not token_ws or not url_transbank:
        messages.error(request, "Datos de redirección a Transbank no encontrados. Intente el pago nuevamente.")
        return redirect('carrito')

    context = {'token': token_ws, 'url': url_transbank}
    return render(request, 'ferremasApp/redireccion_transbank.html', context)

@csrf_exempt
def pago_exito(request):
    """
    Confirma la transacción con Transbank. Esta es la 'return_url'.
    Después de confirmar, redirige al usuario a la URL final que Transbank proporciona.
    """
    token = request.GET.get("token_ws") or request.POST.get("token_ws")

    # Si hay TBK_TOKEN, la transacción fue anulada por el usuario en Transbank
    if not token and (request.POST.get('TBK_TOKEN') or request.GET.get('TBK_TOKEN')):
        messages.warning(request, "Transacción anulada por el usuario en Transbank.")
        return redirect('pago_fallido')

    if not token:
        messages.error(request, "Token de transacción no encontrado. La transacción no pudo ser verificada.")
        return redirect('pago_fallido')

    # Recupera los datos de la sesión y los elimina inmediatamente para evitar re-procesamiento
    transbank_session_data = request.session.pop('transbank_data', None)
    request.session.modified = True

    if not transbank_session_data or transbank_session_data.get('token_ws') != token:
        messages.error(request, "Token de transacción inválido o sesión expirada. Posible intento de manipulación o doble procesamiento.")
        return redirect('pago_fallido')

    logger.info(f"Confirmando pago Transbank con token: {token} usando SDK.")

    try:
        if settings.TBK_ENVIRONMENT == 'INTEGRATION':
            integration_type = IntegrationType.TEST
        elif settings.TBK_ENVIRONMENT == 'PRODUCTION':
            integration_type = IntegrationType.LIVE
        else:
            raise ValueError(f"TBK_ENVIRONMENT '{settings.TBK_ENVIRONMENT}' inválido en settings.py")

        options = WebpayOptions(settings.TBK_API_KEY_ID, settings.TBK_API_KEY_SECRET, integration_type)
        transaction = Transaction(options)

        # Llama al método commit del SDK
        tbk_result = transaction.commit(token)
        logger.info(f"Respuesta de Transbank (COMMIT) por SDK: {tbk_result}")

        # =====================================================================
        # ¡¡¡CAMBIO CRÍTICO AQUÍ!!!
        # Acceder a los valores de tbk_result como elementos de un DICCIONARIO.
        # Tus logs mostraron que tbk_result es un diccionario.
        # =====================================================================
        response_code = tbk_result.get('response_code')
        status = tbk_result.get('status')

        if response_code == 0 and status == "AUTHORIZED":
            original_buy_order = transbank_session_data['buy_order']
            original_amount_decimal = decimal.Decimal(transbank_session_data['amount'])

            # Extracción de datos del resultado del commit (asumiendo diccionario)
            tbk_result_buy_order = tbk_result.get('buy_order')
            tbk_result_amount_raw = tbk_result.get('amount')
            tbk_result_amount = decimal.Decimal(tbk_result_amount_raw) if tbk_result_amount_raw is not None else decimal.Decimal(0)

            if original_buy_order != tbk_result_buy_order or original_amount_decimal != tbk_result_amount:
                messages.error(request, "Error de seguridad: los detalles de la orden o el monto no coinciden con la sesión.")
                return redirect('pago_fallido')

            carrito_para_descuento = transbank_session_data.get('carrito_antes_pago', {})
            if not carrito_para_descuento:
                messages.warning(request, "No se pudo recuperar el carrito para el descuento de stock. Contacta a soporte.")

            boleta = None
            try:
                # Crear la Boleta
                boleta = Boleta.objects.create(
                    usuario=request.user if request.user.is_authenticated else None,
                    total=original_amount_decimal,
                    buy_order=tbk_result_buy_order,
                    transbank_token=token,
                    estado_pago='PAGADO',
                    # Acceso a campos como diccionario. Usa .get() con un diccionario vacío {} para anidados.
                    authorization_code=tbk_result.get('authorization_code'),
                    card_last_digits=tbk_result.get('card_detail', {}).get('card_number', 'N/A')[-4:] 
                )
                messages.success(request, f"Pago exitoso. Boleta Nº {boleta.id} generada.")
            except Exception as db_e_boleta:
                logger.error(f"Error al crear la boleta después de pago exitoso: {db_e_boleta}", exc_info=True)
                messages.warning(request, f"Pago exitoso, pero error al crear la boleta: {db_e_boleta}. Contacta a soporte.")
                boleta = None

            productos_con_problemas_stock = []
            for producto_id_str, cantidad_comprada in carrito_para_descuento.items():
                try:
                    producto = Producto.objects.get(id=int(producto_id_str))
                    if producto.stock >= cantidad_comprada:
                        Producto.objects.filter(id=producto.id).update(stock=F('stock') - cantidad_comprada)
                        if boleta:
                            DetalleBoleta.objects.create(
                                boleta=boleta,
                                producto=producto,
                                cantidad=cantidad_comprada,
                                precio_unitario=producto.precio
                            )
                    else:
                        productos_con_problemas_stock.append(f"{producto.nombre} (ID: {producto_id_str}) - Cantidad solicitada: {cantidad_comprada}, Stock disponible: {producto.stock}")
                except Producto.DoesNotExist:
                    productos_con_problemas_stock.append(f"Producto con ID {producto_id_str} (eliminado o no encontrado en DB)")
                except Exception as e:
                    productos_con_problemas_stock.append(f"Error al procesar el stock/detalle para producto ID {producto_id_str}: {e}")
                    logger.error(f"Error al descontar stock o crear detalle de boleta para producto {producto_id_str}: {e}", exc_info=True)

            if productos_con_problemas_stock:
                messages.warning(request, f"Advertencia: Hubo problemas con el stock de algunos productos o al registrar detalles. Contacta a soporte. Detalles: {'; '.join(productos_con_problemas_stock)}")

            # Vaciar el carrito de la sesión después de un pago exitoso
            if 'carrito' in request.session:
                del request.session['carrito']
                request.session.modified = True

            # Guarda los detalles de la boleta en la sesión para la vista final,
            # ya que la redirección de Transbank a tu `pago_exitoso_final_propia`
            # no pasará estos datos automáticamente en la URL.
            request.session['boleta_final_data'] = {
                'amount': tbk_result_amount_raw,
                'buy_order': tbk_result_buy_order,
                'authorization_code': tbk_result.get('authorization_code'), # Acceso como diccionario
                'transaction_date': tbk_result.get('transaction_date'),     # Acceso como diccionario
                'card_number': tbk_result.get('card_detail', {}).get('card_number', 'N/A')[-4:], # Acceso seguro a diccionario anidado
                'boleta_id': boleta.id if boleta else 'N/A',
            }
            request.session.modified = True # Asegura que la sesión se guarde antes de la redirección

            final_url_from_transbank = tbk_result.get('url_webpay') # Acceso como diccionario
            if not final_url_from_transbank:
                logger.error("No se recibió url_webpay de Transbank después del commit. Redirigiendo directamente a pago_exitoso_final_propia.")
                return redirect('pago_exitoso_final_propia') # Fallback si Transbank no da la URL

            # Renderiza una plantilla simple que hace un POST/redirect al `final_url_from_transbank`
            # ESTO ES LO QUE TRANSBANK ESPERA DE TU RETURN_URL
            return render(request, 'ferremasApp/transbank_final_redirect.html', {
                'url': final_url_from_transbank,
                'token': token # El token_ws final
            })

        else:
            # La transacción fue rechazada o no autorizada
            # Acceso a description también como diccionario
            response_code_description = tbk_result.get('response_code_description', 'Transacción rechazada o error desconocido por Transbank.')
            if not response_code_description:
                response_code_description = "Transacción rechazada o error desconocido por Transbank (sin descripción específica)."

            logger.warning(f"Pago Transbank rechazado o no autorizado. Respuesta del SDK: {tbk_result}")
            messages.error(request, f"El pago fue rechazado: {response_code_description}. Inténtelo de nuevo.")
            return redirect('pago_fallido')
            
    except Exception as e:
        error_msg = f"Ocurrió un error inesperado al procesar la confirmación del pago. Detalles: {e}"
        logger.error(error_msg, exc_info=True)
        messages.error(request, error_msg)
        return redirect('pago_fallido')

@csrf_exempt
def pago_fallido(request):
    """
    Gestiona los pagos fallidos o anulados.
    """
    # Eliminar datos de Transbank de la sesión si existen
    if 'transbank_data' in request.session:
        del request.session['transbank_data']
        request.session.modified = True

    # También elimina los datos de la boleta final si quedaron de un intento anterior
    if 'boleta_final_data' in request.session:
        del request.session['boleta_final_data']
        request.session.modified = True

    token_ws = request.GET.get("token_ws") or request.POST.get("token_ws")
    tbk_token = request.GET.get("TBK_TOKEN") or request.POST.get("TBK_TOKEN") # Este es el token que indica anulación de Transbank

    error_message_display = "El pago ha fallado o fue anulado. Por favor, revisa tus datos e inténtalo nuevamente."

    # Si Transbank nos envía TBK_TOKEN, significa que el usuario anuló en la pasarela.
    if tbk_token:
        error_message_display = "La transacción fue anulada por el usuario en el formulario de Transbank. Puedes intentarlo de nuevo."
    elif token_ws:
        # Podríamos hacer un reverse lookup del token para ver si fue rechazado por Transbank,
        # pero para simplificar, si hay token pero no es éxito, asumimos fallo.
        pass

    messages.error(request, error_message_display)
    context = {'error_message': error_message_display}
    return render(request, 'ferremasApp/pago_fallido.html', context)


# ===================================================================================
# NUEVA VISTA: Para mostrar la página de éxito real al usuario
# ===================================================================================
def pago_exitoso_final_propia(request):
    """
    Esta vista es la que finalmente renderiza la plantilla de éxito después
    de que Transbank haya completado su flujo de redirección a nuestra final_url.
    Recupera los datos de la boleta de la sesión.
    """
    # Recupera los datos que guardaste en la sesión en pago_exito
    boleta_data = request.session.pop('boleta_final_data', None)
    request.session.modified = True

    if not boleta_data:
        # Esto ocurre si el usuario llega aquí directamente o sin una sesión válida de pago exitoso
        messages.error(request, "No se encontraron los detalles de la transacción exitosa. Si cree que fue un error, contacte a soporte.")
        return redirect('tienda') # O a una página de estado del pedido

    context = {
        'amount': boleta_data.get('amount'),
        'buy_order': boleta_data.get('buy_order'),
        'authorization_code': boleta_data.get('authorization_code'),
        'transaction_date': boleta_data.get('transaction_date'),
        'card_number': boleta_data.get('card_number'),
        'boleta_id': boleta_data.get('boleta_id'),
    }
    return render(request, 'ferremasApp/pago_exitoso.html', context)
# ====================================================================
# Funciones de Carrito (Unificadas y Mejoradas)
# ====================================================================

def tienda(request):
    productos = Producto.objects.all()
    categorias_disponibles = Categoria.objects.all()
    query = request.GET.get('q')
    categoria_seleccionada = request.GET.get('categoria')

    if query:
        productos = productos.filter(nombre__icontains=query)
    
    if categoria_seleccionada and categoria_seleccionada != '':
        productos = productos.filter(categoria__id=categoria_seleccionada)

    context = {
        'productos': productos,
        'categorias_disponibles': categorias_disponibles,
        'query': query,
        'categoria_seleccionada': categoria_seleccionada,
    }
    return render(request, "ferremasApp/tienda.html", context)

@require_POST
def agregar_al_carrito(request):
    """
    Agrega un producto al carrito.
    Espera producto_id y opcionalmente cantidad via POST en formato JSON.
    Puede manejar solicitudes AJAX.
    """
    print("--- INICIANDO agregar_al_carrito ---")
    print(f"Request method: {request.method}")
    print(f"Request body: {request.body}")

    if not request.body:
        print("DEBUG: Cuerpo de la solicitud vacío.")
        return JsonResponse({'success': False, 'message': 'Cuerpo de la solicitud vacío.'}, status=400)

    try:
        data = json.loads(request.body)
        producto_id = data.get('producto_id')
        cantidad_a_agregar = int(data.get('cantidad', 1))

        print(f"DEBUG: producto_id recibido: {producto_id}, cantidad_a_agregar: {cantidad_a_agregar}")

        if not producto_id:
            print("DEBUG: ID de producto no proporcionado.")
            return JsonResponse({'success': False, 'message': 'ID de producto no proporcionado.'}, status=400)
        
        if cantidad_a_agregar <= 0:
            print("DEBUG: Cantidad a agregar <= 0.")
            return JsonResponse({'success': False, 'message': 'La cantidad a agregar debe ser al menos 1.'}, status=400)

        producto = get_object_or_404(Producto, id=producto_id)
        
        carrito = request.session.get('carrito', {})
        
        product_id_str = str(producto.id) 
        cantidad_actual_en_carrito = carrito.get(product_id_str, 0)
        
        print(f"DEBUG: Producto: {producto.nombre}, Stock DB: {producto.stock}")
        print(f"DEBUG: Cantidad actual en carrito (sesión): {cantidad_actual_en_carrito}")

        cantidad_despues_de_agregar = cantidad_actual_en_carrito + cantidad_a_agregar
        print(f"DEBUG: Cantidad después de intentar agregar: {cantidad_despues_de_agregar}")

        # --- Lógica de stock ---
        if producto.stock <= 0:
            message = f"Producto '{producto.nombre}' sin stock disponible."
            print(f"DEBUG: Error - {message}") # Depuración
            messages.error(request, message) 
            return JsonResponse({'success': False, 'message': message, 'total_items': sum(carrito.values())}, status=400)

        if cantidad_despues_de_agregar > producto.stock:
            cantidad_maxima_posible_en_carrito = producto.stock
            cantidad_realmente_a_agregar = max(0, cantidad_maxima_posible_en_carrito - cantidad_actual_en_carrito)

            if cantidad_realmente_a_agregar == 0:
                message = (f"No puedes agregar más de '{producto.nombre}'. Ya tienes "
                           f"{cantidad_actual_en_carrito} en el carrito y el stock total es {producto.stock}.")
                print(f"DEBUG: Error - {message}") # Depuración
                messages.error(request, message)
                return JsonResponse({'success': False, 'message': message, 'total_items': sum(carrito.values())}, status=400)
            else:
                carrito[product_id_str] = cantidad_actual_en_carrito + cantidad_realmente_a_agregar
                message_type = 'warning'
                message_text = (f"Se han añadido {cantidad_realmente_a_agregar} unidades de '{producto.nombre}'. "
                                f"El stock disponible solo permitía añadir hasta {producto.stock} en total."
                                f"Ahora tienes {carrito[product_id_str]} unidades en el carrito.")
                print(f"DEBUG: Éxito parcial - {message_text}") # Depuración
        else:
            carrito[product_id_str] = cantidad_despues_de_agregar
            message_type = 'success'
            message_text = f"'{producto.nombre}' ha sido agregado al carrito."
            print(f"DEBUG: Éxito total - {message_text}") # Depuración

        request.session['carrito'] = carrito
        request.session.modified = True 

        total_items_in_cart = sum(carrito.values())
        print(f"DEBUG: Carrito final en sesión: {request.session['carrito']}")
        print(f"DEBUG: Total de ítems en carrito (para frontend): {total_items_in_cart}")

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True, 
                'message': message_text, 
                'total_items': total_items_in_cart
            }, status=200)
        
        messages.add_message(request, getattr(messages, message_type.upper()), message_text)
        print("--- FINALIZANDO agregar_al_carrito (redirigiendo) ---")
        return redirect('tienda')

    except json.JSONDecodeError:
        print("DEBUG: Error - JSONDecodeError.")
        return JsonResponse({'success': False, 'message': 'Petición inválida: El cuerpo de la solicitud no es JSON válido.'}, status=400)
    except Producto.DoesNotExist:
        message = "El producto no existe."
        print(f"DEBUG: Error - {message}")
        messages.error(request, message)
        return JsonResponse({'success': False, 'message': message, 'total_items': sum(request.session.get('carrito', {}).values())}, status=404)
    except ValueError:
        message = "Cantidad o ID de producto inválido."
        print(f"DEBUG: Error - {message}")
        messages.error(request, message)
        return JsonResponse({'success': False, 'message': message, 'total_items': sum(request.session.get('carrito', {}).values())}, status=400)
    except Exception as e:
        message = f"Error interno del servidor al agregar producto al carrito: {str(e)}"
        print(f"DEBUG: Error INESPERADO en agregar_al_carrito: {e}", exc_info=True) # exc_info para traceback
        messages.error(request, message)
        carrito_actual = request.session.get('carrito', {})
        total_items_on_error = sum(carrito_actual.values())
        return JsonResponse({'success': False, 'message': message, 'total_items': total_items_on_error}, status=500)

@require_POST
def eliminar_del_carrito(request, producto_id): 
    """
    Elimina un producto del carrito.
    Esperado via AJAX POST.
    """
    try:
        carrito = request.session.get('carrito', {})
        producto_id_str = str(producto_id) # Asegura que la clave sea un string

        if producto_id_str in carrito:
            del carrito[producto_id_str]
            request.session['carrito'] = carrito
            request.session.modified = True 

            # RECALCULAR total_items_in_cart
            # Si carrito.values() devuelve directamente las cantidades
            total_items_in_cart = sum(carrito.values()) 
            
            # RECALCULAR total_carrito_final (necesita precios de productos)
            total_carrito_final = 0
            if carrito:
                # Obtener los IDs de los productos que quedan en el carrito
                product_ids_remaining = [int(p_id) for p_id in carrito.keys()]
                
                # CUIDADO: Necesitas importar tu modelo Producto para esto
                # Suponiendo que tu modelo se llama 'Producto'
                # Filtra los productos de la base de datos usando los IDs que quedan en el carrito
                from .models import Producto # Asegúrate de que esta importación sea correcta
                productos_en_db = Producto.objects.filter(id__in=product_ids_remaining)
                
                # Calcular el total sumando (precio del producto * cantidad en carrito)
                for p_db in productos_en_db:
                    cantidad_en_carrito = carrito.get(str(p_db.id), 0) # Asegúrate de obtener la cantidad como un int
                    total_carrito_final += p_db.precio * cantidad_en_carrito
            
            return JsonResponse({'success': True, 'message': 'Producto eliminado con éxito.', 'total_items': total_items_in_cart, 'total_carrito': float(total_carrito_final)})
        else:
            return JsonResponse({'success': False, 'message': 'El producto no se encontró en el carrito.'}, status=404)

    except Exception as e:
        print(f"DEBUG: Error al eliminar producto del carrito: {e}")
        return JsonResponse({'success': False, 'message': f'Error al eliminar producto: {str(e)}'}, status=500)

@require_POST
def actualizar_cantidad_carrito(request):
    """
    Actualiza la cantidad de un producto en el carrito.
    Espera product_id y cantidad via JSON POST.
    """
    try:
        data = json.loads(request.body)
        product_id = str(data.get('producto_id')) # Asegurarse de que sea string para las claves de sesión
        new_quantity = int(data.get('cantidad'))

        if new_quantity <= 0:
            # Si la nueva cantidad es 0 o menos, eliminar el producto
            return eliminar_del_carrito(request, int(product_id)) # Reutilizamos la función de eliminar

        carrito = request.session.get('carrito', {})
        
        if product_id not in carrito:
            return JsonResponse({'success': False, 'message': 'El producto no está en el carrito.'}, status=404)

        producto = get_object_or_404(Producto, id=int(product_id)) # Convertir a int para la búsqueda en DB

        if new_quantity > producto.stock:
            message = f"No hay suficiente stock para '{producto.nombre}'. Solo quedan {producto.stock} disponibles."
            # Ajustar la cantidad a la máxima disponible
            new_quantity = producto.stock 
            # Esto puede ser un error si new_quantity ajustada es 0, pero la lógica de eliminar_del_carrito lo cubre.
            if new_quantity == 0:
                return eliminar_del_carrito(request, int(product_id))

            messages.warning(request, message) # Mensaje para el usuario
            
        # Actualizar la cantidad del producto en el carrito
        # Aquí es donde debemos ser más cuidadosos con cómo se guarda el carrito.
        # Si tu carrito en sesión guarda solo la cantidad:
        carrito[product_id] = new_quantity
        # Si tu carrito en sesión guarda un diccionario por producto (ej. {'id':..., 'nombre':..., 'precio':..., 'cantidad':...})
        # deberías hacer esto:
        # carrito[product_id]['cantidad'] = new_quantity


        request.session['carrito'] = carrito
        request.session.modified = True

        # Recalcular el total general del carrito y el subtotal del ítem actualizado
        total_carrito_actualizado = 0
        total_items_in_cart = 0
        items_for_response = [] # Para devolver los detalles actualizados del carrito
        
        # Recuperar los detalles completos de los productos para la respuesta
        product_ids_in_cart = [int(p_id) for p_id in carrito.keys()]
        productos_en_db = Producto.objects.filter(id__in=product_ids_in_cart)
        productos_dict = {str(p.id): p for p in productos_en_db} # Crear un diccionario para fácil acceso

        for p_id_str, cantidad_en_carrito in carrito.items():
            if p_id_str in productos_dict:
                p_db = productos_dict[p_id_str]
                # Si tu carrito en sesión solo guarda la cantidad, entonces p_db.precio es el precio actual del producto
                precio_unitario = float(p_db.precio) 
                
                subtotal_item = precio_unitario * cantidad_en_carrito
                total_carrito_actualizado += subtotal_item
                total_items_in_cart += cantidad_en_carrito
                
                items_for_response.append({
                    'id': p_db.id,
                    'nombre': p_db.nombre,
                    'precio': precio_unitario,
                    'cantidad': cantidad_en_carrito,
                    'subtotal': subtotal_item,
                    'stock': p_db.stock, # Incluir el stock actual
                    'imagen': p_db.imagen.url if p_db.imagen else ''
                })

        return JsonResponse({
            'success': True,
            'message': message if 'message' in locals() else 'Cantidad actualizada con éxito.',
            'total_items': total_items_in_cart,
            'total_carrito': float(total_carrito_actualizado),
            'updated_item_id': int(product_id), # ID del ítem que se actualizó
            'new_quantity': new_quantity, # La cantidad final aplicada
            'new_item_subtotal': float(producto.precio) * new_quantity, # Subtotal del ítem específico
            'items': items_for_response # Retornar todos los ítems actualizados es más robusto
        })

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Petición inválida: No es un JSON válido.'}, status=400)
    except Producto.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Producto no encontrado.'}, status=404)
    except Exception as e:
        print(f"DEBUG: Error al actualizar cantidad en carrito: {e}")
        return JsonResponse({'success': False, 'message': f'Error al actualizar la cantidad: {str(e)}'}, status=500)
def get_cart_items(request):
    """
    Devuelve los ítems del carrito y el total para mostrarlos en la página del carrito.
    """
    carrito = request.session.get('carrito', {})
    items_data = []
    total_carrito = 0
    total_items_count = 0

    if not carrito:
        return JsonResponse({'items': [], 'total_carrito': 0, 'total_items_count': 0})

    # Obtener todos los productos del carrito de la base de datos de una sola vez
    product_ids = [int(p_id) for p_id in carrito.keys()]
    productos_en_db = Producto.objects.filter(id__in=product_ids)
    productos_dict = {str(p.id): p for p in productos_en_db} # Mapear por ID para fácil acceso

    for product_id_str, cantidad_en_sesion in carrito.items():
        if product_id_str in productos_dict:
            producto = productos_dict[product_id_str]
            # Asegurarse de que la cantidad en sesión no exceda el stock actual
            cantidad_final = min(cantidad_en_sesion, producto.stock)
            if cantidad_final <= 0: # Si no hay stock o cantidad es 0, se puede considerar eliminarlo del carrito aquí
                # Si deciden eliminarlo del carrito si el stock es 0, descomentar y manejar la sesión
                # del carrito aquí o en una vista de limpieza programada
                continue 

            subtotal = float(producto.precio) * cantidad_final
            total_carrito += subtotal
            total_items_count += cantidad_final

            items_data.append({
                'id': producto.id,
                'nombre': producto.nombre,
                'precio': float(producto.precio), # Convertir Decimal a float para JSON
                'cantidad': cantidad_final,
                'subtotal': subtotal,
                'stock': producto.stock, # Para que el frontend pueda validar max
                'imagen': producto.imagen.url if producto.imagen else '/static/img/no_image.png' # Ruta por defecto si no hay imagen
            })
        else:
            # Producto en el carrito de sesión que ya no existe en la DB
            # Se podría considerar limpiar el carrito de sesión aquí, pero lo haremos de forma más robusta
            print(f"Advertencia: Producto con ID {product_id_str} en carrito, pero no existe en DB.")
            # Si se desea eliminar automáticamente el producto del carrito si no existe en la DB
            # del request.session['carrito'][product_id_str]
            # request.session.modified = True

    # Si tu carrito de sesión solo guarda {id: cantidad}, y no los detalles completos del producto,
    # necesitarás una lógica para reconstruir los detalles para el frontend.
    # El bucle anterior ya hace eso.
    
    return JsonResponse({
        'items': items_data,
        'total_carrito': float(total_carrito), # Asegúrate de que es float para JSON
        'total_items_count': total_items_count
    })


def calcular_total_carrito(carrito_session):
    """
    Función auxiliar para calcular el total del carrito,
    consultando la base de datos para los precios actuales de los productos.
    """
    total = decimal.Decimal(0)
    producto_ids_en_carrito = [int(p_id) for p_id in carrito_session.keys()]

    if producto_ids_en_carrito:
        productos_db = Producto.objects.filter(id__in=producto_ids_en_carrito)
        productos_dict = {p.id: p for p in productos_db}

        for producto_id_str, cantidad in carrito_session.items():
            producto = productos_dict.get(int(producto_id_str))
            if producto:
                total += producto.precio * cantidad
    return total

def ver_carrito(request):
    """
    Muestra el contenido del carrito.
    Ajusta cantidades o elimina productos si el stock o la existencia en DB ha cambiado.
    """
    carrito_session = request.session.get('carrito', {})
    items_en_carrito = []
    total_carrito = decimal.Decimal(0)
    producto_ids_en_carrito = [int(p_id) for p_id in carrito_session.keys()]

    productos_a_eliminar_del_carrito = []

    if producto_ids_en_carrito:
        productos_db = Producto.objects.filter(id__in=producto_ids_en_carrito)
        productos_dict = {p.id: p for p in productos_db}

        for producto_id_str, cantidad in carrito_session.items():
            producto_id = int(producto_id_str)
            producto = productos_dict.get(producto_id)

            if producto:
                # Ajuste de cantidad si excede el stock
                if cantidad > producto.stock:
                    messages.warning(request, f"La cantidad de '{producto.nombre}' en tu carrito ha sido ajustada a {producto.stock} debido a la disponibilidad de stock.")
                    cantidad = producto.stock
                    if cantidad == 0:
                        productos_a_eliminar_del_carrito.append(producto_id_str)
                        continue # Pasa al siguiente item si la cantidad se ajustó a 0
                    request.session['carrito'][producto_id_str] = cantidad
                    request.session.modified = True # Marcamos la sesión como modificada

                subtotal = producto.precio * cantidad
                total_carrito += subtotal
                items_en_carrito.append({
                    'producto': producto,
                    'cantidad': cantidad,
                    'subtotal': subtotal
                })
            else:
                # Producto no encontrado en DB, marcar para eliminación
                productos_a_eliminar_del_carrito.append(producto_id_str)
                messages.warning(request, f"Un producto en tu carrito (ID: {producto_id_str}) ya no está disponible y será eliminado.")

    # Eliminar productos del carrito de sesión si fueron marcados para ello
    for prod_id_to_remove in productos_a_eliminar_del_carrito:
        if prod_id_to_remove in request.session['carrito']:
            del request.session['carrito'][prod_id_to_remove]

    # Guardar la sesión si hubo modificaciones (por ajustes de stock o eliminaciones)
    if productos_a_eliminar_del_carrito or any(item.get('cantidad_ajustada') for item in items_en_carrito):
        request.session.modified = True

    context = {
        'productos_en_carrito': items_en_carrito, # Renombrado para consistencia con el template
        'total_carrito': total_carrito,
    }
    return render(request, "ferremasApp/carrito.html", context)

def limpiar_carrito(request):
    """
    Vacía todo el carrito de la sesión.
    Puede manejar solicitudes AJAX.
    """
    if 'carrito' in request.session:
        del request.session['carrito']
        request.session.modified = True
        messages.info(request, "El carrito ha sido vaciado.")
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'message': 'Carrito vaciado.', 'total_items': 0})
    return redirect('tienda')

def get_cart_total(request):
    """
    Devuelve el número total de items en el carrito (para el icono del carrito).
    """
    carrito = request.session.get('carrito', {})
    total_items = sum(carrito.values())
    return JsonResponse({'total_items': total_items})

def get_cart_details_json(request):
    """
    Devuelve los detalles completos del carrito en formato JSON.
    Realiza ajustes de stock y elimina productos no disponibles.
    """
    carrito_session = request.session.get('carrito', {})
    items_data = []
    total_carrito = decimal.Decimal(0)

    producto_ids_en_carrito = [int(p_id) for p_id in carrito_session.keys()]
    products_to_remove = []
    session_modified_flag = False # Flag para saber si la sesión necesita ser guardada

    if producto_ids_en_carrito:
        productos_db = Producto.objects.filter(id__in=producto_ids_en_carrito)
        productos_dict = {p.id: p for p in productos_db}

        for producto_id_str, cantidad in carrito_session.items():
            producto_id = int(producto_id_str)
            producto = productos_dict.get(producto_id)

            if producto:
                # Ajuste de cantidad si excede el stock
                if cantidad > producto.stock:
                    cantidad = producto.stock
                    if cantidad == 0:
                        products_to_remove.append(producto_id_str)
                        messages.warning(request, f"'{producto.nombre}' fue eliminado de tu carrito porque se agotó el stock.")
                        session_modified_flag = True
                        continue
                    request.session['carrito'][producto_id_str] = cantidad
                    messages.warning(request, f"La cantidad de '{producto.nombre}' en tu carrito ha sido ajustada a {cantidad} debido a la disponibilidad de stock.")
                    session_modified_flag = True

                subtotal = producto.precio * cantidad
                total_carrito += subtotal
                items_data.append({
                    'id': producto.id,
                    'nombre': producto.nombre,
                    'precio': str(producto.precio), # Convertir Decimal a str para JSON
                    'cantidad': cantidad,
                    'subtotal': str(subtotal), # Convertir Decimal a str para JSON
                    'imagen_url': producto.imagen.url if producto.imagen else settings.STATIC_URL + 'img/no-image.png',
                    'stock': producto.stock
                })
            else:
                products_to_remove.append(producto_id_str)
                messages.warning(request, f"Un producto en tu carrito (ID: {producto_id_str}) ya no está disponible y será eliminado.")
                session_modified_flag = True

    for p_id_to_remove in products_to_remove:
        if p_id_to_remove in request.session['carrito']:
            del request.session['carrito'][p_id_to_remove]
            session_modified_flag = True # Asegurar que el flag esté en True

    if session_modified_flag:
        request.session.modified = True

    return JsonResponse({
        'success': True,
        'items': items_data,
        'total_carrito': str(total_carrito), # Convertir Decimal a str para JSON
        'total_items_count': sum(carrito_session.values())
    })

# ====================================================================
# Funciones Adicionales
# ====================================================================

# Las vistas `enviar_contacto` y `vista_productos_html` originales se han eliminado
# ya que eran redundantes o menos completas que las ya existentes.

def reseñas(request):
    # Obtener todas las reseñas ordenadas por fecha de creación descendente
    todas_las_reseñas = Resena.objects.all().order_by('-fecha_creacion')
    context = {
        'reseñas': todas_las_reseñas
    }
    return render(request, 'ferremasApp/reseñas.html', context)

def enviar_reseña(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        comentario = request.POST.get('comentario')
        puntuacion = request.POST.get('puntuacion')

        if not all([nombre, comentario, puntuacion]):
            messages.error(request, 'Todos los campos son obligatorios para enviar una reseña.')
            return redirect('reseñas') # Redirige a la página de reseñas para mostrar el error

        try:
            puntuacion = int(puntuacion)
            if not (1 <= puntuacion <= 5):
                raise ValueError("La puntuación debe estar entre 1 y 5.")
        except ValueError:
            messages.error(request, 'La puntuación debe ser un número entre 1 y 5.')
            return redirect('reseñas')

        try:
            Resena.objects.create(
                nombre=nombre,
                comentario=comentario,
                puntuacion=puntuacion
            )
            messages.success(request, '¡Tu reseña ha sido enviada con éxito!')
        except Exception as e:
            messages.error(request, f'Ocurrió un error al guardar tu reseña: {e}')
            logger.error(f"Error al guardar reseña: {e}", exc_info=True)
        
        return redirect('reseñas') # Redirige de vuelta a la página de reseñas para ver la nueva reseña
    else:
        # Si alguien intenta acceder a /enviar-reseña/ con GET, lo redirigimos a la página principal de reseñas
        return redirect('reseñas')
