# Image Flask générique du TP RT0705
FROM python:3.12-slim

# Pas de fichiers .pyc dans le volume, journaux affichés immédiatement
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_APP=app.py

# Utilisateur non root :
ARG UID=1000
RUN useradd --create-home --uid "${UID}" flask

# Dépendances Python du projet
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Arborescence d'une application Flask :
RUN mkdir -p /app/templates /app/static && chown -R flask:flask /app
WORKDIR /app
USER flask

# Le port d'écoute est donné par FLASK_RUN_PORT (docker-compose.yml)
CMD ["flask", "run", "--host=0.0.0.0"]
