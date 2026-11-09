"""Authentification : sessions à jeton opaque stockées dans sessions.json

Le client envoie son jeton dans l'en-tête :  Authorization: Bearer <jeton>
"""
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import g, request

import config
import db
from erreurs import ErreurApi, acces_interdit
from services import utilisateurs
from services.commun import horodatage


def _non_authentifie(message="Authentification requise"):
    return ErreurApi(401, "NON_AUTHENTIFIE", message)


def _expiree(session):
    return datetime.fromisoformat(session["expiration"]) <= datetime.now(timezone.utc)


# --- Ouverture et fermeture de session ---------------------------------------

def ouvrir_session(login, mot_de_passe):
    """Vérifie les identifiants, crée une session et renvoie jeton + profil"""
    with db.lecture() as donnees:
        utilisateur = utilisateurs.par_login(donnees, login)
        valide = (utilisateur is not None and utilisateur["actif"]
                  and utilisateurs.mot_de_passe_valide(utilisateur, mot_de_passe))
        if not valide:
            # Même réponse pour un login inconnu, un mauvais mot de passe ou un
            # compte désactivé (RG10) : on ne révèle pas l'existence d'un compte
            raise ErreurApi(401, "IDENTIFIANTS_INCORRECTS", "Identifiant ou mot de passe incorrect")
        profil = utilisateurs.public(utilisateur)

    debut = datetime.now(timezone.utc)
    session = {
        "jeton": secrets.token_urlsafe(32),
        "utilisateurId": profil["id"],
        "creation": horodatage(debut),
        "expiration": horodatage(debut + timedelta(hours=config.SESSION_DUREE_HEURES)),
    }
    with db.ecriture("sessions") as donnees_sessions:
        # On profite de l'écriture pour purger les sessions expirées
        donnees_sessions["sessions"] = [s for s in donnees_sessions["sessions"] if not _expiree(s)]
        donnees_sessions["sessions"].append(session)

    return {"jeton": session["jeton"], "expiration": session["expiration"], "utilisateur": profil}


def fermer_session(jeton):
    with db.ecriture("sessions") as donnees_sessions:
        donnees_sessions["sessions"] = [s for s in donnees_sessions["sessions"] if s["jeton"] != jeton]


def fermer_sessions_utilisateur(utilisateur_id):
    """Révoque tous les jetons d'un utilisateur (ex. : compte désactivé)"""
    with db.ecriture("sessions") as donnees_sessions:
        donnees_sessions["sessions"] = [s for s in donnees_sessions["sessions"]
                                        if s["utilisateurId"] != utilisateur_id]


# --- Identification de l'appelant ----------------------------------------------

def _jeton_de_la_requete():
    entete = request.headers.get("Authorization", "")
    prefixe = "Bearer "
    if not entete.startswith(prefixe) or not entete[len(prefixe):].strip():
        raise _non_authentifie()
    return entete[len(prefixe):].strip()


def _utilisateur_courant():
    """Renvoie (profil public, jeton) de l'appelant, ou lève une erreur 401"""
    jeton = _jeton_de_la_requete()

    with db.lecture("sessions") as donnees_sessions:
        session = next((s for s in donnees_sessions["sessions"]
                        if secrets.compare_digest(s["jeton"], jeton)), None)
    if session is None or _expiree(session):
        raise _non_authentifie("Session invalide ou expirée")

    with db.lecture() as donnees:
        utilisateur = next((u for u in donnees["utilisateurs"]
                            if u["id"] == session["utilisateurId"]), None)
    if utilisateur is None or not utilisateur["actif"]:
        raise _non_authentifie("Session invalide ou expirée")

    return utilisateurs.public(utilisateur), jeton


# --- Décorateurs de routes -----------------------------------------------------

def connexion_requise(route):
    """La route exige un jeton valide : l'appelant est disponible dans g.utilisateur"""
    @wraps(route)
    def route_protegee(*args, **kwargs):
        g.utilisateur, g.jeton = _utilisateur_courant()
        return route(*args, **kwargs)
    return route_protegee


def admin_requis(route):
    """La route est réservée aux administrateurs"""
    @wraps(route)
    def route_protegee(*args, **kwargs):
        g.utilisateur, g.jeton = _utilisateur_courant()
        if g.utilisateur["role"] != "ADMIN":
            raise acces_interdit("Opération réservée aux administrateurs")
        return route(*args, **kwargs)
    return route_protegee


def est_admin():
    return g.utilisateur["role"] == "ADMIN"
