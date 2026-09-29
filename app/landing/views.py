from django.shortcuts import render

# Create your views here.
def view(request):
    return render(request, 'landing/index.html', {'project_name': 'PyForge'})


def future_plans(request):
    return render(request, 'landing/future_plans.html')
