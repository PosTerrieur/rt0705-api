"""Stockage JSON : seul module qui touche aux fichiers

- chaque fichier "nom.json" est protégé par un verrou posé sur un fichier
  annexe "nom.json.lock" (verrou partagé en lecture, exclusif en écriture)
- une écriture passe par un fichier temporaire, renommé ensuite à la place de
  l'original : le renommage est atomique, le fichier n'est jamais à moitié écrit

Utilisation :
    with db.lecture() as donnees:      # lecture seule
        ...
    with db.ecriture() as donnees:     # modification : enregistrée en sortie du bloc,
        ...                            # sauf si une exception est levée (rien n'est écrit)
"""
import fcntl
import json
import os
import tempfile
from contextlib import contextmanager

import config


def _chemin(nom):
    return os.path.join(config.DATA_DIR, f"{nom}.json")


@contextmanager
def _verrou(nom, exclusif):
    # Le mode "a" crée le fichier de verrou s'il n'existe pas, sans le vider
    with open(_chemin(nom) + ".lock", "a") as fichier_verrou:
        fcntl.flock(fichier_verrou, fcntl.LOCK_EX if exclusif else fcntl.LOCK_SH)
        try:
            yield
        finally:
            fcntl.flock(fichier_verrou, fcntl.LOCK_UN)


def _lire(nom):
    with open(_chemin(nom), encoding="utf-8") as f:
        return json.load(f)


def _ecrire(nom, donnees):
    """Écriture atomique : fichier temporaire dans le même dossier, puis renommage"""
    descripteur, chemin_temporaire = tempfile.mkstemp(
        dir=config.DATA_DIR, prefix=f".{nom}.", suffix=".tmp")
    try:
        with os.fdopen(descripteur, "w", encoding="utf-8") as f:
            json.dump(donnees, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())          # données réellement sur le disque
        os.replace(chemin_temporaire, _chemin(nom))
    except BaseException:
        if os.path.exists(chemin_temporaire):
            os.remove(chemin_temporaire)
        raise


@contextmanager
def lecture(nom="videotheque"):
    with _verrou(nom, exclusif=False):
        yield _lire(nom)


@contextmanager
def ecriture(nom="videotheque"):
    with _verrou(nom, exclusif=True):
        donnees = _lire(nom)
        yield donnees
        # Atteint seulement si le bloc "with" s'est terminé sans exception
        _ecrire(nom, donnees)


def _fichier_de_reference():
    """Fichier de data_init/ à copier : le jeu de démonstration, sinon la structure vide"""
    for chemin in (config.FICHIER_EXEMPLE, config.FICHIER_TEMPLATE):
        if os.path.exists(chemin):
            return chemin
    raise RuntimeError(
        f"Aucun fichier de référence dans {config.DATA_INIT_DIR} : "
        "vérifiez le montage du dossier data_init/ (docker-compose.yml)")


def initialiser():
    """Crée les fichiers de données manquants + renvoie la liste des actions faites"""
    os.makedirs(config.DATA_DIR, exist_ok=True)
    actions = []

    with _verrou("videotheque", exclusif=True):
        if not os.path.exists(_chemin("videotheque")):
            reference = _fichier_de_reference()
            with open(reference, encoding="utf-8") as f:
                _ecrire("videotheque", json.load(f))
            actions.append(f"videotheque.json créé à partir de {reference}")

    with _verrou("sessions", exclusif=True):
        if not os.path.exists(_chemin("sessions")):
            # Fichier technique sans modèle de référence : une liste de sessions vide
            _ecrire("sessions", {"sessions": []})
            actions.append("sessions.json créé vide")

    return actions
