"""Client du service externe TMDb (bonus F15) : préremplissage d'une fiche film

Deux appels à TMDb :
1. /search/movie   : recherche par titre (et année), on garde le premier résultat
2. /movie/{id}     : détails + distribution (append_to_response=credits)

Uniquement la bibliothèque standard (urllib) : aucune dépendance ajoutée
"""
import json
import urllib.error
import urllib.parse
import urllib.request

import config
from erreurs import ErreurApi


def _indisponible(message):
    return ErreurApi(503, "SERVICE_EXTERNE_INDISPONIBLE", message)


def _get(chemin, **params):
    """GET sur TMDb, renvoie le JSON décodé ou lève une erreur 503"""
    if not config.TMDB_CLE:
        raise _indisponible("Import désactivé : aucune clé TMDb n'est configurée (TMDB_API_KEY)")

    entetes = {"Accept": "application/json"}
    if config.TMDB_CLE.startswith("eyJ"):       # « API Read Access Token » (JWT) : en-tête Bearer
        entetes["Authorization"] = f"Bearer {config.TMDB_CLE}"
    else:                                       # clé v3 : paramètre api_key
        params["api_key"] = config.TMDB_CLE

    url = f"{config.TMDB_URL}{chemin}?{urllib.parse.urlencode(params)}"
    requete = urllib.request.Request(url, headers=entetes)
    try:
        with urllib.request.urlopen(requete, timeout=config.TMDB_DELAI_SECONDES) as reponse:
            return json.load(reponse)
    except urllib.error.HTTPError as erreur:
        if erreur.code == 401:
            raise _indisponible("Clé TMDb refusée : vérifiez TMDB_API_KEY") from erreur
        raise _indisponible(f"TMDb a répondu avec une erreur {erreur.code}") from erreur
    except (OSError, ValueError) as erreur:     # réseau, délai dépassé, JSON invalide
        raise _indisponible("TMDb est injoignable pour le moment") from erreur


def rechercher(titre, annee=None):
    """Renvoie une proposition de film au format du payload POST /api/films"""
    params = {"query": titre, "language": config.TMDB_LANGUE, "include_adult": "false"}
    if annee:
        params["year"] = annee
    resultats = _get("/search/movie", **params).get("results", [])
    if not resultats:
        raise ErreurApi(404, "RESSOURCE_INTROUVABLE", f"Aucun film trouvé sur TMDb pour « {titre} »")

    details = _get(f"/movie/{resultats[0]['id']}",
                   language=config.TMDB_LANGUE, append_to_response="credits")
    return _vers_film(details)


def _vers_film(details):
    """Conversion du format TMDb vers notre modèle"""
    credits = details.get("credits", {})
    date_sortie = details.get("release_date") or ""
    acteurs = sorted(credits.get("cast", []), key=lambda p: p.get("order", 0))
    return {
        "titre": details.get("title") or details.get("original_title"),
        "titreOriginal": details.get("original_title"),
        "annee": int(date_sortie[:4]) if date_sortie[:4].isdigit() else None,
        "dureeMinutes": details.get("runtime") or None,
        "synopsis": details.get("overview") or None,      # vide si pas de traduction
        "genres": [g["name"] for g in details.get("genres", [])],
        "langueOriginale": details.get("original_language"),
        "afficheUrl": (f"{config.TMDB_IMAGES}{details['poster_path']}"
                       if details.get("poster_path") else None),
        "realisateurs": [p["name"] for p in credits.get("crew", []) if p.get("job") == "Director"],
        "acteurs": [p["name"] for p in acteurs[:config.NB_ACTEURS_IMPORTES]],
    }
