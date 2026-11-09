"""Fonctions partagées par les services"""
import uuid
from datetime import date, datetime, timezone

from erreurs import introuvable


def nouvel_id():
    return str(uuid.uuid4())


def aujourdhui():
    return date.today().isoformat()


def horodatage(moment=None):
    """Date et heure UTC au format ISO 8601 : 2026-11-06T09:12:44Z"""
    moment = moment or datetime.now(timezone.utc)
    return moment.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normaliser(texte):
    """Supprime les espaces superflus"""
    return " ".join(texte.split())


def cle(texte):
    """Clé de comparaison insensible à la casse et aux espaces superflus"""
    return normaliser(texte).casefold()


def trouver(collection, identifiant, nom_objet):
    """Renvoie l'objet de la collection ayant cet id, ou lève une erreur 404"""
    for objet in collection:
        if objet["id"] == identifiant:
            return objet
    raise introuvable(nom_objet)


def paginer(elements, page, taille):
    debut = (page - 1) * taille
    return {
        "elements": elements[debut:debut + taille],
        "pagination": {"page": page, "taille": taille, "total": len(elements)},
    }
