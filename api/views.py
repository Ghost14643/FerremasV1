from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import Producto, Categoria
from .serializers import ProductoSerializer, CategoriaSerializer
from django.db.models import Q

@api_view(['GET'])
def lista_productos(request):
    search = request.GET.get('search')
    productos = Producto.objects.all()

    if search:
        productos = productos.filter(
            Q(nombre__icontains=search) |
            Q(marca__icontains=search) |
            Q(codigo__icontains=search) |
            Q(categoria__nombre__icontains=search)
        )

    serializer = ProductoSerializer(productos, many=True)
    return Response(serializer.data)

@api_view(['GET'])
def lista_categorias(request):
    categorias = Categoria.objects.all()
    serializer = CategoriaSerializer(categorias, many=True)
    return Response(serializer.data)
