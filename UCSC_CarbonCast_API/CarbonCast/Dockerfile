# CarbonCast API + Celery image.
# Python 3.10 required: TensorFlow 2.9.x / NumPy 1.23.x do not support 3.11+.
FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# libeccodes0: runtime dependency of cfgrib (GRIB weather file parsing)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libeccodes0 \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

COPY . /app/

# manage.py lives here; helper.py resolves real_time/ four parents up (/app)
WORKDIR /app/src/CarbonCastAPI

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
