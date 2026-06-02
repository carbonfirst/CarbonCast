import os
from pathlib import Path

from celery import Celery

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if load_dotenv:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CarbonCastAPI.settings')

app = Celery('CarbonCastAPI')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
