# videocall/contactScreen.py
import os
import unicodedata
import re
from translation import _
from datetime import datetime
from kivy.uix.screenmanager import Screen
from kivy.lang import Builder
from kivy.clock import Clock
from kivy.factory import Factory
from kivy.metrics import dp, sp
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.graphics import Color, RoundedRectangle
from kivy.uix.behaviors import ButtonBehavior
from kivy.app import App
from videocall.request_call import send_pizarra_notification

# ✅ NOUVEAU : Importer le popup
from videocall.confirmation_popup import show_call_sent_popup

# Logs ICSO
from icso_data.navigation_logger import log_navigation
from icso_data.videocall_logger import log_call_request


# ------------------- Paths -------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMG_DIR = os.path.join(os.path.dirname(BASE_DIR), "images")
CONTACT_DIR = os.path.join(os.path.dirname(BASE_DIR), "contacts")

def img_path(name):
    p = os.path.join(IMG_DIR, name)
    return p if os.path.exists(p) else ""

def img_contact_path(name):
    p = os.path.join(CONTACT_DIR, name)
    return p if os.path.exists(p) else ""

list_contact_path = os.path.join(CONTACT_DIR, "list_contacts.txt")

# ------------------- Tools -------------------
def normalize_name(name):
    name = ''.join(
        c for c in unicodedata.normalize('NFD', name)
        if unicodedata.category(c) != 'Mn'
    )
    return re.sub(r'[^a-z0-9]', '', name.lower())

def load_contacts_from_file(file_path, default_image):
    """
    Format attendu :
    Mamie=iris
    Papa=alexandre
    Jules=jules
    
    ✅ Supporte PNG, JPG, JPEG, BMP, GIF, WebP
    ✅ Cherche d'abord .png, puis .jpg, puis .jpeg, etc.
    """
    contacts = []
    if not os.path.exists(file_path):
        print("Aucun fichier list_contacts.txt")
        return contacts
    
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            if "=" not in line:
                continue
            display_name, user_name = line.strip().split("=", 1)
            display_name = display_name.strip()
            user_name = user_name.strip()
            
            # Chercher l'image avec plusieurs extensions possibles
            img_base_name = normalize_name(display_name)
            img_path_final = None
            
            # Liste des extensions supportées (par ordre de priorité)
            extensions = ['.png', '.jpg', '.jpeg', '.PNG', '.JPG', '.JPEG', '.bmp', '.gif', '.webp']
            
            for ext in extensions:
                test_path = img_contact_path(img_base_name + ext)
                if test_path and os.path.exists(test_path):
                    img_path_final = test_path
                    print(f"[CONTACTS] ✅ Image trouvée: {img_base_name}{ext}")
                    break
            
            # Si aucune image trouvée, utiliser l'image par défaut
            if not img_path_final:
                img_path_final = default_image
                print(f"[CONTACTS] ⚠️ Pas d'image pour '{display_name}', utilisation image par défaut")
            
            contacts.append({
                "display_name": display_name,
                "user_name": user_name,
                "image": img_path_final
            })
    
    return contacts

# ------------------- KV UI -------------------
CONTACT_KV = f"""
#:import dp kivy.metrics.dp
#:import sp kivy.metrics.sp
#:set C_BLACK 0,0,0,1
#:set R_CARD dp(20)
#:set H_HEADER dp(140)
#:set GAP_Y dp(18)

<ContactRoot@FloatLayout>:
    canvas.before:
        Color:
            rgba: 1,1,1,1
        Rectangle:
            pos: self.pos
            size: self.size
            source: app.bg_image if hasattr(app, 'bg_image') and app.has_bg_image else ""
    BoxLayout:
        orientation: "vertical"
        size_hint: 0.94, 0.94
        pos_hint: {{'center_x': .5, 'center_y': .5}}
        padding: [0, GAP_Y, 0, GAP_Y]
        spacing: GAP_Y
        
        # ------ Header ------
        BoxLayout:
            size_hint_y: None
            height: H_HEADER
            padding: dp(22), dp(14)
            spacing: dp(18)
            canvas.before:
                Color:
                    rgba: 1,1,1,0.85
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [R_CARD,]
            Label:
                id: lbl_contacts
                text: "Contacts"
                font_size: sp(65)
                bold: True
                color: C_BLACK
                size_hint_x: None
                width: dp(350)
                halign: "left"
                valign: "middle"
                text_size: self.size
            Label:
                text: "|"
                font_size: sp(65)
                color: C_BLACK
                size_hint_x: None
                width: dp(14)
            BoxLayout:
                orientation: "vertical"
                size_hint_x: None
                width: dp(700)
                Label:
                    id: lbl_today
                    text: ""
                    font_size: sp(36)
                    color: C_BLACK
                    halign: "left"
                    valign: "bottom"
                    text_size: self.size
                Label:
                    id: lbl_time
                    text: ""
                    font_size: sp(28)
                    color: C_BLACK
                    halign: "left"
                    valign: "top"
                    text_size: self.size
            Widget:
            BoxLayout:
                orientation: "horizontal"
                size_hint_x: None
                spacing: dp(12)
                padding: [0, 0, dp(22), 0]
                width: self.minimum_width
                IconBadge:
                    icon_source: "{img_path('back.png')}"
                    on_release: app.root.current = "main"
                IconBadge:
                    icon_source: "{img_path('voice.png')}"
                    on_release: app.start_assistant()
                    #on_release: app.start_voice_command()
        
        # ------ Contacts ------
        ScrollView:
            bar_width: dp(10)
            do_scroll_x: True
            do_scroll_y: False
            BoxLayout:
                id: contacts_row
                orientation: "horizontal"
                spacing: dp(25)
                padding: dp(20), 0
                size_hint_y: None
                height: dp(850)
                size_hint_x: None
                width: self.minimum_width
"""

Builder.load_string(CONTACT_KV)

# ------------------- Widgets -------------------
class ContactRoot(FloatLayout):
    pass

class ContactCard(ButtonBehavior, BoxLayout):
    def __init__(self, display_name, user_name, image_source, **kwargs):
        super().__init__(orientation="vertical",
                         size_hint=(None, None),
                         size=(dp(570), dp(830)),
                         padding=dp(15),
                         spacing=dp(15),
                         **kwargs)
        self.display_name = display_name
        self.user_name = user_name
        
        # Background
        with self.canvas.before:
            Color(1, 1, 1, 0.85)
            self.bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(20)])
        self.bind(pos=self._update_bg, size=self._update_bg)
        
        # Image
        self.add_widget(Image(
            source=image_source,
            size_hint=(1, 0.75),
            allow_stretch=True,
            keep_ratio=True
        ))
        
        # Name
        self.add_widget(Label(
            text=display_name,
            font_size=sp(75),
            color=(0, 0, 0, 1),
            size_hint=(1, 0.25),
            halign="center",
            valign="middle",
            text_size=(None, None),
        ))
    
    def _update_bg(self, *args):
        self.bg.pos = self.pos
        self.bg.size = self.size
    
    def on_release(self):
        """
        ✅ MODIFIÉ : Affiche popup après envoi de la notification
        """
        # 1. Envoyer la notification
        send_pizarra_notification(self.user_name)
        
        # 2. Afficher le popup de confirmation
        show_call_sent_popup(contact_name=self.display_name)

        # 3. Logger la demande d'appel
        log_navigation("touchscreen", "videocall request")
        log_call_request()
        
        print(f"[CONTACT] 📞 Notification envoyée à {self.user_name} ({self.display_name})")

# ------------------- Screen -------------------
class ContactScreen(Screen):
    def __init__(self, sm, contacts_file=list_contact_path, **kwargs):
        super().__init__(**kwargs)
        self.sm = sm
        self.root_view = Factory.ContactRoot()
        self.add_widget(self.root_view)
        
        # ✅ FIX : Sauvegarder le chemin du fichier pour rechargement
        self.contacts_file = contacts_file
        
        self.default_image = img_contact_path("default_user.png")
        self.contacts = load_contacts_from_file(contacts_file, self.default_image)
        print(f"[ContactScreen] {len(self.contacts)} contacts chargés.")
        
        Clock.schedule_once(self._populate_contacts, 0.2)
        Clock.schedule_interval(self._refresh_header, 1)
        
        # ✅ Mettre à jour labels après création UI
        Clock.schedule_once(lambda *_: self.update_labels(), 0.3)
    
    def update_labels(self):
        """✅ Met à jour tous les labels traduits"""
        # Mettre à jour le titre "Contacts"
        if hasattr(self.root_view, 'ids'):
            ids = self.root_view.ids
            if 'lbl_contacts' in ids:
                ids.lbl_contacts.text = _("Contactos")
        
        # Mettre à jour date/heure avec traduction
        self._refresh_header()
    
    def _refresh_header(self, *args):
        """Met à jour date et heure avec traductions"""
        now = datetime.now()
        
        # ✅ Mois et jours traduits (comme dans mainApp.py)
        months = [
            _("enero"), _("febrero"), _("marzo"), _("abril"), _("mayo"), _("junio"),
            _("julio"), _("agosto"), _("septiembre"), _("octubre"), _("noviembre"), _("diciembre")
        ]
        days = [
            _("lunes"), _("martes"), _("miércoles"), _("jueves"), 
            _("viernes"), _("sábado"), _("domingo")
        ]
        
        if not hasattr(self.root_view, 'ids'):
            return
            
        ids = self.root_view.ids
        
        # ✅ Format identique à mainApp.py
        if 'lbl_today' in ids and ids.lbl_today:
            ids.lbl_today.text = f"{days[now.weekday()].capitalize()}, {now.day} {_('de')} {months[now.month-1]}, {now.year}"
    
        if 'lbl_time' in ids and ids.lbl_time:
            ids.lbl_time.text = now.strftime("%H:%M")
    
    def _populate_contacts(self, *args):
        """Remplit la liste des contacts"""
        if not hasattr(self.root_view, 'ids') or 'contacts_row' not in self.root_view.ids:
            return
            
        row = self.root_view.ids["contacts_row"]
        row.clear_widgets()
        for c in self.contacts:
            card = ContactCard(
                display_name=c["display_name"],
                user_name=c["user_name"],
                image_source=c["image"]
            )
            row.add_widget(card)

    def reload_contacts_from_disk(self):
        """Reload contacts file and refresh cards."""
        self.contacts = load_contacts_from_file(self.contacts_file, self.default_image)
        print(f"[CONTACTS] ✅ Reloaded contacts from disk: {len(self.contacts)}")
        self._populate_contacts()
    
    def on_pre_enter(self, *args):
        """✅ Appelé avant d'afficher l'écran - RECHARGE LES CONTACTS"""
        print("[CONTACTS] 🔄 on_pre_enter: rechargement contacts...")
        print("=" * 80)
        print("🔥 ON_PRE_ENTER APPELÉ !!!!")
        print(f"🔍 Contacts actuels: {len(self.contacts)}")
        print(f"🔍 Fichier: {self.contacts_file}")
        print(f"🔍 Fichier existe? {os.path.exists(self.contacts_file)}")
        print("=" * 80)
        
        # Recharger contacts depuis le fichier
        self.reload_contacts_from_disk()

        # Mettre à jour labels traduits
        self.update_labels()
