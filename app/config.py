"""Configuration de l'API, lue dans les variables d'environnement"""
import os

# --- Fichiers -----------------------------------------------------------------
DATA_DIR = os.environ.get("DATA_DIR", "/data")
DATA_INIT_DIR = os.environ.get("DATA_INIT_DIR", "/data_init")
# Fichiers de référence copiés au premier démarrage si data/videotheque.json n'existe pas
FICHIER_EXEMPLE = os.path.join(DATA_INIT_DIR, "videotheque.exemple.json")
FICHIER_TEMPLATE = os.path.join(DATA_INIT_DIR, "videotheque.template.json")

# --- Règles de gestion paramétrables ----------------------------------------
QUOTA_PRETS = int(os.environ.get("QUOTA_PRETS", "3"))                     # RG5
DUREE_PRET_JOURS = int(os.environ.get("DUREE_PRET_JOURS", "14"))          # RG6
SESSION_DUREE_HEURES = int(os.environ.get("SESSION_DUREE_HEURES", "24"))

# --- Compte administrateur initial --------------------------------------------
ADMIN_LOGIN = "admin"
ADMIN_MOT_DE_PASSE = os.environ.get("ADMIN_MOT_DE_PASSE") or None

# --- Pagination ---------------------------------------------------------------
TAILLE_PAGE_DEFAUT = 20
TAILLE_PAGE_MAX = 100

# --- Énumérations du modèle -----------------------------------------------------
CATEGORIES_SUPPORT = ("PHYSIQUE", "NUMERIQUE")
TYPES_PHYSIQUES = ("DVD", "BLU_RAY", "BLU_RAY_4K", "VHS")
ETATS_SUPPORT = ("NEUF", "BON", "USE", "ENDOMMAGE", "PERDU")
ROLES_UTILISATEUR = ("MEMBRE", "ADMIN")
ROLES_PARTICIPATION = ("REALISATEUR", "ACTEUR")
STATUTS_PRET = ("EN_COURS", "RENDU")
