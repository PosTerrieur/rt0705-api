"""Films : recherche, fiche, création, modification, suppression (F04 à F09, RG1, RG2, RG7, RG11)"""
from datetime import date

from erreurs import conflit
from services import personnes, supports
from services.commun import aujourdhui, cle, nouvel_id, trouver
from validation import Validateur

CHAMPS_TRI = ("titre", "annee", "dateAjout", "note")

CHAMPS_SIMPLES = ("titre", "titreOriginal", "annee", "dureeMinutes", "synopsis",
                  "genres", "langueOriginale", "afficheUrl")


# --- Données calculées -------------------------------------------------------

def note(donnees, film_id):
    """Renvoie (moyenne arrondie à 0,1, nombre de notes)"""
    notes = [s["note"] for s in donnees["suivis"]
             if s["filmId"] == film_id and s["note"] is not None]
    if not notes:
        return None, 0
    return round(sum(notes) / len(notes), 1), len(notes)


def resume(donnees, film):
    """Version courte pour les listes (une carte du catalogue)"""
    supports_film = supports.du_film(donnees, film["id"])
    return {
        "id": film["id"],
        "titre": film["titre"],
        "annee": film["annee"],
        "genres": film["genres"],
        "realisateurs": [p["nom"] for p in personnes.du_film(donnees, film["id"], "REALISATEUR")],
        "afficheUrl": film["afficheUrl"],
        "noteMoyenne": note(donnees, film["id"])[0],
        "typesSupports": sorted({supports.type_affiche(s) for s in supports_film}),
        "disponible": any(supports.disponible(donnees, s) for s in supports_film),
    }


def fiche(donnees, film):
    """Fiche complète : le client obtient tout en un seul appel"""
    logins = {u["id"]: u["login"] for u in donnees["utilisateurs"]}
    moyenne, nombre = note(donnees, film["id"])
    avis = [
        {"login": logins.get(s["utilisateurId"], "?"), "note": s["note"],
         "commentaire": s["commentaire"], "dateMaj": s["dateMaj"]}
        for s in donnees["suivis"]
        if s["filmId"] == film["id"] and (s["note"] is not None or s["commentaire"])
    ]
    avis.sort(key=lambda a: a["dateMaj"], reverse=True)
    return {
        **film,
        "realisateurs": personnes.du_film(donnees, film["id"], "REALISATEUR"),
        "acteurs": personnes.du_film(donnees, film["id"], "ACTEUR"),
        "supports": [supports.representation(donnees, s)
                     for s in supports.du_film(donnees, film["id"])],
        "noteMoyenne": moyenne,
        "nombreNotes": nombre,
        "avis": avis,
    }


# --- Recherche ---------------------------------------------------------------

def _a_participant(donnees, film_id, role, texte):
    return any(cle(texte) in cle(p["nom"]) for p in personnes.du_film(donnees, film_id, role))


def _correspond(donnees, film, criteres):
    q = criteres.get("q")
    if q and cle(q) not in cle(film["titre"]) and cle(q) not in cle(film["titreOriginal"] or ""):
        return False
    genre = criteres.get("genre")
    if genre and cle(genre) not in [cle(g) for g in film["genres"]]:
        return False
    if criteres.get("annee") is not None and film["annee"] != criteres["annee"]:
        return False
    if criteres.get("realisateur") and not _a_participant(donnees, film["id"], "REALISATEUR", criteres["realisateur"]):
        return False
    if criteres.get("acteur") and not _a_participant(donnees, film["id"], "ACTEUR", criteres["acteur"]):
        return False

    supports_film = supports.du_film(donnees, film["id"])
    type_support = criteres.get("type")
    if type_support and type_support not in [supports.type_affiche(s) for s in supports_film]:
        return False
    if criteres.get("disponible") is not None:
        est_disponible = any(supports.disponible(donnees, s) for s in supports_film)
        if est_disponible != criteres["disponible"]:
            return False
    return True


def rechercher(donnees, criteres, tri="titre", ordre="asc"):
    """Renvoie les résumés des films correspondant aux critères, triés"""
    films = [f for f in donnees["films"] if _correspond(donnees, f, criteres)]
    decroissant = ordre == "desc"

    if tri == "titre":
        films.sort(key=lambda f: cle(f["titre"]), reverse=decroissant)
    elif tri == "note":
        # Les films sans note restent en fin de liste, quel que soit l'ordre
        notes = {f["id"]: note(donnees, f["id"])[0] for f in films}
        avec_note = sorted((f for f in films if notes[f["id"]] is not None),
                           key=lambda f: notes[f["id"]], reverse=decroissant)
        films = avec_note + [f for f in films if notes[f["id"]] is None]
    else:   # annee ou dateAjout
        films.sort(key=lambda f: f[tri], reverse=decroissant)

    return [resume(donnees, f) for f in films]


# --- Création, modification, suppression ------------------------------------

def _valider(payload, partiel):
    v = Validateur(payload, partiel)
    v.texte("titre", obligatoire=True, longueur_max=200)
    v.texte("titreOriginal", nullable=True, longueur_max=200)
    v.entier("annee", obligatoire=True, mini=1888, maxi=date.today().year + 5)
    v.entier("dureeMinutes", obligatoire=True, mini=1, maxi=1500)
    v.texte("synopsis", nullable=True, longueur_max=5000)
    v.liste_textes("genres")
    v.texte("langueOriginale", nullable=True, longueur_max=10)
    v.texte("afficheUrl", nullable=True, longueur_max=500)
    v.liste_textes("realisateurs")
    v.liste_textes("acteurs")
    if partiel:
        v.non_modifiable("id", "dateAjout")
    return v.verifier()


def _verifier_unicite(donnees, titre, annee, sauf_id=None):
    """RG1 : le couple (titre, année) est unique, casse et espaces ignorés"""
    for film in donnees["films"]:
        if film["id"] != sauf_id and cle(film["titre"]) == cle(titre) and film["annee"] == annee:
            raise conflit("FILM_EXISTANT", "Ce film existe déjà.", {"filmId": film["id"]})


def _mettre_a_jour_participations(donnees, film_id, valeurs):
    if "realisateurs" in valeurs:
        personnes.remplacer_participations(donnees, film_id, "REALISATEUR", valeurs["realisateurs"])
    if "acteurs" in valeurs:
        personnes.remplacer_participations(donnees, film_id, "ACTEUR", valeurs["acteurs"])


def creer(donnees, payload):
    valeurs = _valider(payload, partiel=False)
    _verifier_unicite(donnees, valeurs["titre"], valeurs["annee"])

    film = {"id": nouvel_id()}
    for champ in CHAMPS_SIMPLES:
        film[champ] = valeurs.get(champ, [] if champ == "genres" else None)
    film["dateAjout"] = aujourdhui()

    donnees["films"].append(film)
    _mettre_a_jour_participations(donnees, film["id"], valeurs)
    return film


def modifier(donnees, film_id, payload):
    film = trouver(donnees["films"], film_id, "Film")
    valeurs = _valider(payload, partiel=True)
    _verifier_unicite(donnees, valeurs.get("titre", film["titre"]),
                      valeurs.get("annee", film["annee"]), sauf_id=film_id)

    for champ in CHAMPS_SIMPLES:
        if champ in valeurs:
            film[champ] = valeurs[champ]
    _mettre_a_jour_participations(donnees, film_id, valeurs)
    return film


def supprimer(donnees, film_id):
    trouver(donnees["films"], film_id, "Film")
    ids_supports = {s["id"] for s in supports.du_film(donnees, film_id)}

    # RG7 : aucun support du film ne doit être en prêt
    if any(supports.a_un_pret_en_cours(donnees, sid) for sid in ids_supports):
        raise conflit("PRET_EN_COURS", "Un support de ce film est actuellement prêté")

    # RG11 : suppression en cascade, les personnes sont conservées
    donnees["prets"] = [p for p in donnees["prets"] if p["supportId"] not in ids_supports]
    donnees["supports"] = [s for s in donnees["supports"] if s["filmId"] != film_id]
    donnees["participations"] = [pa for pa in donnees["participations"] if pa["filmId"] != film_id]
    donnees["suivis"] = [s for s in donnees["suivis"] if s["filmId"] != film_id]
    donnees["films"] = [f for f in donnees["films"] if f["id"] != film_id]
