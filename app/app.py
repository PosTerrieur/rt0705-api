"""API REST de la vidéothèque - version de test des conteneurs

- le conteneur répond (/api/sante)
- le volume de données est bien monté et lisible (/api/test/videotheque)
"""
import json
import os
from pathlib import Path

from flask import Flask, jsonify

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
FICHIER_VIDEOTHEQUE = DATA_DIR / "videotheque.json"

app = Flask(__name__)
app.json.ensure_ascii = False   # garde les accents lisibles dans les réponses
app.json.sort_keys = False      # conserve l'ordre des champs du fichier


def erreur(code_http, code, message):
    """Réponse d'erreur au format commun défini dans l'architecture"""
    return jsonify(erreur={"code": code, "message": message}), code_http


@app.get("/api/sante")
def sante():
    return jsonify(statut="ok")


@app.get("/api/test/videotheque")
def videotheque():
    """Renvoie le contenu brut du fichier de données"""
    if not FICHIER_VIDEOTHEQUE.exists():
        return erreur(404, "FICHIER_ABSENT",
                      f"Fichier introuvable : {FICHIER_VIDEOTHEQUE}")
    try:
        with FICHIER_VIDEOTHEQUE.open(encoding="utf-8") as f:
            donnees = json.load(f)
    except json.JSONDecodeError as e:
        return erreur(500, "FICHIER_INVALIDE",
                      f"JSON invalide dans {FICHIER_VIDEOTHEQUE.name} : {e}")
    return jsonify(donnees)
