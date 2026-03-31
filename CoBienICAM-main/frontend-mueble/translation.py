# translation.py
# Centralized translation module
# ==================================================
# This module exposes a single translation manager instance
# that can be imported and used across the whole application.
# 
# Usage:
#   from translation import _
#   text = _("Bonjour")
#
# To switch language:
#   from translation import change_language
#   change_language("fr")

import gettext
import os
import ast
from typing import Dict


class PoTranslations:
    """Simple `.po`-based fallback translation catalog (no `.mo` required)."""

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
    """Minimal `.po` parser for simple and multiline `msgid`/`msgstr` entries."""
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
    Centralized translation manager.
    Maintains a shared gettext-like translator that can be switched globally.
    """
    
    def __init__(self):
        """Initialize the manager with Spanish as the default language."""
        self._current_lang = "es"
        self._translation = None
        self.load_translation("es")
    
    def load_translation(self, lang):
        """
        Load translations for the given language.
        
        Args:
            lang (str): Language code ("es" or "fr")
        """
        self._current_lang = lang

        localedir = os.path.join(os.path.dirname(__file__), 'locales')
        po_path = os.path.join(localedir, lang, "LC_MESSAGES", "app.po")

        # 1) Preferred path: gettext with compiled app.mo files
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

        # 2) Fallback path: load plain `.po` files with local parser
        try:
            if os.path.exists(po_path):
                catalog = _load_po_catalog(po_path)
                self._translation = PoTranslations(catalog)
                print(f"[TRANSLATION] ✅ Langue chargée depuis PO: {lang}")
                return
        except Exception as e:
            print(f"[TRANSLATION] ⚠️ Erreur fallback PO ({lang}): {e}")

        # 3) Last fallback: identity translation
        print(f"[TRANSLATION] ⚠️ Aucun catalogue disponible pour '{lang}', fallback identity")
        self._translation = gettext.NullTranslations()
    
    def gettext(self, message):
        """
        Translate a message.
        
        Args:
            message (str): Message to translate
            
        Returns:
            str: Translated message
        """
        if self._translation is None:
            return message
        return self._translation.gettext(message)
    
    def get_current_lang(self):
        """
        Return the currently active language code.
        
        Returns:
            str: Current language code ("es" or "fr")
        """
        return self._current_lang


# ============================================================================
# SINGLE SHARED INSTANCE
# ============================================================================
# Shared across the entire application process.
_translation_manager = TranslationManager()


# ============================================================================
# GLOBAL TRANSLATION FUNCTION
# ============================================================================
def _(message):
    """
    Global translation function.
    This helper is intended to be imported and used anywhere.
    
    Args:
        message (str): Message to translate
        
    Returns:
        str: Translated message for the active language
        
    Example:
        from translation import _
        print(_("Bonjour"))  # -> "Hola" when language is "es"
    """
    return _translation_manager.gettext(message)


# ============================================================================
# LANGUAGE SWITCH FUNCTION
# ============================================================================
def change_language(lang):
    """
    Switch language globally for the entire application.
    All subsequent calls to `_()` will use the new language.
    
    Args:
        lang (str): Language code ("es" for Spanish, "fr" for French)
        
    Example:
        from translation import change_language, _
        change_language("fr")
        print(_("Hola"))  # -> "Bonjour"
    """
    _translation_manager.load_translation(lang)
    print(f"[TRANSLATION] 🌍 Langue changée globalement: {lang}")


# ============================================================================
# CURRENT LANGUAGE ACCESSOR
# ============================================================================
def get_current_language():
    """
    Return the currently active language.
    
    Returns:
        str: Current language code ("es" or "fr")
        
    Example:
        from translation import get_current_language
        lang = get_current_language()
        print(f"Current language: {lang}")
    """
    return _translation_manager.get_current_lang()


# ============================================================================
# LOCAL SMOKE TEST
# ============================================================================
if __name__ == "__main__":
    # Module smoke test
    print("=" * 60)
    print("TEST DU MODULE DE TRADUCTION")
    print("=" * 60)
    
    print("\n1. Test Espagnol (défaut)")
    print(f"   _('Tiempo') = {_('Tiempo')}")
    print(f"   _('Eventos') = {_('Eventos')}")
    print(f"   _('Configuración') = {_('Configuración')}")
    
    print("\n2. Switch to French")
    change_language("fr")
    print(f"   _('Tiempo') = {_('Tiempo')}")
    print(f"   _('Eventos') = {_('Eventos')}")
    print(f"   _('Configuración') = {_('Configuración')}")
    
    print("\n3. Switch back to Spanish")
    change_language("es")
    print(f"   _('Tiempo') = {_('Tiempo')}")
    print(f"   _('Eventos') = {_('Eventos')}")
    print(f"   _('Configuración') = {_('Configuración')}")
    
    print("\n4. Current language")
    print(f"   get_current_language() = {get_current_language()}")
    
    print("\n" + "=" * 60)
    print("TEST TERMINÉ")
    print("=" * 60)
