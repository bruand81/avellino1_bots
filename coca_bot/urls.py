from django.urls import path
from django.views.decorators.csrf import csrf_exempt

from .views import CocaBotView

urlpatterns = [
    path('', csrf_exempt(CocaBotView.as_view()))
]