"""Routes HTTP de l'API : lecture de la requête, appel du service, réponse JSON

Chaque module définit un Blueprint « bp », enregistré sous le préfixe /api dans app.py
"""
from routes import films, metadonnees, personnes, prets, sessions, suivis, supports, utilisateurs

BLUEPRINTS = [module.bp for module in
              (sessions, utilisateurs, suivis, films, supports, personnes, prets, metadonnees)]
