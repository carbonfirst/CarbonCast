#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
from pathlib import Path

from django.conf import settings

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None



def main():
    """Run administrative tasks."""
    if load_dotenv:
        load_dotenv(Path(__file__).resolve().parent / ".env", override=False)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CarbonCastAPI.settings')
    os.environ.setdefault('REQUIRES_AUTH', 'True')    
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    
    args = sys.argv
    if "--rmauth" in args:
        idx = args.index("--rmauth")
        os.environ['REQUIRES_AUTH'] = 'False'
        args.pop(idx)
        execute_from_command_line(args)
    else:
        execute_from_command_line(args)


if __name__ == '__main__':
    main()
