# MatchGuard - tournament-service
# Author: Elias
FROM python:3.11-slim

WORKDIR /app

# Keep pip quiet and don't cache wheels in the image
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 5001

# gunicorn in prod-ish mode, 2 workers is plenty for a course project
CMD ["gunicorn", "--bind", "0.0.0.0:5001", "--workers", "2", "app:app"]
