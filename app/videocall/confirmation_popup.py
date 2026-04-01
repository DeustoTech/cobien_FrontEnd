# videocall/confirmation_popup.py
"""
Popup de confirmation après envoi d'une demande d'appel vidéo.

Fermeture possible :
1. Clic sur l'écran (n'importe où)
2. Bouton OK
3. Auto-fermeture après 5 secondes
"""

from kivy.uix.modalview import ModalView
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.clock import Clock
from kivy.metrics import dp, sp
from kivy.graphics import Color, RoundedRectangle, Line
from translation import _


class CallConfirmationPopup(ModalView):
    """
    Popup de confirmation d'envoi de demande d'appel vidéo.
    
    Usage:
        popup = CallConfirmationPopup(contact_name="Mamie")
        popup.open()
    """
    
    def __init__(self, contact_name="", **kwargs):
        # Configuration de base du popup
        super().__init__(
            size_hint=(None, None),
            size=(dp(800), dp(400)),
            auto_dismiss=True,  # ✅ Ferme si clic à l'extérieur
            background='',
            background_color=(0, 0, 0, 0.5),  # Fond semi-transparent
            **kwargs
        )
        
        self.contact_name = contact_name
        
        # ✅ Timer auto-fermeture après 5 secondes
        self.auto_close_timer = None
        
        # Créer le contenu
        self._build_content()
        
        # ✅ Démarrer timer quand popup s'ouvre
        self.bind(on_open=self._start_timer)
        self.bind(on_dismiss=self._cancel_timer)
    
    def _build_content(self):
        """Construit le contenu du popup"""
        
        # Container principal
        container = BoxLayout(
            orientation='vertical',
            padding=dp(40),
            spacing=dp(30)
        )
        
        # ✅ Background blanc avec bordure
        with container.canvas.before:
            Color(1, 1, 1, 1)
            self.bg_rect = RoundedRectangle(
                pos=container.pos,
                size=container.size,
                radius=[dp(24)]
            )
            Color(0, 0, 0, 0.2)
            self.border_line = Line(
                rounded_rectangle=(
                    container.x, container.y,
                    container.width, container.height,
                    dp(24)
                ),
                width=3
            )
        
        container.bind(pos=self._update_bg, size=self._update_bg)
        
        # Spacer du haut
        container.add_widget(BoxLayout(size_hint_y=0.2))
        
        # ✅ Message principal
        message = Label(
            text=_("Notificación enviada"),
            font_size=sp(40),
            bold=True,
            color=(0, 0, 0, 1),
            size_hint_y=None,
            height=dp(50)
        )
        container.add_widget(message)
        
        # ✅ Message secondaire avec nom du contact
        if self.contact_name:
            submessage = Label(
                text=f"{self.contact_name} {_('recibirá tu llamada')}",
                font_size=sp(28),
                color=(0.3, 0.3, 0.3, 1),
                size_hint_y=None,
                height=dp(40)
            )
            container.add_widget(submessage)
        
        # Spacer
        container.add_widget(BoxLayout(size_hint_y=0.3))
        
        # ✅ Bouton OK
        btn_ok = Button(
            text="OK",
            size_hint=(None, None),
            size=(dp(200), dp(70)),
            pos_hint={'center_x': 0.5},
            background_normal='',
            background_color=(0.15, 0.55, 0.95, 1),  # Bleu
            color=(1, 1, 1, 1),
            font_size=sp(32),
            bold=True
        )
        btn_ok.bind(on_release=self._close)
        
        # Wrapper pour centrer le bouton
        btn_wrapper = BoxLayout(size_hint_y=None, height=dp(70))
        btn_wrapper.add_widget(BoxLayout())
        btn_wrapper.add_widget(btn_ok)
        btn_wrapper.add_widget(BoxLayout())
        
        container.add_widget(btn_wrapper)
        
        self.add_widget(container)
    
    def _update_bg(self, instance, value):
        """Met à jour le background quand la taille/position change"""
        self.bg_rect.pos = instance.pos
        self.bg_rect.size = instance.size
        self.border_line.rounded_rectangle = (
            instance.x, instance.y,
            instance.width, instance.height,
            dp(24)
        )
    
    def _start_timer(self, *args):
        """Démarre le timer d'auto-fermeture (5 secondes)"""
        print("[POPUP] ⏱️ Timer auto-fermeture démarré (5s)")
        self.auto_close_timer = Clock.schedule_once(self._auto_close, 5)
    
    def _cancel_timer(self, *args):
        """Annule le timer si popup fermée manuellement"""
        if self.auto_close_timer:
            print("[POPUP] 🛑 Timer annulé")
            self.auto_close_timer.cancel()
            self.auto_close_timer = None
    
    def _auto_close(self, dt):
        """Ferme automatiquement après 5 secondes"""
        print("[POPUP] ⏰ Auto-fermeture (5s écoulées)")
        self.dismiss()
    
    def _close(self, *args):
        """Ferme le popup (bouton OK)"""
        print("[POPUP] ✅ Fermeture manuelle (bouton OK)")
        self.dismiss()


# ==========================================
# FONCTION HELPER POUR USAGE RAPIDE
# ==========================================

def show_call_sent_popup(contact_name=""):
    """
    Affiche le popup de confirmation d'envoi d'appel.
    
    Args:
        contact_name: Nom du contact appelé
    
    Returns:
        Instance du popup (pour tests/debug)
    
    Example:
        show_call_sent_popup("Mamie")
    """
    popup = CallConfirmationPopup(contact_name=contact_name)
    popup.open()
    return popup