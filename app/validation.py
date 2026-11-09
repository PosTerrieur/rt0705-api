"""Validation des données reçues : corps JSON et paramètres d'URL"""
import re
from datetime import date

from flask import request

import config
from erreurs import ErreurApi


def corps_json(optionnel=False):
    """Renvoie le corps de la requête, qui doit être un objet JSON

    Avec optionnel=True, un corps vide est accepté et vaut {}
    """
    if optionnel and not request.get_data():
        return {}
    donnees = request.get_json(silent=True)
    if not isinstance(donnees, dict):
        raise ErreurApi(400, "VALIDATION", "Le corps de la requête doit être un objet JSON")
    return donnees


class Validateur:
    """Vérifie les champs d'un objet JSON en accumulant les erreurs

    - self.valeurs contient les champs présents et valides (nettoyés)
    - en mode partiel (PATCH), un champ absent est simplement ignoré
    - les champs non prévus sont ignorés : le client ne peut pas imposer un id, une date
    """

    def __init__(self, donnees, partiel=False):
        self.donnees = donnees
        self.partiel = partiel
        self.erreurs = {}
        self.valeurs = {}

    def _lire(self, champ, obligatoire, nullable):
        """Renvoie (à_valider, valeur) en traitant les cas « absent » et « null »"""
        if champ not in self.donnees:
            if obligatoire and not self.partiel:
                self.erreurs[champ] = "champ obligatoire"
            return False, None
        valeur = self.donnees[champ]
        if valeur is None:
            if nullable:
                self.valeurs[champ] = None
            else:
                self.erreurs[champ] = "ne peut pas être null"
            return False, None
        return True, valeur

    def texte(self, champ, obligatoire=False, nullable=False, longueur_min=1,
              longueur_max=500, motif=None, nettoyer=True):
        a_valider, valeur = self._lire(champ, obligatoire, nullable)
        if not a_valider:
            return
        if not isinstance(valeur, str):
            self.erreurs[champ] = "doit être une chaîne de caractères"
            return
        if nettoyer:
            valeur = valeur.strip()
        if len(valeur) < longueur_min:
            self.erreurs[champ] = ("ne peut pas être vide" if longueur_min == 1
                                   else f"doit contenir au moins {longueur_min} caractères")
        elif len(valeur) > longueur_max:
            self.erreurs[champ] = f"ne doit pas dépasser {longueur_max} caractères"
        elif motif and not re.fullmatch(motif, valeur):
            self.erreurs[champ] = "format invalide"
        else:
            self.valeurs[champ] = valeur

    def entier(self, champ, obligatoire=False, nullable=False, mini=None, maxi=None):
        a_valider, valeur = self._lire(champ, obligatoire, nullable)
        if not a_valider:
            return
        # En Python, True est un int : on l'exclut explicitement
        if not isinstance(valeur, int) or isinstance(valeur, bool):
            self.erreurs[champ] = "doit être un entier"
        elif mini is not None and valeur < mini:
            self.erreurs[champ] = f"doit être supérieur ou égal à {mini}"
        elif maxi is not None and valeur > maxi:
            self.erreurs[champ] = f"doit être inférieur ou égal à {maxi}"
        else:
            self.valeurs[champ] = valeur

    def nombre(self, champ, obligatoire=False, nullable=False, mini=None):
        a_valider, valeur = self._lire(champ, obligatoire, nullable)
        if not a_valider:
            return
        if not isinstance(valeur, (int, float)) or isinstance(valeur, bool):
            self.erreurs[champ] = "doit être un nombre"
        elif mini is not None and valeur < mini:
            self.erreurs[champ] = f"doit être supérieur ou égal à {mini}"
        else:
            self.valeurs[champ] = float(valeur)

    def booleen(self, champ, obligatoire=False):
        a_valider, valeur = self._lire(champ, obligatoire, nullable=False)
        if not a_valider:
            return
        if not isinstance(valeur, bool):
            self.erreurs[champ] = "doit valoir true ou false"
        else:
            self.valeurs[champ] = valeur

    def choix(self, champ, valeurs_possibles, obligatoire=False):
        a_valider, valeur = self._lire(champ, obligatoire, nullable=False)
        if not a_valider:
            return
        if valeur not in valeurs_possibles:
            self.erreurs[champ] = f"valeur attendue parmi : {', '.join(valeurs_possibles)}"
        else:
            self.valeurs[champ] = valeur

    def date(self, champ, obligatoire=False, nullable=False):
        a_valider, valeur = self._lire(champ, obligatoire, nullable)
        if not a_valider:
            return
        try:
            self.valeurs[champ] = date.fromisoformat(valeur).isoformat()
        except (TypeError, ValueError):
            self.erreurs[champ] = "date attendue au format AAAA-MM-JJ"

    def liste_textes(self, champ, obligatoire=False):
        """Liste de textes : espaces superflus retirés, doublons (casse ignorée) supprimés"""
        a_valider, valeur = self._lire(champ, obligatoire, nullable=False)
        if not a_valider:
            return
        if not isinstance(valeur, list) or not all(isinstance(e, str) and e.strip() for e in valeur):
            self.erreurs[champ] = "doit être une liste de textes non vides"
            return
        resultat, deja_vus = [], set()
        for element in valeur:
            propre = " ".join(element.split())
            if propre.casefold() not in deja_vus:
                deja_vus.add(propre.casefold())
                resultat.append(propre)
        self.valeurs[champ] = resultat

    def non_modifiable(self, *champs):
        for champ in champs:
            if champ in self.donnees:
                self.erreurs[champ] = "non modifiable"

    def verifier(self):
        if self.erreurs:
            raise ErreurApi(400, "VALIDATION", "Données invalides.", self.erreurs)
        return self.valeurs


# --- Paramètres d'URL (?cle=valeur) -------------------------------------------

def _parametre_invalide(nom, message):
    return ErreurApi(400, "VALIDATION", f"Paramètre « {nom} » invalide", {nom: message})


def param_texte(nom):
    valeur = request.args.get(nom, "").strip()
    return valeur or None


def param_entier(nom, defaut=None, mini=None, maxi=None):
    brut = request.args.get(nom, "").strip()
    if not brut:
        return defaut
    try:
        valeur = int(brut)
    except ValueError:
        raise _parametre_invalide(nom, "doit être un entier") from None
    if (mini is not None and valeur < mini) or (maxi is not None and valeur > maxi):
        raise _parametre_invalide(nom, f"doit être compris entre {mini} et {maxi}")
    return valeur


def param_booleen(nom):
    brut = request.args.get(nom, "").strip().lower()
    if not brut:
        return None
    if brut in ("true", "1"):
        return True
    if brut in ("false", "0"):
        return False
    raise _parametre_invalide(nom, "doit valoir true ou false")


def param_choix(nom, valeurs_possibles, defaut=None):
    brut = request.args.get(nom, "").strip()
    if not brut:
        return defaut
    if brut not in valeurs_possibles:
        raise _parametre_invalide(nom, f"valeur attendue parmi : {', '.join(valeurs_possibles)}")
    return brut


def pagination():
    """Lit ?page= et ?taille= et renvoie (page, taille)"""
    page = param_entier("page", defaut=1, mini=1)
    taille = param_entier("taille", defaut=config.TAILLE_PAGE_DEFAUT,
                          mini=1, maxi=config.TAILLE_PAGE_MAX)
    return page, taille
