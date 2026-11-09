"""Suivi personnel d'un film : vu, note, commentaire (F14, RG8)"""
from erreurs import ErreurApi
from services.commun import aujourdhui, trouver
from validation import Validateur


def _chercher(donnees, utilisateur_id, film_id):
    for suivi in donnees["suivis"]:
        if suivi["utilisateurId"] == utilisateur_id and suivi["filmId"] == film_id:
            return suivi
    return None


def de_l_utilisateur(donnees, utilisateur_id):
    suivis = [s for s in donnees["suivis"] if s["utilisateurId"] == utilisateur_id]
    return sorted(suivis, key=lambda s: s["dateMaj"], reverse=True)


def obtenir(donnees, utilisateur_id, film_id):
    trouver(donnees["films"], film_id, "Film")
    suivi = _chercher(donnees, utilisateur_id, film_id)
    if suivi is None:
        raise ErreurApi(404, "RESSOURCE_INTROUVABLE", "Aucun suivi pour ce film")
    return suivi


def enregistrer(donnees, utilisateur_id, film_id, payload):
    """PUT : crée ou remplace le suivi + renvoie (suivi, cree)"""
    trouver(donnees["films"], film_id, "Film")
    v = Validateur(payload)
    v.booleen("vu", obligatoire=True)
    v.entier("note", nullable=True, mini=0, maxi=5)
    v.texte("commentaire", nullable=True, longueur_max=2000)
    valeurs = v.verifier()

    contenu = {
        "vu": valeurs["vu"],
        "note": valeurs.get("note"),
        "commentaire": valeurs.get("commentaire"),
        "dateMaj": aujourdhui(),
    }
    suivi = _chercher(donnees, utilisateur_id, film_id)   # RG8 : un seul suivi par film
    if suivi is not None:
        suivi.update(contenu)
        return suivi, False

    suivi = {"utilisateurId": utilisateur_id, "filmId": film_id, **contenu}
    donnees["suivis"].append(suivi)
    return suivi, True
