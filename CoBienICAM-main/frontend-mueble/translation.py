# translation.py
# Module centralisé pour la gestion des traductions
# ==================================================
# Ce module fournit une instance unique de gestionnaire de traductions
# qui peut être importée et utilisée partout dans l'application.
# 
# Usage:
#   from translation import _
#   text = _("Bonjour")
#
# Pour changer de langue:
#   from translation import change_language
#   change_language("fr")

import gettext
import os
import ast
from typing import Dict


class PoTranslations:
    """Fallback simple de traducciones desde .po (sin requerir .mo)."""

    def __init__(self, catalog: Dict[str, str]):
        self._catalog = catalog or {}

    def gettext(self, message):
        return self._catalog.get(message, message)


def _unquote_po(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    if value[0] == '"' and value[-1] == '"':
        try:
            return ast.literal_eval(value)
        except Exception:
            return value[1:-1]
    return value


def _load_po_catalog(po_path: str) -> Dict[str, str]:
    """Parser minimal de .po para msgid/msgstr simples y multilínea."""
    catalog: Dict[str, str] = {}
    if not os.path.exists(po_path):
        return catalog

    current_id = None
    current_str = None
    mode = None

    def flush():
        nonlocal current_id, current_str, mode
        if current_id is not None and current_id != "" and current_str is not None and current_str != "":
            catalog[current_id] = current_str
        current_id = None
        current_str = None
        mode = None

    with open(po_path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                flush()
                continue
            if line.startswith("#"):
                continue
            if line.startswith("msgid "):
                if current_id is not None:
                    flush()
                current_id = _unquote_po(line[len("msgid "):])
                current_str = ""
                mode = "id"
                continue
            if line.startswith("msgstr "):
                current_str = _unquote_po(line[len("msgstr "):])
                mode = "str"
                continue
            if line.startswith('"'):
                if mode == "id" and current_id is not None:
                    current_id += _unquote_po(line)
                elif mode == "str" and current_str is not None:
                    current_str += _unquote_po(line)

    flush()
    return catalog

class TranslationManager:
    """
    Gestionnaire centralisé des traductions.
    Maintient une instance unique de gettext qui peut être mise à jour globalement.
    """
    
    def __init__(self):
        """Initialise le gestionnaire avec l'espagnol par défaut"""
        self._current_lang = "es"
        self._translation = None
        self.load_translation("es")
    
    def load_translation(self, lang):
        """
        Charge la traduction pour la langue donnée.
        
        Args:
            lang (str): Code langue ("es" ou "fr")
        """
        self._current_lang = lang

        localedir = os.path.join(os.path.dirname(__file__), 'locales')
        po_path = os.path.join(localedir, lang, "LC_MESSAGES", "app.po")

        # 1) Chemin nominal: gettext avec app.mo
        try:
            self._translation = gettext.translation(
                'app',
                localedir=localedir,
                languages=[lang],
                fallback=False
            )
            print(f"[TRANSLATION] ✅ Langue chargée: {lang}")
            return
        except Exception:
            pass

        # 2) Fallback: charger le .po directamente (parser interno)
        try:
            if os.path.exists(po_path):
                catalog = _load_po_catalog(po_path)
                self._translation = PoTranslations(catalog)
                print(f"[TRANSLATION] ✅ Langue chargée depuis PO: {lang}")
                return
        except Exception as e:
            print(f"[TRANSLATION] ⚠️ Erreur fallback PO ({lang}): {e}")

        # 3) Dernier fallback: identité
        print(f"[TRANSLATION] ⚠️ Aucun catalogue disponible pour '{lang}', fallback identity")
        self._translation = gettext.NullTranslations()
    
    def gettext(self, message):
        """
        Traduit un message.
        
        Args:
            message (str): Message à traduire
            
        Returns:
            str: Message traduit
        """
        if self._translation is None:
            return message
        return self._translation.gettext(message)
    
    def get_current_lang(self):
        """
        Retourne la langue actuelle.
        
        Returns:
            str: Code langue actuel ("es" ou "fr")
        """
        return self._current_lang


# ============================================================================
# INSTANCE GLOBALE UNIQUE
# ============================================================================
# Cette instance est partagée par toute l'application
_translation_manager = TranslationManager()


# ============================================================================
# FONCTION DE TRADUCTION GLOBALE
# ============================================================================
def _(message):
    """
    Fonction de traduction globale.
    Cette fonction peut être importée et utilisée partout.
    
    Args:
        message (str): Message à traduire
        
    Returns:
        str: Message traduit selon la langue actuelle
        
    Example:
        from translation import _
        print(_("Bonjour"))  # → "Hola" (si langue = "es")
    """
    return _translation_manager.gettext(message)


# ============================================================================
# FONCTION POUR CHANGER DE LANGUE
# ============================================================================
def change_language(lang):
    """
    Change la langue globalement pour toute l'application.
    Tous les appels à _() utiliseront automatiquement la nouvelle langue.
    
    Args:
        lang (str): Code langue ("es" pour espagnol, "fr" pour français)
        
    Example:
        from translation import change_language, _
        change_language("fr")
        print(_("Hola"))  # → "Bonjour"
    """
    _translation_manager.load_translation(lang)
    print(f"[TRANSLATION] 🌍 Langue changée globalement: {lang}")


# ============================================================================
# FONCTION POUR OBTENIR LA LANGUE ACTUELLE
# ============================================================================
def get_current_language():
    """
    Retourne la langue actuellement active.
    
    Returns:
        str: Code langue actuel ("es" ou "fr")
        
    Example:
        from translation import get_current_language
        lang = get_current_language()
        print(f"Langue actuelle : {lang}")
    """
    return _translation_manager.get_current_lang()


# ============================================================================
# INITIALISATION
# ============================================================================
if __name__ == "__main__":
    # Test du module
    print("=" * 60)
    print("TEST DU MODULE DE TRADUCTION")
    print("=" * 60)
    
    print("\n1. Test Espagnol (défaut)")
    print(f"   _('Tiempo') = {_('Tiempo')}")
    print(f"   _('Eventos') = {_('Eventos')}")
    print(f"   _('Configuración') = {_('Configuración')}")
    
    print("\n2. Changement vers Français")
    change_language("fr")
    print(f"   _('Tiempo') = {_('Tiempo')}")
    print(f"   _('Eventos') = {_('Eventos')}")
    print(f"   _('Configuración') = {_('Configuración')}")
    
    print("\n3. Retour à l'Espagnol")
    change_language("es")
    print(f"   _('Tiempo') = {_('Tiempo')}")
    print(f"   _('Eventos') = {_('Eventos')}")
    print(f"   _('Configuración') = {_('Configuración')}")
    
    print("\n4. Langue actuelle")
    print(f"   get_current_language() = {get_current_language()}")
    
    print("\n" + "=" * 60)
    print("TEST TERMINÉ")
    print("=" * 60)
