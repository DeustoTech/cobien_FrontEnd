# virtual_assistant/commands.py
import os

def load_contact_names():
    """
    Charge les prénoms depuis contacts/list_contacts.txt
    Format attendu : Prenom=identifiant
    """
    names = []

    base_dir = os.path.dirname(__file__)  # virtual_assistant/
    contacts_file = os.path.join(base_dir, "..", "contacts", "list_contacts.txt")

    try:
        with open(contacts_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or "=" not in line:
                    continue
                prenom = line.split("=", 1)[0].strip().lower()
                if prenom:
                    names.append(prenom)

    except FileNotFoundError:
        print(f"[WARN] Fichier contacts introuvable: {contacts_file}")

    return names

CONTACT_NAMES = load_contact_names()

COMMANDS = {
    "weather": {
        "keywords": [
            # French
            "météo", "meteo", "prévision", "prévisions",
            # Spanish
            "tiempo", "clima", "pronóstico", "pronostico",
        ],
        "nav": "tiempo",
    },
    "events": {
        "keywords": [
            "agenda", "agencia", "calendrier", "événement",
            "calendario", "eventos",
        ],
        "nav": "eventos",
    },
    "contacts": {
        "keywords": [
            "appelle", "appeler", "appel",
            "llamar", "llamada", "contacto", "contactos", "llama"
        ] + CONTACT_NAMES,
        "nav": "llamame",
    },
    "gallery": {
        "keywords": [
            "galerie", "galeria",
            "photo", "foto",
            "message", "pizarra", "mensaje", "mensajes"
        ],
        "nav": "pizarra",
    },
    "main": {
        "keywords": [
            "accueil", "recepcion",
            "début", "comienzo",
            "principal", "retourner", "volver", "retour"
            "initial", "inicio"
        ],
        "nav": "main",
    },
}


def refresh_contact_keywords():
    """Reload contact names from disk and refresh contact command keywords."""
    global CONTACT_NAMES
    CONTACT_NAMES = load_contact_names()
    base_keywords = [
        "appelle", "appeler", "appel",
        "llamar", "llamada", "contacto", "contactos", "llama"
    ]
    COMMANDS["contacts"]["keywords"] = base_keywords + CONTACT_NAMES

def match_command(text: str):
    text = text.lower()

    for command in COMMANDS.values():
        for kw in command["keywords"]:
            if kw in text:
                return command["nav"]

    return None
