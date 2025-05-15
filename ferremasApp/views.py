from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
import requests
import uuid
import json

from django.views.decorators.csrf import csrf_exempt

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
    return render(request, "ferremasApp/contacto.html")

def carrito_view(request):
    return render(request, 'ferremasApp/carrito.html')


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
            "amount": float(total),
            "return_url": return_url
        }

        try:
            response = requests.post(
                TBK_API_BASE_URL,
                headers=headers,
                json=data
            )
            if response.status_code == 200:
                respuesta = response.json()
                # Aquí está el cambio para que use la plantilla correcta
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

    return redirect('carrito')


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
            return render(request, 'ferremasApp/pago_exito.html', {
                'response': resultado
            })
        else:
            print(f"Error al confirmar la transacción: {response.text}")
            return HttpResponse("Error al confirmar la transacción", status=response.status_code)
    except Exception as e:
        print(f"Error al confirmar transacción: {e}")
        return HttpResponse("Error al procesar pago", status=500)
