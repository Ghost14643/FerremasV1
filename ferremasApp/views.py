from django.shortcuts import render, HttpResponse
import requests
from datetime import date
from django.http import JsonResponse
import json  # Usaremos json para la API de la CMF
from rest_framework.permissions import AllowAny
from rest_framework import viewsets





# Tu API Key de la CMF
API_KEY_CMF = "793d989c2c3b0987eb56404ed529a24910086f80"
URL_BASE_CMF = "https://api.cmfchile.cl/api-sbifv3/recursos_api"

# Create your views here.

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

def obtener_valor_dolar_cmf():
    """Obtiene el valor del Dólar del día actual desde la API de la CMF."""
    url = f"{URL_BASE_CMF}/dolar?apikey={API_KEY_CMF}&formato=json"
    try:
        response = requests.get(url)
        response.raise_for_status()  # Lanza excepción para errores HTTP
        data = response.json()
        if data and data.Dolares and data.Dolares.length > 0 and data.Dolares[0].Dolar:
            valor = data["Dolares"][0]["Dolar"]["Valor"].replace(',', '.')
            return float(valor)
        else:
            print("Formato de respuesta de la API de la CMF inesperado.")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Error al obtener datos del dólar desde la CMF: {e}")
        return None
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as e:
        print(f"Error al procesar la respuesta de la API de la CMF: {e}")
        return None

def api_conversion(request):
    valor = obtener_valor_dolar_cmf()
    if valor is not None:
        return JsonResponse({"valor": valor})
    else:
        return JsonResponse({"error": "No se pudo obtener el valor del dólar desde la CMF"})
    
