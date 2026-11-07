from django.urls import path
from .views import deployment_setup, documentation, future_plans, view

urlpatterns = [
    path('', view, name='home'),
    path('future-plans/', future_plans, name='future_plans'),
    path('documentation/', documentation, name='documentation'),
    path('deploy/', deployment_setup, name='deployment_setup'),
]
