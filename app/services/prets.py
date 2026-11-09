"""Prêts en libre-service supervisé (F10 à F13, RG3 à RG6, RG9)"""
from datetime import date, timedelta

import config
from erreurs import acces_interdit, conflit
from services import supports
from services.commun import aujourdhui, nouvel_id, trouver


def en_retard(pret):
    """Donnée calculée : prêt en cours dont la date de retour prévue est dépassée"""
    return (pret["statut"] == "EN_COURS"
            and date.today() > date.fromisoformat(pret["dateRetourPrevue"]))


def representation(donnees, pret):
    """Prêt enrichi : retard calculé, résumé du support, du film et de l'emprunteur"""
    support = trouver(donnees["supports"], pret["supportId"], "Support")
    film = trouver(donnees["films"], support["filmId"], "Film")
    emprunteur = trouver(donnees["utilisateurs"], pret["utilisateurId"], "Utilisateur")
    return {
        **pret,
        "enRetard": en_retard(pret),
        "support": {"id": support["id"], "type": support["type"],
                    "emplacement": support["emplacement"]},
        "film": {"id": film["id"], "titre": film["titre"], "annee": film["annee"]},
        "emprunteur": {"id": emprunteur["id"], "login": emprunteur["login"]},
    }


def _verifier_acces(utilisateur, pret):
    """RG9 : seul l'emprunteur ou un administrateur peut voir ou rendre un prêt"""
    if utilisateur["role"] != "ADMIN" and pret["utilisateurId"] != utilisateur["id"]:
        raise acces_interdit("Ce prêt appartient à un autre membre")


def obtenir(donnees, utilisateur, pret_id):
    pret = trouver(donnees["prets"], pret_id, "Prêt")
    _verifier_acces(utilisateur, pret)
    return pret


def lister(donnees, utilisateur, statut=None, en_retard_seulement=None, utilisateur_id=None):
    if utilisateur["role"] != "ADMIN":
        if utilisateur_id and utilisateur_id != utilisateur["id"]:
            raise acces_interdit("Un membre ne peut consulter que ses propres prêts")
        utilisateur_id = utilisateur["id"]

    prets = [
        p for p in donnees["prets"]
        if (utilisateur_id is None or p["utilisateurId"] == utilisateur_id)
        and (statut is None or p["statut"] == statut)
        and (en_retard_seulement is None or en_retard(p) == en_retard_seulement)
    ]
    return sorted(prets, key=lambda p: p["dateDebut"], reverse=True)


def emprunter(donnees, utilisateur, support_id):
    support = trouver(donnees["supports"], support_id, "Support")
    supports.verifier_empruntable(donnees, support)          # RG3, RG4

    en_cours = [p for p in donnees["prets"]
                if p["utilisateurId"] == utilisateur["id"] and p["statut"] == "EN_COURS"]
    if len(en_cours) >= config.QUOTA_PRETS:                   # RG5
        raise conflit("QUOTA_ATTEINT",
                      f"Vous avez déjà {len(en_cours)} prêts en cours : rendez un support "
                      "avant d'en emprunter un autre",
                      {"quota": config.QUOTA_PRETS, "pretsEnCours": len(en_cours)})

    debut = date.today()
    pret = {
        "id": nouvel_id(),
        "supportId": support_id,
        "utilisateurId": utilisateur["id"],
        "dateDebut": debut.isoformat(),
        "dateRetourPrevue": (debut + timedelta(days=config.DUREE_PRET_JOURS)).isoformat(),  # RG6
        "dateRetourEffective": None,
        "statut": "EN_COURS",
        "retourEnregistrePar": None,
        "remarqueRetour": None,
    }
    donnees["prets"].append(pret)
    return pret


def rendre(donnees, utilisateur, pret_id, remarque=None):
    pret = trouver(donnees["prets"], pret_id, "Prêt")
    # L'appartenance est vérifiée AVANT l'état : on ne révèle rien des prêts d'autrui
    _verifier_acces(utilisateur, pret)
    if pret["statut"] == "RENDU":
        raise conflit("PRET_DEJA_RENDU", "Ce prêt est déjà clôturé.")

    pret.update(
        dateRetourEffective=aujourdhui(),
        statut="RENDU",
        retourEnregistrePar=utilisateur["id"],
        remarqueRetour=remarque,
    )
    return pret
