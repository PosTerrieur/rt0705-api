"""Routes /api/personnes : recherche, filmographie (F16) et correction du nom (F17)"""
from flask import Blueprint, jsonify

import auth
import db
from services import personnes
from services.commun import paginer, trouver
from validation import corps_json, pagination, param_texte

bp = Blueprint("personnes", __name__)


@bp.get("/personnes")
def rechercher():
    texte = param_texte("q")
    page, taille = pagination()
    with db.lecture() as donnees:
        resultats = personnes.rechercher(donnees, texte)
    return jsonify(paginer(resultats, page, taille))


@bp.get("/personnes/<personne_id>")
def obtenir(personne_id):
    with db.lecture() as donnees:
        personne = trouver(donnees["personnes"], personne_id, "Personne")
        resultat = personnes.fiche(donnees, personne)
    return jsonify(resultat)


@bp.patch("/personnes/<personne_id>")
@auth.admin_requis
def renommer(personne_id):
    payload = corps_json()
    with db.ecriture() as donnees:
        personne = personnes.renommer(donnees, personne_id, payload)
        resultat = personnes.fiche(donnees, personne)
    return jsonify(resultat)
