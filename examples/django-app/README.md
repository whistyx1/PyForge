## How to run?

which python

## Create venv
python -m venv .venv
source .venv/bin/activate

## Install dependencies
from examples/django-app run:

pip install -r requirements.txt

## Run app

python -m django startproject config . - this command for creating basic structure of django app

python manage.py migrate.  - this command for ceatigng local database

python manage.py runserver.  - run server. expeciting see welcome django page by this address http://127.0.0.1:8000/

## Check status

python manage.py startapp core. - this command adds fuctional part of django app

then rewrite core/views.py with

from django.http import JsonResponse


def health(request):
    return JsonResponse({"status": "ok"})

and config/urls.py

from django.contrib import admin
from django.urls import path

from core.views import health


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health", health),
]

the run  python manage.py runserver

and

open: http://127.0.0.1:8000/health

excpected answer: status: ok