"""Routes /api/utilisateurs/me/suivis : suivi personnel des films (F14)"""
from flask import Blueprint, g, jsonify

import auth
import db
from services import suivis
from validation import corps_json

bp = Blueprint("suivis", __name__)


@bp.get("/utilisateurs/me/suivis")
@auth.connexion_requise
def lister():
    with db.lecture() as donnees:
        resultat = suivis.de_l_utilisateur(donnees, g.utilisateur["id"])
    return jsonify(resultat)


@bp.get("/utilisateurs/me/suivis/<film_id>")
@auth.connexion_requise
def obtenir(film_id):
    with db.lecture() as donnees:
        resultat = suivis.obtenir(donnees, g.utilisateur["id"], film_id)
    return jsonify(resultat)


@bp.put("/utilisateurs/me/suivis/<film_id>")
@auth.connexion_requise
def enregistrer(film_id):
    payload = corps_json()
    with db.ecriture() as donnees:
        suivi, cree = suivis.enregistrer(donnees, g.utilisateur["id"], film_id, payload)
    return jsonify(suivi), (201 if cree else 200)
