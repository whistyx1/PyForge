import sqlite3
from contextlib import closing
from pathlib import Path

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def health(request):
    try:
        database = Path(settings.DATABASES['default']['NAME'])
        if not database.is_file():
            raise OSError('Database file is missing')
        with closing(sqlite3.connect(f'{database.resolve().as_uri()}?mode=ro', uri=True, timeout=1)) as connection:
            if connection.execute('SELECT 1 FROM django_migrations LIMIT 1').fetchone() != (1,):
                raise sqlite3.DatabaseError('Database has no applied migrations')
    except (OSError, sqlite3.Error, TypeError, ValueError):
        return JsonResponse({'status': 'unavailable'}, status=503)
    return JsonResponse({'status': 'ok'})
