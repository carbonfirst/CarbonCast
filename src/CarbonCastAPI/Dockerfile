FROM python:3.9-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV MPLCONFIGDIR=/tmp/matplotlib
ENV XDG_CACHE_HOME=/tmp

WORKDIR /CarbonCast

COPY requirements.txt /tmp/requirements.txt
COPY src/CarbonCastAPI/requirements.txt /tmp/requirements-api.txt

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /tmp/requirements.txt \
    && pip install --no-cache-dir -r /tmp/requirements-api.txt \
    && mkdir -p /tmp/matplotlib

COPY . /CarbonCast

EXPOSE 8000
