"""Keyword-based command matcher for the voice assistant.

This module loads contact names dynamically and maps recognized utterances to
navigation targets used by the Kivy application.
"""

import os
from typing import Dict, List, Optional

def load_contact_names() -> List[str]:
    """Load contact first names from the contacts mapping file.

    Expected format per line:
    ``DisplayName=identifier``

    Returns:
        Lower-cased contact display names. Returns an empty list when the file
        is missing.

    Examples:
        >>> names = load_contact_names()
        >>> isinstance(names, list)
        True
    """
    names = []

    base_dir = os.path.dirname(__file__)
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
        print(f"[WARN] Contacts file not found: {contacts_file}")

    return names

CONTACT_NAMES = load_contact_names()

COMMANDS: Dict[str, Dict[str, List[str] | str]] = {
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
    """Reload contact names and rebuild contact-related keywords list.

    Returns:
        None.
    """
    global CONTACT_NAMES
    CONTACT_NAMES = load_contact_names()
    base_keywords = [
        "appelle", "appeler", "appel",
        "llamar", "llamada", "contacto", "contactos", "llama"
    ]
    COMMANDS["contacts"]["keywords"] = base_keywords + CONTACT_NAMES

def match_command(text: str) -> Optional[str]:
    """Match an utterance against known keyword groups.

    Args:
        text: Recognized user utterance.

    Returns:
        Navigation target key when a keyword match is found, otherwise ``None``.

    Examples:
        >>> match_command("quiero ver el tiempo") in {"tiempo", None}
        True
    """
    text = text.lower()

    for command in COMMANDS.values():
        for kw in command["keywords"]:
            if kw in text:
                return command["nav"]

    return None
