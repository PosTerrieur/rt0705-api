"""Routes des supports (F07) : création sous le film, puis accès direct par id"""
from flask import Blueprint, jsonify, url_for

import auth
import db
from services import supports
from services.commun import trouver
from validation import corps_json

bp = Blueprint("supports", __name__)


@bp.get("/films/<film_id>/supports")
def lister_du_film(film_id):
    with db.lecture() as donnees:
        trouver(donnees["films"], film_id, "Film")
        resultat = [supports.representation(donnees, s) for s in supports.du_film(donnees, film_id)]
    return jsonify(resultat)


@bp.post("/films/<film_id>/supports")
@auth.admin_requis
def creer(film_id):
    payload = corps_json()
    with db.ecriture() as donnees:
        support = supports.creer(donnees, film_id, payload)
        resultat = supports.representation(donnees, support)
    entetes = {"Location": url_for(".obtenir", support_id=support["id"])}
    return jsonify(resultat), 201, entetes


@bp.get("/supports/<support_id>")
def obtenir(support_id):
    with db.lecture() as donnees:
        support = trouver(donnees["supports"], support_id, "Support")
        resultat = supports.representation(donnees, support)
    return jsonify(resultat)


@bp.patch("/supports/<support_id>")
@auth.admin_requis
def modifier(support_id):
    payload = corps_json()
    with db.ecriture() as donnees:
        support = supports.modifier(donnees, support_id, payload)
        resultat = supports.representation(donnees, support)
    return jsonify(resultat)


@bp.delete("/supports/<support_id>")
@auth.admin_requis
def supprimer(support_id):
    with db.ecriture() as donnees:
        supports.supprimer(donnees, support_id)
    return "", 204
