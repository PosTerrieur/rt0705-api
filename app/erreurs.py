"""Erreurs métier renvoyées au client au format JSON commun"""


class ErreurApi(Exception):
    """Erreur prévue : elle devient une réponse {"erreur": {...}} avec le bon code HTTP"""

    def __init__(self, statut, code, message, details=None):
        super().__init__(message)
        self.statut = statut      # code HTTP
        self.code = code          # code stable, exploitable par le client
        self.message = message    # texte lisible par un humain
        self.details = details

    def en_json(self):
        erreur = {"code": self.code, "message": self.message}
        if self.details:
            erreur["details"] = self.details
        return {"erreur": erreur}


def introuvable(objet):
    return ErreurApi(404, "RESSOURCE_INTROUVABLE", f"{objet} introuvable")


def acces_interdit(message="Accès interdit"):
    return ErreurApi(403, "ACCES_INTERDIT", message)


def conflit(code, message, details=None):
    return ErreurApi(409, code, message, details)
