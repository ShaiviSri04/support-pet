from django.urls import path
from django.shortcuts import redirect
from . import main

def redirect_to_login(request):
    return redirect('login')

# Combine the root URL pattern with the existing patterns
urlpatterns = [
    path('', redirect_to_login, name='root'),
] + main.urlpatterns 