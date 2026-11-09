"""Scénario de test de l'API REST de la vidéothèque

Parcourt toutes les routes et vérifie les codes HTTP et les règles de gestion :

    docker compose exec -T api python - < scripts/scenario_api.py

Prérequis : données de démonstration (comptes camille/lucas/ines, mot de passe
« videotheque »)
Le scénario nettoie ce qu'il crée, sauf le compte de test (les comptes ne se suppriment pas, RG10)
"""
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request

API = os.environ.get("API_TEST_URL", "http://localhost:5001/api")
MOT_DE_PASSE_DEMO = "videotheque"
SUFFIXE = str(int(time.time()))

resultats = {"ok": 0, "echec": 0}


# --- Outils --------------------------------------------------------------------

def appel(methode, chemin, jeton=None, corps=None):
    """Envoie une requête et renvoie (code HTTP, JSON décodé ou None, en-têtes)"""
    donnees = json.dumps(corps).encode() if corps is not None else None
    requete = urllib.request.Request(API + chemin, data=donnees, method=methode)
    if corps is not None:
        requete.add_header("Content-Type", "application/json")
    if jeton:
        requete.add_header("Authorization", f"Bearer {jeton}")
    try:
        with urllib.request.urlopen(requete, timeout=10) as reponse:
            code, brut, entetes = reponse.status, reponse.read(), reponse.headers
    except urllib.error.HTTPError as erreur:
        code, brut, entetes = erreur.code, erreur.read(), erreur.headers
    return code, (json.loads(brut) if brut else None), entetes


def verifier(description, condition, detail=""):
    if condition:
        resultats["ok"] += 1
        print(f" [OK] {description}")
    else:
        resultats["echec"] += 1
        print(f" [KO] {description}  {detail}")


def attendre(description, code_attendu, reponse, code_erreur=None):
    """Vérifie le code HTTP (et le code d'erreur métier) d'une réponse d'appel()"""
    code, corps, _ = reponse
    ok = code == code_attendu
    if ok and code_erreur:
        ok = (corps or {}).get("erreur", {}).get("code") == code_erreur
    attendu = f"{code_attendu}" + (f" {code_erreur}" if code_erreur else "")
    verifier(f"{description} → {attendu}", ok, f"(reçu {code} : {json.dumps(corps, ensure_ascii=False)[:200]})")
    return corps


def connexion(login):
    corps = attendre(f"connexion de {login}", 201,
                     appel("POST", "/sessions", corps={"login": login, "motDePasse": MOT_DE_PASSE_DEMO}))
    return corps["jeton"], corps["utilisateur"]


def titre(texte):
    print(f"\n=== {texte}")


# --- Scénario --------------------------------------------------------------------

titre("Santé et routes inconnues")
attendre("GET /sante", 200, appel("GET", "/sante"))
attendre("route inconnue", 404, appel("GET", "/inexistante"), "RESSOURCE_INTROUVABLE")
attendre("méthode non autorisée", 405, appel("PUT", "/films"), "METHODE_NON_AUTORISEE")

titre("Catalogue public (F04, F08, F09)")
corps = attendre("liste des films", 200, appel("GET", "/films"))
verifier("au moins 6 films dans le jeu de démo", corps["pagination"]["total"] >= 6)
corps = attendre("recherche « incep »", 200, appel("GET", "/films?q=incep"))
verifier("1 résultat : Inception", [f["titre"] for f in corps["elements"]] == ["Inception"])
corps = attendre("films de Nolan triés par année", 200, appel("GET", "/films?realisateur=nolan&tri=annee"))
verifier("Inception puis Interstellar", [f["titre"] for f in corps["elements"]] == ["Inception", "Interstellar"])
corps = attendre("films avec un support DVD", 200, appel("GET", "/films?type=DVD"))
verifier("2 films en DVD", corps["pagination"]["total"] == 2)
corps = attendre("tri par note décroissante", 200, appel("GET", "/films?tri=note&ordre=desc"))
notes = [f["noteMoyenne"] for f in corps["elements"]]
verifier("les films notés d'abord, sans note à la fin", notes[0] is not None and notes[-1] is None)
attendre("paramètre annee invalide", 400, appel("GET", "/films?annee=abc"), "VALIDATION")
attendre("paramètre tri invalide", 400, appel("GET", "/films?tri=prix"), "VALIDATION")
corps = attendre("pagination taille=2 page=2", 200, appel("GET", "/films?taille=2&page=2"))
verifier("2 éléments en page 2", len(corps["elements"]) == 2 and corps["pagination"]["page"] == 2)

corps = attendre("fiche d'Inception", 200, appel("GET", "/films?q=inception"))
id_inception = corps["elements"][0]["id"]
fiche = attendre("GET /films/{id}", 200, appel("GET", f"/films/{id_inception}"))
verifier("la fiche contient réalisateurs, acteurs, supports, avis",
         all(k in fiche for k in ("realisateurs", "acteurs", "supports", "noteMoyenne", "avis")))
id_nolan = fiche["realisateurs"][0]["id"]
attendre("film inexistant", 404, appel("GET", "/films/inconnu"), "RESSOURCE_INTROUVABLE")

titre("Sessions (F01, RG10)")
attendre("mauvais mot de passe", 401,
         appel("POST", "/sessions", corps={"login": "lucas", "motDePasse": "faux"}), "IDENTIFIANTS_INCORRECTS")
attendre("compte désactivé (theo)", 401,
         appel("POST", "/sessions", corps={"login": "theo", "motDePasse": MOT_DE_PASSE_DEMO}), "IDENTIFIANTS_INCORRECTS")
attendre("corps non JSON", 400, appel("POST", "/sessions", corps=["pas", "un", "objet"]), "VALIDATION")
jeton_admin, admin = connexion("camille")
jeton_lucas, lucas = connexion("lucas")
jeton_ines, ines = connexion("ines")
corps = attendre("GET /utilisateurs/me", 200, appel("GET", "/utilisateurs/me", jeton_lucas))
verifier("le hachage du mot de passe n'est jamais renvoyé", "motDePasseHash" not in corps)
attendre("sans jeton", 401, appel("GET", "/utilisateurs/me"), "NON_AUTHENTIFIE")
attendre("jeton bidon", 401, appel("GET", "/utilisateurs/me", "bidon"), "NON_AUTHENTIFIE")

titre("Gestion des films (F06, RG1, RG12)")
nouveau_film = {
    "titre": f"Film de test {SUFFIXE}", "annee": 2026, "dureeMinutes": 95,
    "genres": ["Drame", " drame ", "Comédie"],
    "realisateurs": ["christopher   NOLAN"],                  # doit être rattaché à Nolan (RG12)
    "acteurs": [f"Acteur Test {SUFFIXE}", "Zendaya"],
}
attendre("création sans jeton", 401, appel("POST", "/films", corps=nouveau_film))
attendre("création par un membre", 403, appel("POST", "/films", jeton_lucas, nouveau_film), "ACCES_INTERDIT")
corps = attendre("création invalide", 400,
                 appel("POST", "/films", jeton_admin, {"titre": "", "annee": 1700, "dureeMinutes": "long"}), "VALIDATION")
verifier("les erreurs détaillent chaque champ", set(corps["erreur"]["details"]) == {"titre", "annee", "dureeMinutes"})
code, film, entetes = appel("POST", "/films", jeton_admin, nouveau_film)
attendre("création par l'admin", 201, (code, film, entetes))
id_film = film["id"]
verifier("en-tête Location renvoyé", entetes.get("Location", "").endswith(f"/api/films/{id_film}"))
verifier("genres dédoublonnés", film["genres"] == ["Drame", "Comédie"])
verifier("réalisateur rattaché à la personne existante (RG12)", film["realisateurs"] == [{"id": id_nolan, "nom": "Christopher Nolan"}])
attendre("doublon titre + année (casse différente)", 409,
         appel("POST", "/films", jeton_admin, {**nouveau_film, "titre": nouveau_film["titre"].upper()}), "FILM_EXISTANT")
corps = attendre("modification partielle", 200,
                 appel("PATCH", f"/films/{id_film}", jeton_admin, {"dureeMinutes": 100, "synopsis": "Un test."}))
verifier("durée modifiée, titre conservé", corps["dureeMinutes"] == 100 and corps["titre"] == nouveau_film["titre"])
attendre("modification d'un champ non modifiable", 400,
         appel("PATCH", f"/films/{id_film}", jeton_admin, {"dateAjout": "2000-01-01"}), "VALIDATION")

titre("Supports (F07, RG3)")
def creer_support(corps_support):
    return attendre(f"ajout d'un support {corps_support.get('type', corps_support['categorie'])}", 201,
                    appel("POST", f"/films/{id_film}/supports", jeton_admin, corps_support))["id"]
ids_physiques = [creer_support({"categorie": "PHYSIQUE", "type": "DVD", "emplacement": f"Test {i}"}) for i in range(5)]
id_numerique = creer_support({"categorie": "NUMERIQUE", "format": "MKV", "chemin": "/media/test.mkv", "tailleGo": 2.5})
attendre("support sans catégorie", 400, appel("POST", f"/films/{id_film}/supports", jeton_admin, {"type": "DVD"}), "VALIDATION")
attendre("support physique sans type", 400,
         appel("POST", f"/films/{id_film}/supports", jeton_admin, {"categorie": "PHYSIQUE"}), "VALIDATION")
attendre("changer la catégorie", 400,
         appel("PATCH", f"/supports/{id_numerique}", jeton_admin, {"categorie": "PHYSIQUE"}), "VALIDATION")
corps = attendre("liste des supports du film", 200, appel("GET", f"/films/{id_film}/supports"))
verifier("6 supports, le numérique jamais disponible",
         len(corps) == 6 and not next(s for s in corps if s["id"] == id_numerique)["disponible"])

titre("Emprunts (F10, RG3, RG4, RG5)")
code, pret_ines, _ = appel("POST", "/prets", jeton_ines, {"supportId": ids_physiques[0]})
attendre("Inès emprunte le DVD n°0", 201, (code, pret_ines, None))
verifier("retour prévu 14 jours plus tard (RG6)", pret_ines["dateRetourPrevue"] > pret_ines["dateDebut"])
attendre("Lucas emprunte le même DVD", 409, appel("POST", "/prets", jeton_lucas, {"supportId": ids_physiques[0]}), "SUPPORT_INDISPONIBLE")
attendre("emprunter un support numérique", 400,
         appel("POST", "/prets", jeton_lucas, {"supportId": id_numerique}), "SUPPORT_NON_EMPRUNTABLE")
attendre("emprunter un support inconnu", 404, appel("POST", "/prets", jeton_lucas, {"supportId": "inconnu"}))
attendre("emprunter sans être connecté", 401, appel("POST", "/prets", corps={"supportId": ids_physiques[1]}))

# Lucas a déjà 1 prêt en cours dans le jeu de démo : 2 de plus atteignent le quota de 3
prets_lucas = []
for i in (1, 2):
    code, corps, _ = appel("POST", "/prets", jeton_lucas, {"supportId": ids_physiques[i]})
    attendre(f"Lucas emprunte le DVD n°{i}", 201, (code, corps, None))
    prets_lucas.append(corps["id"])
attendre("4e emprunt de Lucas", 409, appel("POST", "/prets", jeton_lucas, {"supportId": ids_physiques[3]}), "QUOTA_ATTEINT")

titre("Consultation des prêts (F12, F13, RG9)")
corps = attendre("Lucas liste ses prêts", 200, appel("GET", "/prets?statut=EN_COURS", jeton_lucas))
verifier("uniquement les prêts de Lucas", all(p["emprunteur"]["login"] == "lucas" for p in corps["elements"]))
attendre("Lucas filtre sur Inès", 403, appel("GET", f"/prets?utilisateurId={ines['id']}", jeton_lucas), "ACCES_INTERDIT")
corps = attendre("l'admin filtre sur Inès", 200, appel("GET", f"/prets?utilisateurId={ines['id']}", jeton_admin))
verifier("les prêts d'Inès", corps["elements"] and all(p["emprunteur"]["login"] == "ines" for p in corps["elements"]))
corps = attendre("l'admin liste les retards", 200, appel("GET", "/prets?enRetard=true", jeton_admin))
verifier("tous les prêts listés sont en retard", corps["elements"] and all(p["enRetard"] for p in corps["elements"]))
attendre("Lucas consulte le prêt d'Inès", 403, appel("GET", f"/prets/{pret_ines['id']}", jeton_lucas), "ACCES_INTERDIT")

titre("Suppression bloquée par un prêt en cours (RG7)")
attendre("supprimer un support prêté", 409, appel("DELETE", f"/supports/{ids_physiques[0]}", jeton_admin), "PRET_EN_COURS")
attendre("supprimer le film", 409, appel("DELETE", f"/films/{id_film}", jeton_admin), "PRET_EN_COURS")

titre("Retours (F11, F13, RG9)")
attendre("Lucas rend le prêt d'Inès", 403, appel("POST", f"/prets/{pret_ines['id']}/retour", jeton_lucas), "ACCES_INTERDIT")
corps = attendre("Inès rend son prêt avec une remarque", 200,
                 appel("POST", f"/prets/{pret_ines['id']}/retour", jeton_ines, {"remarque": "Boîtier fendu"}))
verifier("statut RENDU, clôturé par Inès", corps["statut"] == "RENDU" and corps["retourEnregistrePar"] == ines["id"])
attendre("rendre deux fois", 409, appel("POST", f"/prets/{pret_ines['id']}/retour", jeton_ines), "PRET_DEJA_RENDU")
corps = attendre("l'admin clôture un prêt de Lucas", 200, appel("POST", f"/prets/{prets_lucas[0]}/retour", jeton_admin))
verifier("clôture tracée au nom de l'admin", corps["retourEnregistrePar"] == admin["id"])
attendre("Lucas rend son autre prêt (sans corps)", 200, appel("POST", f"/prets/{prets_lucas[1]}/retour", jeton_lucas))
attendre("déclarer le DVD n°4 perdu", 200, appel("PATCH", f"/supports/{ids_physiques[4]}", jeton_admin, {"etat": "PERDU"}))
attendre("emprunter un support perdu", 409, appel("POST", "/prets", jeton_lucas, {"supportId": ids_physiques[4]}), "SUPPORT_INDISPONIBLE")

titre("Emprunts simultanés du même support (verrou, RG4)")
codes = []
def emprunt_concurrent(jeton):
    codes.append(appel("POST", "/prets", jeton, {"supportId": ids_physiques[3]})[0])
fils = [threading.Thread(target=emprunt_concurrent, args=(j,)) for j in (jeton_admin, jeton_lucas, jeton_ines) * 2]
for f in fils:
    f.start()
for f in fils:
    f.join()
verifier(f"6 demandes simultanées : une seule réussit (codes {sorted(codes)})",
         codes.count(201) == 1 and codes.count(409) == 5)
corps = attendre("prêts en cours sur ce support", 200, appel("GET", "/prets?statut=EN_COURS", jeton_admin))
gagnant = [p for p in corps["elements"] if p["supportId"] == ids_physiques[3]]
verifier("exactement un prêt en cours enregistré", len(gagnant) == 1)
attendre("l'admin clôture ce prêt", 200, appel("POST", f"/prets/{gagnant[0]['id']}/retour", jeton_admin))

titre("Suivi personnel et avis (F14, RG8)")
suivi = {"vu": True, "note": 4, "commentaire": "Pas mal du tout."}
attendre("premier suivi", 201, appel("PUT", f"/utilisateurs/me/suivis/{id_film}", jeton_lucas, suivi))
attendre("même suivi renvoyé (idempotent)", 200, appel("PUT", f"/utilisateurs/me/suivis/{id_film}", jeton_lucas, suivi))
attendre("note hors limites", 400, appel("PUT", f"/utilisateurs/me/suivis/{id_film}", jeton_lucas, {"vu": True, "note": 9}), "VALIDATION")
attendre("suivi d'Inès inexistant", 404, appel("GET", f"/utilisateurs/me/suivis/{id_film}", jeton_ines))
attendre("Inès note le film 2/5", 201, appel("PUT", f"/utilisateurs/me/suivis/{id_film}", jeton_ines, {"vu": True, "note": 2}))
corps = attendre("fiche du film", 200, appel("GET", f"/films/{id_film}"))
verifier("note moyenne 3.0 sur 2 notes", corps["noteMoyenne"] == 3.0 and corps["nombreNotes"] == 2)
verifier("l'avis de Lucas est affiché", any(a["login"] == "lucas" and a["commentaire"] for a in corps["avis"]))

titre("Personnes (F16, F17, RG12)")
corps = attendre("recherche de personnes « nolan »", 200, appel("GET", "/personnes?q=nolan"))
verifier("une seule personne Nolan", corps["pagination"]["total"] == 1)
corps = attendre("filmographie de Nolan", 200, appel("GET", f"/personnes/{id_nolan}"))
verifier("3 films réalisés (dont le film de test)", len(corps["filmographie"]["REALISATEUR"]) == 3)
id_acteur_test = next(a["id"] for a in film["acteurs"] if a["nom"].startswith("Acteur Test"))
attendre("renommer en un nom déjà pris", 409,
         appel("PATCH", f"/personnes/{id_acteur_test}", jeton_admin, {"nom": "zendaya"}), "NOM_DEJA_PRIS")
corps = attendre("corriger le nom", 200,
                 appel("PATCH", f"/personnes/{id_acteur_test}", jeton_admin, {"nom": f"Acteur Corrigé {SUFFIXE}"}))
attendre("renommer en tant que membre", 403,
         appel("PATCH", f"/personnes/{id_acteur_test}", jeton_lucas, {"nom": "X"}), "ACCES_INTERDIT")

titre("Nettoyage : suppression du film de test (RG11)")
attendre("suppression d'un support libre", 204, appel("DELETE", f"/supports/{ids_physiques[1]}", jeton_admin))
attendre("suppression du film", 204, appel("DELETE", f"/films/{id_film}", jeton_admin))
attendre("le film n'existe plus", 404, appel("GET", f"/films/{id_film}"))
attendre("ses supports non plus", 404, appel("GET", f"/supports/{ids_physiques[0]}"))
corps = attendre("Nolan existe toujours (personnes conservées)", 200, appel("GET", f"/personnes/{id_nolan}"))
verifier("filmographie de Nolan revenue à 2 films", len(corps["filmographie"]["REALISATEUR"]) == 2)

titre("Profil et comptes (F02, F03, RG10)")
attendre("profil : mauvais mot de passe actuel", 403,
         appel("PATCH", "/utilisateurs/me", jeton_lucas, {"motDePasseActuel": "faux", "email": "x@y.fr"}), "MOT_DE_PASSE_INCORRECT")
attendre("profil : changer son rôle", 400,
         appel("PATCH", "/utilisateurs/me", jeton_lucas, {"motDePasseActuel": MOT_DE_PASSE_DEMO, "role": "ADMIN"}), "VALIDATION")
attendre("un membre liste les comptes", 403, appel("GET", "/utilisateurs", jeton_lucas), "ACCES_INTERDIT")
attendre("l'admin liste les comptes", 200, appel("GET", "/utilisateurs?actif=true", jeton_admin))
nouveau_compte = {"login": f"test_{SUFFIXE}", "email": f"test_{SUFFIXE}@videotheque.local", "motDePasse": "motdepasse-test"}
corps = attendre("création d'un compte", 201, appel("POST", "/utilisateurs", jeton_admin, nouveau_compte))
id_test = corps["id"]
verifier("rôle MEMBRE par défaut", corps["role"] == "MEMBRE")
attendre("login déjà pris", 409, appel("POST", "/utilisateurs", jeton_admin, nouveau_compte), "LOGIN_OU_EMAIL_PRIS")
attendre("mot de passe trop court", 400,
         appel("POST", "/utilisateurs", jeton_admin, {**nouveau_compte, "login": "autre", "motDePasse": "court"}), "VALIDATION")
corps = attendre("connexion du nouveau compte", 201,
                 appel("POST", "/sessions", corps={"login": nouveau_compte["login"], "motDePasse": "motdepasse-test"}))
jeton_test = corps["jeton"]
attendre("désactivation par l'admin", 200, appel("PATCH", f"/utilisateurs/{id_test}", jeton_admin, {"actif": False}))
attendre("son jeton est révoqué immédiatement", 401, appel("GET", "/utilisateurs/me", jeton_test), "NON_AUTHENTIFIE")
attendre("il ne peut plus se connecter", 401,
         appel("POST", "/sessions", corps={"login": nouveau_compte["login"], "motDePasse": "motdepasse-test"}))
attendre("le dernier admin ne peut pas se rétrograder", 409,
         appel("PATCH", f"/utilisateurs/{admin['id']}", jeton_admin, {"role": "MEMBRE"}), "DERNIER_ADMIN")

titre("Déconnexion")
attendre("DELETE /sessions/current", 204, appel("DELETE", "/sessions/current", jeton_lucas))
attendre("le jeton ne fonctionne plus", 401, appel("GET", "/utilisateurs/me", jeton_lucas))

print(f"\n{resultats['ok']} vérifications réussies, {resultats['echec']} en échec")
sys.exit(1 if resultats["echec"] else 0)
