from django.shortcuts import render

# Create your views here.

from django.http import HttpResponse

def index(request):
    return HttpResponse("Hola holita. Gifts index.")

def detail(request, gift_id):
    return HttpResponse("Detalle del regalo %s." % gift_id)

def mark(request, gift_id):
    return HttpResponse("Se ha marcado como hecho el regalo %s." % gift_id)
