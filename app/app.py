"""Point d'entrée de l'API REST de la vidéothèque (tiers données)

Lancement : flask run (voir docker-compose.yml)
Commande d'administration : flask creer-admin
"""
import click
from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

import config
import db
import routes
from erreurs import ErreurApi
from services import utilisateurs

app = Flask(__name__)
app.json.ensure_ascii = False   # accents lisibles dans les réponses JSON
app.json.sort_keys = False      # conserve l'ordre des champs

for blueprint in routes.BLUEPRINTS:
    app.register_blueprint(blueprint, url_prefix="/api")


@app.get("/api/sante")
def sante():
    return jsonify(statut="ok")


# --- Toutes les erreurs sont renvoyées en JSON --------------------------------

@app.errorhandler(ErreurApi)
def erreur_api(erreur):
    return jsonify(erreur.en_json()), erreur.statut


@app.errorhandler(HTTPException)
def erreur_http(erreur):
    """Erreurs levées par Flask lui-même : route inconnue, méthode non autorisée"""
    codes = {404: ("RESSOURCE_INTROUVABLE", "Route inconnue"),
             405: ("METHODE_NON_AUTORISEE", "Méthode HTTP non autorisée sur cette route")}
    code, message = codes.get(erreur.code, ("ERREUR_HTTP", erreur.description))
    return jsonify(erreur={"code": code, "message": message}), erreur.code


@app.errorhandler(Exception)
def erreur_interne(erreur):
    app.logger.exception("Erreur non prévue")
    return jsonify(erreur={"code": "ERREUR_INTERNE", "message": "Erreur interne du serveur"}), 500


# --- Démarrage : fichiers de données et compte admin --------------------------

def preparer_donnees():
    for action in db.initialiser():
        app.logger.warning(action)

    with db.lecture() as donnees:
        admin_present = bool(utilisateurs.admins_actifs(donnees))

    if not admin_present and config.ADMIN_MOT_DE_PASSE:
        with db.ecriture() as donnees:
            utilisateurs.creer_ou_reinitialiser_admin(donnees, config.ADMIN_MOT_DE_PASSE)
        app.logger.warning("Compte 'admin' créé à partir de ADMIN_MOT_DE_PASSE")
    elif not admin_present:
        app.logger.warning("Aucun administrateur actif : lancez « flask creer-admin »")


preparer_donnees()


@app.cli.command("creer-admin")
def creer_admin():
    """Crée (ou réinitialise) le compte 'admin' en demandant son mot de passe"""
    mot_de_passe = click.prompt("Mot de passe du compte admin", hide_input=True,
                                confirmation_prompt="Confirmation")
    if len(mot_de_passe) < utilisateurs.LONGUEUR_MIN_MOT_DE_PASSE:
        raise click.ClickException(
            f"{utilisateurs.LONGUEUR_MIN_MOT_DE_PASSE} caractères minimum")
    with db.ecriture() as donnees:
        utilisateurs.creer_ou_reinitialiser_admin(donnees, mot_de_passe)
    click.echo(f"Compte '{config.ADMIN_LOGIN}' prêt")
