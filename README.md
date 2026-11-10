# Vidéothèque RT0705 : API REST (tiers données)

API REST de la vidéothèque partagée. C'est le **tiers d'accès aux données** de l'architecture 3 tiers :

```text
Navigateur  ──HTML──▶  serveur (Flask + Jinja)  ──HTTP + JSON──▶  API (ce dépôt)  ──▶  fichiers JSON
  client                  présentation                              données
```

- **Seul composant qui lit et écrit les données** : le fichier `data/videotheque.json`.
- **Seul composant qui applique les règles métier** (RG1 à RG13) et vérifie les droits.
- **Réponses toujours en JSON**, y compris les erreurs.
- **Aucun port publié** : l'API n'est joignable que par les conteneurs du réseau Docker `videotheque_net`, c'est-à-dire par le site web du dépôt `serveur/`.

Dépendances : **Flask** uniquement, plus la bibliothèque standard Python.

* * *

## Prérequis

- Docker et Docker Compose v2 : `docker compose version`
- Le réseau Docker commun, à créer **une seule fois** :

```bash
docker network create videotheque_net
```

## Lancement seul (sans le site)

Pour lancer **toute l'application** (API + site), utilise plutôt la commande unique décrite dans le README du dépôt `serveur/`.

```bash
cd API
cp .env.exemple .env                       # facultatif : voir « Configuration »
docker compose up -d --build
docker compose ps                          # « Up ... (healthy) » après quelques secondes
docker compose logs api
```

Au premier démarrage, `data/videotheque.json` est créé à partir de `data_init/videotheque.exemple.json` (données de démonstration). Si ce fichier est absent, la structure vide `videotheque.template.json` est utilisée.

L'API n'étant pas publiée, on la teste **depuis le réseau Docker** :

```bash
# Test rapide depuis le conteneur lui-même
docker compose exec api python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:5001/api/sante').read())"

# curl dans un conteneur jetable relié au réseau de l'API
docker run --rm --network videotheque_net curlimages/curl -s "http://api:5001/api/films?q=incep"
```

Arrêt : `docker compose down`. Les données sont conservées dans `data/`.

* * *

## Configuration

Fichier `.env` (non versionné), modèle fourni dans `.env.exemple` :

| Variable | Défaut | Rôle |
| --- | --- | --- |
| `FLASK_DEBUG` | `0` | `1` : rechargement automatique du code et page de débogage (développement uniquement) |
| `ADMIN_MOT_DE_PASSE` | *(vide)* | Si défini et qu'aucun admin n'existe, le compte `admin` est créé au démarrage |
| `TMDB_API_KEY` | *(vide)* | Clé TMDb pour l'import de fiches (bonus). Sans clé, l'import répond proprement 503 |

Les paramètres des règles de gestion sont dans `docker-compose.yml` : `QUOTA_PRETS=3` (RG5), `DUREE_PRET_JOURS=14` (RG6), `SESSION_DUREE_HEURES=24`.

### Comptes

| Login | Rôle | Mot de passe |
| --- | --- | --- |
| `camille` | Administrateur | `videotheque` |
| `lucas`, `ines` | Membre | `videotheque` |
| `theo` | Membre **désactivé** (connexion refusée) | `videotheque` |

Pour créer ou réinitialiser le compte `admin`, le mot de passe est demandé deux fois sans être affiché :

```bash
docker compose run --rm api flask creer-admin
```

### Import TMDb (bonus F15)

1. Crée un compte gratuit sur [themoviedb.org](https://www.themoviedb.org), puis va dans **Paramètres → API**.
2. Copie la « Clé d'API » ou le « Jeton d'accès en lecture » (commence par `eyJ`). Les deux formats sont acceptés.
3. Ajoute `TMDB_API_KEY=...` dans `API/.env`, puis lance `docker compose up -d` pour recréer le conteneur.

L'import ne fait que **proposer** une fiche (titre, année, durée, genres, synopsis en français, affiche, réalisation, 5 acteurs). L'enregistrement passe par `POST /api/films` et toutes ses règles.

* * *

## Routes

Préfixe `/api`. Authentification : en-tête `Authorization: Bearer <jeton>`, obtenu par `POST /api/sessions`.

| Ressource | Routes | Accès |
| --- | --- | --- |
| Santé | `GET /sante` | Public |
| Sessions | `POST /sessions` · `DELETE /sessions/current` | Public / connecté |
| Profil | `GET` · `PATCH /utilisateurs/me` | Connecté |
| Comptes | `GET` · `POST /utilisateurs` · `GET` · `PATCH /utilisateurs/{id}` | Admin |
| Suivis | `GET /utilisateurs/me/suivis` · `GET` · `PUT /utilisateurs/me/suivis/{filmId}` | Connecté |
| Films | `GET /films` (filtres `q`, `genre`, `annee`, `realisateur`, `acteur`, `type`, `disponible`, `tri`, `ordre`, `page`, `taille`) · `GET /films/{id}` | Public |
| | `POST /films` · `PATCH` · `DELETE /films/{id}` | Admin |
| Supports | `GET /films/{id}/supports` · `GET /supports/{id}` | Public |
| | `POST /films/{id}/supports` · `PATCH` · `DELETE /supports/{id}` | Admin |
| Personnes | `GET /personnes` · `GET /personnes/{id}` | Public |
| | `PATCH /personnes/{id}` | Admin |
| Prêts | `POST /prets` · `GET /prets` · `GET /prets/{id}` · `POST /prets/{id}/retour` | Connecté (un membre ne voit que ses prêts, RG9) |
| Métadonnées | `GET /metadonnees?titre=&annee=` | Admin |

Format commun des erreurs, avec un code stable pour le client et un message lisible :

```json
{"erreur": {"code": "QUOTA_ATTEINT", "message": "Vous avez déjà 3 prêts en cours...", "details": {"quota": 3, "pretsEnCours": 3}}}
```

Codes HTTP utilisés : 200, 201 (+ `Location`), 204, 400, 401, 403, 404, 409, 503.

La description complète des routes et des formats JSON se trouve dans le document d'architecture, sections 2.4 à 2.6.

* * *

## Choix techniques

**Pas de base de données : un fichier JSON unique.** C'est la consigne du TP (« API REST agissant sur un stockage JSON »), et c'est adapté au volume : quelques milliers de films tiennent dans quelques Mo. Un seul fichier permet des écritures **tout ou rien** sans gérer de transactions : ajouter un film touche 3 collections, en supprimer un en touche 5.

**Écritures protégées contre la concurrence** (`app/db.py`) :

1. **Verrou** `fcntl.flock` sur un fichier annexe `videotheque.json.lock` : partagé en lecture, exclusif en écriture. Il fonctionne entre threads comme entre processus.
2. **Écriture atomique** : écriture dans un fichier temporaire, puis `os.replace()`. Le fichier n'est jamais à moitié écrit, même en cas de panne.
3. **Transaction** : `with db.ecriture() as donnees:`. Si une règle métier lève une erreur dans le bloc, **rien n'est écrit**.

Le verrou est posé sur un fichier annexe parce que le renommage **remplace** le fichier de données : un verrou posé sur l'ancien ne protégerait plus rien.

Un test le démontre : sans verrou, 6 demandes simultanées d'emprunt du même DVD obtiennent toutes « 201 Created », alors qu'un seul prêt est enregistré. Avec le verrou, une seule réussit et les 5 autres reçoivent 409.

**Trois couches** :

| Couche | Rôle |
| --- | --- |
| `routes/` | HTTP : lit la requête, ouvre la transaction, renvoie le JSON |
| `services/` | Règles métier pures, sans HTTP ni fichiers |
| `db.py` | Seul module qui touche aux fichiers |

**Données calculées non stockées** : la disponibilité d'un support, le retard d'un prêt et la note moyenne d'un film sont recalculés à chaque lecture. Aucune incohérence possible, aucune tâche planifiée.

**Sessions** : jeton aléatoire opaque stocké dans `data/sessions.json`, valable 24 h. Il est révocable immédiatement : déconnexion, ou désactivation du compte (RG10). Les mots de passe sont hachés avec scrypt (`werkzeug.security`).

**Données de référence versionnées, données vivantes ignorées** : `data_init/` (exemple et template) est versionné, en lecture seule dans le conteneur. `data/` est exclu de Git : il change à chaque emprunt et contient des hachages de mots de passe.

* * *

## Tests

Le scénario parcourt toutes les routes et toutes les règles de gestion, dont les emprunts simultanés (125 vérifications). Il s'exécute dans le conteneur, seul endroit d'où l'API est joignable :

```bash
docker compose exec -T api python - < scripts/scenario_api.py
```

Il est rejouable : il nettoie ce qu'il crée, sauf un compte `test_<horodatage>` désactivé à chaque passage. Pour repartir des données de démonstration :

```bash
docker compose down && rm -f data/*.json data/*.lock && docker compose up -d
```

* * *

## Arborescence

```text
API/
├── Dockerfile               image Flask générique (identique à celle du site)
├── docker-compose.yml       service api, healthcheck, volumes, réseau externe
├── requirements.txt         Flask
├── .env.exemple             modèle du fichier .env
├── app/                     code (monté sur /app)
│   ├── app.py               création de l'app, erreurs JSON, démarrage, commande creer-admin
│   ├── config.py            configuration et énumérations du modèle
│   ├── db.py                stockage : verrou, écriture atomique, initialisation
│   ├── auth.py              sessions et décorateurs de droits
│   ├── validation.py        validation des corps JSON et des paramètres
│   ├── erreurs.py           format d'erreur commun
│   ├── metadonnees.py       client TMDb (bonus)
│   ├── routes/              un Blueprint par ressource
│   └── services/            règles métier par domaine
├── data/                    données vivantes (monté sur /data, non versionné)
├── data_init/               jeu de démonstration et structure vide (monté sur /data_init, lecture seule)
└── scripts/scenario_api.py  scénario de test
```

## Limites connues

- **Serveur de développement Flask** (`flask run`) : suffisant pour le TP. En production, on utiliserait un serveur WSGI (gunicorn) et HTTPS devant le site.
- **Verrou sur un seul hôte** : `flock` protège les processus d'une même machine. Il ne convient pas à un stockage réseau partagé entre plusieurs serveurs.
- **Personnes identifiées par leur nom** (RG12) : deux homonymes réels seraient fusionnés.

Données de films et affiches importées : ce produit utilise l'API TMDb, sans être approuvé ni certifié par TMDb.
