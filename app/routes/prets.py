"""Routes /api/prets : emprunt, retour, consultation (F10 à F13)"""
from flask import Blueprint, g, jsonify, url_for

import auth
import config
import db
from services import prets
from services.commun import paginer
from validation import (Validateur, corps_json, pagination, param_booleen,
                        param_choix, param_texte)

bp = Blueprint("prets", __name__)


@bp.post("/prets")
@auth.connexion_requise
def emprunter():
    v = Validateur(corps_json())
    v.texte("supportId", obligatoire=True, longueur_max=100)
    support_id = v.verifier()["supportId"]

    # Lecture, contrôles RG3/RG4/RG5 et écriture dans la même section verrouillée :
    # deux emprunts simultanés du même support ne peuvent pas réussir tous les deux
    with db.ecriture() as donnees:
        pret = prets.emprunter(donnees, g.utilisateur, support_id)
        resultat = prets.representation(donnees, pret)
    entetes = {"Location": url_for(".obtenir", pret_id=pret["id"])}
    return jsonify(resultat), 201, entetes


@bp.get("/prets")
@auth.connexion_requise
def lister():
    statut = param_choix("statut", config.STATUTS_PRET)
    en_retard = param_booleen("enRetard")
    utilisateur_id = param_texte("utilisateurId")
    page, taille = pagination()

    with db.lecture() as donnees:
        liste = prets.lister(donnees, g.utilisateur, statut, en_retard, utilisateur_id)
        resultats = [prets.representation(donnees, p) for p in liste]
    return jsonify(paginer(resultats, page, taille))


@bp.get("/prets/<pret_id>")
@auth.connexion_requise
def obtenir(pret_id):
    with db.lecture() as donnees:
        resultat = prets.representation(donnees, prets.obtenir(donnees, g.utilisateur, pret_id))
    return jsonify(resultat)


@bp.post("/prets/<pret_id>/retour")
@auth.connexion_requise
def rendre(pret_id):
    v = Validateur(corps_json(optionnel=True))
    v.texte("remarque", nullable=True, longueur_max=1000)
    remarque = v.verifier().get("remarque")

    with db.ecriture() as donnees:
        pret = prets.rendre(donnees, g.utilisateur, pret_id, remarque)
        resultat = prets.representation(donnees, pret)
    return jsonify(resultat)
