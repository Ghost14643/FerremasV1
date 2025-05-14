from django.shortcuts import render, HttpResponse

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

