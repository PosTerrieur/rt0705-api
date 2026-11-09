"""Routes /api/sessions : connexion et déconnexion (F01)"""
from flask import Blueprint, g, jsonify

import auth
from validation import Validateur, corps_json

bp = Blueprint("sessions", __name__)


@bp.post("/sessions")
def creer():
    v = Validateur(corps_json())
    v.texte("login", obligatoire=True, longueur_max=100)
    v.texte("motDePasse", obligatoire=True, longueur_max=200, nettoyer=False)
    valeurs = v.verifier()
    return jsonify(auth.ouvrir_session(valeurs["login"], valeurs["motDePasse"])), 201


@bp.delete("/sessions/current")
@auth.connexion_requise
def supprimer():
    auth.fermer_session(g.jeton)
    return "", 204
