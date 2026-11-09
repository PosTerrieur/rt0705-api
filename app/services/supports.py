"""Supports physiques et numériques d'un film (F07, RG3, RG7, RG11)"""
import config
from erreurs import ErreurApi, conflit
from services.commun import aujourdhui, nouvel_id, trouver
from validation import Validateur


def du_film(donnees, film_id):
    return [s for s in donnees["supports"] if s["filmId"] == film_id]


def a_un_pret_en_cours(donnees, support_id):
    return any(p["supportId"] == support_id and p["statut"] == "EN_COURS"
               for p in donnees["prets"])


def disponible(donnees, support):
    """Donnée calculée : physique, pas perdu, et aucun prêt en cours"""
    return (support["categorie"] == "PHYSIQUE"
            and support["etat"] != "PERDU"
            and not a_un_pret_en_cours(donnees, support["id"]))


def type_affiche(support):
    """Type à afficher : DVD, BLU_RAY, ou NUMERIQUE"""
    return support["type"] if support["categorie"] == "PHYSIQUE" else "NUMERIQUE"


def representation(donnees, support):
    return {**support, "disponible": disponible(donnees, support)}


def _valider(payload, categorie, partiel):
    v = Validateur(payload, partiel)
    v.date("dateAcquisition", nullable=True)
    v.texte("commentaire", nullable=True, longueur_max=1000)
    if categorie == "PHYSIQUE":
        v.choix("type", config.TYPES_PHYSIQUES, obligatoire=True)
        v.choix("etat", config.ETATS_SUPPORT)
        v.texte("emplacement", nullable=True, longueur_max=100)
    else:
        v.texte("format", obligatoire=True, longueur_max=20)
        v.texte("resolution", nullable=True, longueur_max=20)
        v.texte("chemin", obligatoire=True, longueur_max=500)
        v.nombre("tailleGo", nullable=True, mini=0)
    if partiel:
        v.non_modifiable("id", "filmId", "categorie")
    return v.verifier()


def creer(donnees, film_id, payload):
    trouver(donnees["films"], film_id, "Film")

    v = Validateur(payload)
    v.choix("categorie", config.CATEGORIES_SUPPORT, obligatoire=True)
    categorie = v.verifier()["categorie"]
    valeurs = _valider(payload, categorie, partiel=False)

    support = {
        "id": nouvel_id(),
        "filmId": film_id,
        "categorie": categorie,
        "dateAcquisition": valeurs.get("dateAcquisition") or aujourdhui(),
        "commentaire": valeurs.get("commentaire"),
    }
    if categorie == "PHYSIQUE":
        support.update(type=valeurs["type"], etat=valeurs.get("etat", "BON"),
                       emplacement=valeurs.get("emplacement"))
    else:
        support.update(format=valeurs["format"], resolution=valeurs.get("resolution"),
                       chemin=valeurs["chemin"], tailleGo=valeurs.get("tailleGo"))
    donnees["supports"].append(support)
    return support


def modifier(donnees, support_id, payload):
    support = trouver(donnees["supports"], support_id, "Support")
    support.update(_valider(payload, support["categorie"], partiel=True))
    return support


def supprimer(donnees, support_id):
    trouver(donnees["supports"], support_id, "Support")
    if a_un_pret_en_cours(donnees, support_id):
        raise conflit("PRET_EN_COURS", "Ce support est actuellement prêté")   # RG7
    # RG11 : l'historique de prêts du support disparaît avec lui
    donnees["prets"] = [p for p in donnees["prets"] if p["supportId"] != support_id]
    donnees["supports"] = [s for s in donnees["supports"] if s["id"] != support_id]


def verifier_empruntable(donnees, support):
    """RG3 et RG4 : lève l'erreur adaptée si le support ne peut pas être emprunté"""
    if support["categorie"] != "PHYSIQUE":
        raise ErreurApi(400, "SUPPORT_NON_EMPRUNTABLE",
                        "Un support numérique ne peut pas être emprunté")
    if support["etat"] == "PERDU":
        raise conflit("SUPPORT_INDISPONIBLE", "Ce support est déclaré perdu")
    if a_un_pret_en_cours(donnees, support["id"]):
        raise conflit("SUPPORT_INDISPONIBLE", "Ce support est déjà prêté")
