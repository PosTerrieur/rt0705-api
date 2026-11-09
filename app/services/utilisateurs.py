"""Comptes utilisateurs : création, modification, profil (F02, F03, RG10)"""
from werkzeug.security import check_password_hash, generate_password_hash

import config
from erreurs import ErreurApi, conflit
from services.commun import aujourdhui, cle, nouvel_id, trouver
from validation import Validateur

MOTIF_LOGIN = r"[A-Za-z0-9._-]+"
MOTIF_EMAIL = r"[^@\s]+@[^@\s]+\.[^@\s]+"
LONGUEUR_MIN_MOT_DE_PASSE = 8


def public(utilisateur):
    """Représentation renvoyée au client : jamais le hachage du mot de passe"""
    return {cle_champ: valeur for cle_champ, valeur in utilisateur.items()
            if cle_champ != "motDePasseHash"}


def par_login(donnees, login):
    for utilisateur in donnees["utilisateurs"]:
        if cle(utilisateur["login"]) == cle(login):
            return utilisateur
    return None


def mot_de_passe_valide(utilisateur, mot_de_passe):
    return check_password_hash(utilisateur["motDePasseHash"], mot_de_passe)


def admins_actifs(donnees):
    return [u for u in donnees["utilisateurs"] if u["role"] == "ADMIN" and u["actif"]]


def lister(donnees, actif=None):
    utilisateurs = [u for u in donnees["utilisateurs"] if actif is None or u["actif"] == actif]
    return [public(u) for u in sorted(utilisateurs, key=lambda u: cle(u["login"]))]


def creer(donnees, payload):
    v = Validateur(payload)
    v.texte("login", obligatoire=True, longueur_min=3, longueur_max=30, motif=MOTIF_LOGIN)
    v.texte("email", obligatoire=True, longueur_max=200, motif=MOTIF_EMAIL)
    v.texte("motDePasse", obligatoire=True, longueur_min=LONGUEUR_MIN_MOT_DE_PASSE,
            longueur_max=200, nettoyer=False)
    v.choix("role", config.ROLES_UTILISATEUR)
    valeurs = v.verifier()

    _verifier_unicite(donnees, login=valeurs["login"], email=valeurs["email"])
    utilisateur = {
        "id": nouvel_id(),
        "login": valeurs["login"],
        "email": valeurs["email"],
        "motDePasseHash": generate_password_hash(valeurs["motDePasse"]),
        "role": valeurs.get("role", "MEMBRE"),
        "actif": True,
        "dateInscription": aujourdhui(),
    }
    donnees["utilisateurs"].append(utilisateur)
    return utilisateur


def modifier(donnees, utilisateur_id, payload):
    """Modification d'un compte par un administrateur"""
    utilisateur = trouver(donnees["utilisateurs"], utilisateur_id, "Utilisateur")
    v = Validateur(payload, partiel=True)
    v.texte("email", longueur_max=200, motif=MOTIF_EMAIL)
    v.choix("role", config.ROLES_UTILISATEUR)
    v.booleen("actif")
    v.texte("motDePasse", longueur_min=LONGUEUR_MIN_MOT_DE_PASSE, longueur_max=200, nettoyer=False)
    v.non_modifiable("login", "id")
    valeurs = v.verifier()

    if "email" in valeurs:
        _verifier_unicite(donnees, email=valeurs["email"], sauf_id=utilisateur_id)

    # On ne retire pas ses droits au dernier administrateur actif
    perd_ses_droits = valeurs.get("role") == "MEMBRE" or valeurs.get("actif") is False
    if perd_ses_droits and admins_actifs(donnees) == [utilisateur]:
        raise conflit("DERNIER_ADMIN", "Impossible : c'est le dernier administrateur actif")

    for champ in ("email", "role", "actif"):
        if champ in valeurs:
            utilisateur[champ] = valeurs[champ]
    if "motDePasse" in valeurs:
        utilisateur["motDePasseHash"] = generate_password_hash(valeurs["motDePasse"])
    return utilisateur


def modifier_profil(donnees, utilisateur_id, payload):
    """Modification de son propre compte : email et mot de passe uniquement"""
    utilisateur = trouver(donnees["utilisateurs"], utilisateur_id, "Utilisateur")
    # Seul le mot de passe actuel est obligatoire, les autres champs sont facultatifs
    v = Validateur(payload)
    v.texte("motDePasseActuel", obligatoire=True, longueur_max=200, nettoyer=False)
    v.texte("email", longueur_max=200, motif=MOTIF_EMAIL)
    v.texte("nouveauMotDePasse", longueur_min=LONGUEUR_MIN_MOT_DE_PASSE,
            longueur_max=200, nettoyer=False)
    v.non_modifiable("login", "role", "actif", "id")
    valeurs = v.verifier()

    if not mot_de_passe_valide(utilisateur, valeurs["motDePasseActuel"]):
        raise ErreurApi(403, "MOT_DE_PASSE_INCORRECT", "Le mot de passe actuel est incorrect")
    if "email" in valeurs:
        _verifier_unicite(donnees, email=valeurs["email"], sauf_id=utilisateur_id)
        utilisateur["email"] = valeurs["email"]
    if "nouveauMotDePasse" in valeurs:
        utilisateur["motDePasseHash"] = generate_password_hash(valeurs["nouveauMotDePasse"])
    return utilisateur


def creer_ou_reinitialiser_admin(donnees, mot_de_passe):
    """Compte « admin » initial : créé s'il n'existe pas, réinitialisé sinon"""
    admin = par_login(donnees, config.ADMIN_LOGIN)
    if admin is None:
        admin = {
            "id": nouvel_id(),
            "login": config.ADMIN_LOGIN,
            "email": "admin@videotheque.local",
            "motDePasseHash": "",
            "role": "ADMIN",
            "actif": True,
            "dateInscription": aujourdhui(),
        }
        donnees["utilisateurs"].append(admin)
    admin.update(role="ADMIN", actif=True, motDePasseHash=generate_password_hash(mot_de_passe))
    return admin


def _verifier_unicite(donnees, login=None, email=None, sauf_id=None):
    for utilisateur in donnees["utilisateurs"]:
        if utilisateur["id"] == sauf_id:
            continue
        if (login and cle(utilisateur["login"]) == cle(login)) or \
           (email and cle(utilisateur["email"]) == cle(email)):
            raise conflit("LOGIN_OU_EMAIL_PRIS", "Ce login ou cet email est déjà utilisé")
