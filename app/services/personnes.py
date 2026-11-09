"""Personnes (acteurs, réalisateurs) et participations aux films (RG12, RG13, F16, F17)"""
from erreurs import conflit
from services.commun import cle, nouvel_id, normaliser, trouver
from validation import Validateur


def par_nom(donnees, nom):
    for personne in donnees["personnes"]:
        if cle(personne["nom"]) == cle(nom):
            return personne
    return None


def trouver_ou_creer(donnees, nom):
    """RG12 : un nom déjà connu est rattaché à la personne existante"""
    personne = par_nom(donnees, nom)
    if personne is None:
        personne = {"id": nouvel_id(), "nom": normaliser(nom)}
        donnees["personnes"].append(personne)
    return personne


def du_film(donnees, film_id, role):
    """Personnes ayant ce rôle dans le film, dans l'ordre de saisie : [{"id", "nom"}]"""
    personnes = {p["id"]: p for p in donnees["personnes"]}
    return [{"id": pa["personneId"], "nom": personnes[pa["personneId"]]["nom"]}
            for pa in donnees["participations"]
            if pa["filmId"] == film_id and pa["role"] == role]


def remplacer_participations(donnees, film_id, role, noms):
    """Remplace toutes les participations d'un rôle pour un film"""
    donnees["participations"] = [
        pa for pa in donnees["participations"]
        if not (pa["filmId"] == film_id and pa["role"] == role)
    ]
    for nom in noms:
        personne = trouver_ou_creer(donnees, nom)
        donnees["participations"].append(
            {"filmId": film_id, "personneId": personne["id"], "role": role})


def rechercher(donnees, texte=None):
    personnes = [p for p in donnees["personnes"] if not texte or cle(texte) in cle(p["nom"])]
    return sorted(personnes, key=lambda p: cle(p["nom"]))


def fiche(donnees, personne):
    """Personne + filmographie classée par rôle puis par année (F16)"""
    films = {f["id"]: f for f in donnees["films"]}
    filmographie = {"REALISATEUR": [], "ACTEUR": []}
    for pa in donnees["participations"]:
        if pa["personneId"] == personne["id"]:
            film = films[pa["filmId"]]
            filmographie[pa["role"]].append(
                {"id": film["id"], "titre": film["titre"], "annee": film["annee"]})
    for liste in filmographie.values():
        liste.sort(key=lambda f: f["annee"])
    return {"id": personne["id"], "nom": personne["nom"], "filmographie": filmographie}


def renommer(donnees, personne_id, payload):
    """F17 : la correction s'applique à tous les films de la personne"""
    personne = trouver(donnees["personnes"], personne_id, "Personne")
    v = Validateur(payload)
    v.texte("nom", obligatoire=True, longueur_max=200)
    nom = normaliser(v.verifier()["nom"])

    homonyme = par_nom(donnees, nom)
    if homonyme is not None and homonyme["id"] != personne_id:
        raise conflit("NOM_DEJA_PRIS", "Une autre personne porte déjà ce nom.",
                      {"personneId": homonyme["id"]})
    personne["nom"] = nom
    return personne
