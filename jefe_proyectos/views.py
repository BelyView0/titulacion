from django.http import HttpResponse

def inicio(request):
    return HttpResponse("Hola, este es el módulo de administración")