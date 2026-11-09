"""Routes /api/utilisateurs : profil (F02) et gestion des comptes (F03)"""
from flask import Blueprint, g, jsonify, url_for

import auth
import db
from services import utilisateurs
from services.commun import trouver
from validation import corps_json, param_booleen

bp = Blueprint("utilisateurs", __name__)


# --- Profil de l'utilisateur connecté ------------------------------------------

@bp.get("/utilisateurs/me")
@auth.connexion_requise
def moi():
    return jsonify(g.utilisateur)


@bp.patch("/utilisateurs/me")
@auth.connexion_requise
def modifier_moi():
    payload = corps_json()
    with db.ecriture() as donnees:
        utilisateur = utilisateurs.modifier_profil(donnees, g.utilisateur["id"], payload)
        resultat = utilisateurs.public(utilisateur)
    return jsonify(resultat)


# --- Gestion des comptes (administrateur) --------------------------------------

@bp.get("/utilisateurs")
@auth.admin_requis
def lister():
    actif = param_booleen("actif")
    with db.lecture() as donnees:
        resultat = utilisateurs.lister(donnees, actif)
    return jsonify(resultat)


@bp.post("/utilisateurs")
@auth.admin_requis
def creer():
    payload = corps_json()
    with db.ecriture() as donnees:
        resultat = utilisateurs.public(utilisateurs.creer(donnees, payload))
    entetes = {"Location": url_for(".obtenir", utilisateur_id=resultat["id"])}
    return jsonify(resultat), 201, entetes


@bp.get("/utilisateurs/<utilisateur_id>")
@auth.admin_requis
def obtenir(utilisateur_id):
    with db.lecture() as donnees:
        resultat = utilisateurs.public(trouver(donnees["utilisateurs"], utilisateur_id, "Utilisateur"))
    return jsonify(resultat)


@bp.patch("/utilisateurs/<utilisateur_id>")
@auth.admin_requis
def modifier(utilisateur_id):
    payload = corps_json()
    with db.ecriture() as donnees:
        resultat = utilisateurs.public(utilisateurs.modifier(donnees, utilisateur_id, payload))
    if not resultat["actif"]:
        auth.fermer_sessions_utilisateur(utilisateur_id)   # RG10 : révocation immédiate
    return jsonify(resultat)
