FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/core_saas/requirements.txt .

RUN pip install --upgrade pip setuptools wheel && pip install -r requirements.txt

COPY . .
