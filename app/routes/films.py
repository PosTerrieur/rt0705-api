"""Routes /api/films : catalogue, recherche et gestion des films (F04 à F09)"""
from flask import Blueprint, jsonify, url_for

import auth
import config
import db
from services import films
from services.commun import paginer, trouver
from validation import (corps_json, pagination, param_booleen, param_choix,
                        param_entier, param_texte)

bp = Blueprint("films", __name__)

TYPES_RECHERCHABLES = config.TYPES_PHYSIQUES + ("NUMERIQUE",)


@bp.get("/films")
def rechercher():
    criteres = {
        "q": param_texte("q"),
        "genre": param_texte("genre"),
        "annee": param_entier("annee"),
        "realisateur": param_texte("realisateur"),
        "acteur": param_texte("acteur"),
        "type": param_choix("type", TYPES_RECHERCHABLES),
        "disponible": param_booleen("disponible"),
    }
    tri = param_choix("tri", films.CHAMPS_TRI, defaut="titre")
    ordre = param_choix("ordre", ("asc", "desc"), defaut="asc")
    page, taille = pagination()

    with db.lecture() as donnees:
        resultats = films.rechercher(donnees, criteres, tri, ordre)
    return jsonify(paginer(resultats, page, taille))


@bp.post("/films")
@auth.admin_requis
def creer():
    payload = corps_json()
    with db.ecriture() as donnees:
        film = films.creer(donnees, payload)
        resultat = films.fiche(donnees, film)
    entetes = {"Location": url_for(".obtenir", film_id=film["id"])}
    return jsonify(resultat), 201, entetes


@bp.get("/films/<film_id>")
def obtenir(film_id):
    with db.lecture() as donnees:
        resultat = films.fiche(donnees, trouver(donnees["films"], film_id, "Film"))
    return jsonify(resultat)


@bp.patch("/films/<film_id>")
@auth.admin_requis
def modifier(film_id):
    payload = corps_json()
    with db.ecriture() as donnees:
        resultat = films.fiche(donnees, films.modifier(donnees, film_id, payload))
    return jsonify(resultat)


@bp.delete("/films/<film_id>")
@auth.admin_requis
def supprimer(film_id):
    with db.ecriture() as donnees:
        films.supprimer(donnees, film_id)
    return "", 204
