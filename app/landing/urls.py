from django.urls import path
from .views import future_plans, view

urlpatterns = [
    path('', view, name='home'),
    path('future-plans/', future_plans, name='future_plans'),
]
