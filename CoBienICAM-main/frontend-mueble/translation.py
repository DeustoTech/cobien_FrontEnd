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
        
        # Chemin vers le dossier locales
        localedir = os.path.join(os.path.dirname(__file__), 'locales')
        
        try:
            self._translation = gettext.translation(
                'app',
                localedir=localedir,
                languages=[lang],
                fallback=True
            )
            print(f"[TRANSLATION] ✅ Langue chargée: {lang}")
            
            # Test immédiat
            test_text = self._translation.gettext("Tiempo")
            print(f"[TRANSLATION] Test: 'Tiempo' = '{test_text}'")
            
        except Exception as e:
            print(f"[TRANSLATION] ⚠️ Erreur chargement {lang}: {e}")
            print(f"[TRANSLATION] Utilisation fallback")
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