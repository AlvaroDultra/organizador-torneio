from django.urls import path
from django.http import JsonResponse

def ping(_):
    return JsonResponse({"pong": True})

urlpatterns = [
    path("ping/", ping),
]
