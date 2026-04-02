"""Contact screen for video-call initiation.

This module renders contact cards used to request video calls, loading contact
metadata from ``app/contacts/list_contacts.txt`` and matching local contact
images when available.
"""

import os
import unicodedata
import re
from typing import Any, Dict, List
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

from videocall.confirmation_popup import show_call_sent_popup

# ICSO logs
from icso_data.navigation_logger import log_navigation
from icso_data.videocall_logger import log_call_request


# ------------------- Paths -------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMG_DIR = os.path.join(os.path.dirname(BASE_DIR), "images")
CONTACT_DIR = os.path.join(os.path.dirname(BASE_DIR), "contacts")

def img_path(name: str) -> str:
    """Resolve an image file from the shared `images` directory.

    Args:
        name: Image file name (for example, ``"back.png"``).

    Returns:
        Absolute path if the file exists, otherwise an empty string.

    Examples:
        >>> icon = img_path("voice.png")
    """
    p = os.path.join(IMG_DIR, name)
    return p if os.path.exists(p) else ""

def img_contact_path(name: str) -> str:
    """Resolve a contact image file from the `contacts` directory.

    Args:
        name: Contact image file name.

    Returns:
        Absolute path if the file exists, otherwise an empty string.
    """
    p = os.path.join(CONTACT_DIR, name)
    return p if os.path.exists(p) else ""

list_contact_path = os.path.join(CONTACT_DIR, "list_contacts.txt")

# ------------------- Tools -------------------
def normalize_name(name: str) -> str:
    """Normalize display names for deterministic image file lookup.

    The normalization removes diacritics, lowercases the value and strips any
    non alphanumeric character.

    Args:
        name: Raw display name.

    Returns:
        Normalized slug-like string.

    Examples:
        >>> normalize_name("María José")
        'mariajose'
    """
    name = ''.join(
        c for c in unicodedata.normalize('NFD', name)
        if unicodedata.category(c) != 'Mn'
    )
    return re.sub(r'[^a-z0-9]', '', name.lower())

def load_contacts_from_file(file_path: str, default_image: str) -> List[Dict[str, str]]:
    """Load contacts from a key-value text file.

    Expected line format:
    ``DisplayName=username``

    Image resolution strategy:
    1. Normalize ``DisplayName``.
    2. Search for a matching file in supported extensions.
    3. Use ``default_image`` if no image is found.

    Args:
        file_path: Path to the contacts mapping file.
        default_image: Fallback image path used when no specific photo is found.

    Returns:
        A list of dictionaries with keys:
        ``display_name``, ``user_name``, ``image``.

    Raises:
        No exception is propagated. Missing files return an empty list.

    Examples:
        >>> contacts = load_contacts_from_file("list_contacts.txt", "default_user.png")
    """
    contacts: List[Dict[str, str]] = []
    if not os.path.exists(file_path):
        print("[CONTACTS] list_contacts.txt not found")
        return contacts
    
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            if "=" not in line:
                continue
            display_name, user_name = line.strip().split("=", 1)
            display_name = display_name.strip()
            user_name = user_name.strip()
            
            # Search image with multiple supported extensions
            img_base_name = normalize_name(display_name)
            img_path_final = None
            
            # Supported extensions in lookup priority order
            extensions = ['.png', '.jpg', '.jpeg', '.PNG', '.JPG', '.JPEG', '.bmp', '.gif', '.webp']
            
            for ext in extensions:
                test_path = img_contact_path(img_base_name + ext)
                if test_path and os.path.exists(test_path):
                    img_path_final = test_path
                    print(f"[CONTACTS] ✅ Image found: {img_base_name}{ext}")
                    break
            
            # Fallback to default image
            if not img_path_final:
                img_path_final = default_image
                print(f"[CONTACTS] ⚠️ Missing image for '{display_name}', using default image")
            
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
    """Root layout for the contacts screen KV tree."""

    pass

class ContactCard(ButtonBehavior, BoxLayout):
    """Clickable card representing one contact target."""

    def __init__(self, display_name: str, user_name: str, image_source: str, **kwargs: Any) -> None:
        """Initialize a contact card widget.

        Args:
            display_name: Name shown to the user.
            user_name: Backend username used for notification target.
            image_source: Local image path for the contact card.
            **kwargs: Additional Kivy widget keyword arguments.
        """
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
    
    def _update_bg(self, *args: Any) -> None:
        """Keep the rounded background rectangle aligned with widget geometry."""
        self.bg.pos = self.pos
        self.bg.size = self.size
    
    def on_release(self) -> None:
        """Handle contact click by requesting a call and showing confirmation.

        Returns:
            None.

        Raises:
            Any exception raised by downstream notification services can propagate
            if those services do not handle errors internally.
        """
        send_pizarra_notification(self.user_name)
        show_call_sent_popup(contact_name=self.display_name)
        log_navigation("touchscreen", "videocall request")
        log_call_request()
        
        print(f"[CONTACT] 📞 Notification sent to {self.user_name} ({self.display_name})")

class ContactScreen(Screen):
    """Contacts browser used to trigger video-call notifications."""

    def __init__(self, sm: Any, contacts_file: str = list_contact_path, **kwargs: Any) -> None:
        """Initialize contacts screen and schedule UI refresh routines.

        Args:
            sm: Parent Kivy `ScreenManager`.
            contacts_file: Contacts source file path.
            **kwargs: Standard Kivy `Screen` keyword arguments.
        """
        super().__init__(**kwargs)
        self.sm = sm
        self.root_view = Factory.ContactRoot()
        self.add_widget(self.root_view)
        
        # Keep contacts file path for future reloads.
        self.contacts_file = contacts_file
        
        self.default_image = img_contact_path("default_user.png")
        self.contacts = load_contacts_from_file(contacts_file, self.default_image)
        print(f"[ContactScreen] Loaded contacts: {len(self.contacts)}")
        
        Clock.schedule_once(self._populate_contacts, 0.2)
        Clock.schedule_interval(self._refresh_header, 1)
        
        # Update translated labels after UI creation.
        Clock.schedule_once(lambda *_: self.update_labels(), 0.3)
    
    def update_labels(self) -> None:
        """Refresh all translatable labels on the contacts screen."""
        if hasattr(self.root_view, 'ids'):
            ids = self.root_view.ids
            if 'lbl_contacts' in ids:
                ids.lbl_contacts.text = _("Contactos")
        
        self._refresh_header()
    
    def _refresh_header(self, *args: Any) -> None:
        """Refresh translated date/time values shown in the contacts header."""
        now = datetime.now()
        
        # Translated month and day labels.
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
        
        if 'lbl_today' in ids and ids.lbl_today:
            ids.lbl_today.text = f"{days[now.weekday()].capitalize()}, {now.day} {_('de')} {months[now.month-1]}, {now.year}"
    
        if 'lbl_time' in ids and ids.lbl_time:
            ids.lbl_time.text = now.strftime("%H:%M")
    
    def _populate_contacts(self, *args: Any) -> None:
        """Populate the horizontal contact card list from loaded contacts."""
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

    def reload_contacts_from_disk(self) -> None:
        """Reload contacts file and refresh visible cards."""
        self.contacts = load_contacts_from_file(self.contacts_file, self.default_image)
        print(f"[CONTACTS] ✅ Reloaded contacts from disk: {len(self.contacts)}")
        self._populate_contacts()
    
    def on_pre_enter(self, *args: Any) -> None:
        """Kivy hook executed before entering the screen.

        This method refreshes contacts from disk to ensure runtime edits in
        ``list_contacts.txt`` are reflected without restarting the app.
        """
        print("[CONTACTS] 🔄 on_pre_enter: reloading contacts...")
        print("=" * 80)
        print("🔥 ON_PRE_ENTER CALLED")
        print(f"🔍 Current contacts: {len(self.contacts)}")
        print(f"🔍 File: {self.contacts_file}")
        print(f"🔍 File exists? {os.path.exists(self.contacts_file)}")
        print("=" * 80)
        
        self.reload_contacts_from_disk()
        self.update_labels()
