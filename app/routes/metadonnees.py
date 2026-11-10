"""Route /api/metadonnees : proposition de fiche depuis TMDb (bonus F15)"""
from flask import Blueprint, jsonify

import auth
import metadonnees
from erreurs import ErreurApi
from validation import param_entier, param_texte

bp = Blueprint("metadonnees", __name__)


@bp.get("/metadonnees")
@auth.admin_requis
def importer():
    titre = param_texte("titre")
    if not titre:
        raise ErreurApi(400, "VALIDATION", "Paramètre « titre » obligatoire",
                        {"titre": "champ obligatoire"})
    annee = param_entier("annee", mini=1888, maxi=2100)
    # GET : l'opération ne modifie rien, elle renvoie une proposition non enregistrée
    return jsonify(metadonnees.rechercher(titre, annee))
