from kivy.uix.screenmanager import Screen
from kivy.lang import Builder
from kivy.factory import Factory
from kivy.properties import StringProperty, BooleanProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.button import Button
from kivy.graphics import Color, RoundedRectangle, Line
from kivy.metrics import dp, sp
from kivy.app import App
from translation import _, change_language, get_current_language


# ----------------- WIDGETS RÉUTILISABLES -----------------

class IconBadge(ButtonBehavior, AnchorLayout):
    icon_source = StringProperty("")

Factory.register("IconBadge", cls=IconBadge)

# ----------------- KV LAYOUT -----------------

KV = """
#:import dp kivy.metrics.dp
#:import sp kivy.metrics.sp

#:set C_BLACK 0,0,0,1
#:set C_BORDER 0,0,0,0.85
#:set R_CARD dp(20)
#:set R_BTN dp(16)
#:set H_HEADER dp(110)
#:set GAP_Y dp(18)

<IconBadge>:
    size_hint: None, None
    size: dp(80), dp(80)
    padding: dp(6)
    canvas.before:
        Color:
            rgba: 1,1,1,1
        RoundedRectangle:
            size: self.size
            pos: self.pos
            radius: [R_BTN,]
        Color:
            rgba: C_BORDER
        Line:
            width: 2
            rounded_rectangle: (self.x, self.y, self.width, self.height, R_BTN)
    Image:
        source: root.icon_source
        allow_stretch: True
        keep_ratio: True
        mipmap: True
        size_hint: None, None
        size: dp(56), dp(56)

<LanguageRoot@FloatLayout>:
    parent_screen: None
    canvas.before:
        Color:
            rgba: 1,1,1,1
        Rectangle:
            size: self.size
            pos: self.pos
            source: app.bg_image if app.has_bg_image else ""

    BoxLayout:
        orientation: "vertical"
        size_hint: 0.94, 0.94
        pos_hint: {"center_x": 0.5, "center_y": 0.5}
        padding: [0, GAP_Y, 0, GAP_Y]
        spacing: GAP_Y

        # ---------- CABECERA ----------
        BoxLayout:
            size_hint_y: None
            height: H_HEADER
            padding: dp(22), dp(14)
            spacing: dp(18)
            canvas.before:
                Color:
                    rgba: 1,1,1,0.85
                RoundedRectangle:
                    size: self.size
                    pos: self.pos
                    radius: [R_CARD,]

            Label:
                id: lbl_title
                text: ""
                font_size: sp(40)
                bold: True
                color: C_BLACK
                size_hint_x: None
                width: dp(700)
                halign: "left"
                valign: "middle"
                text_size: self.size

            Widget:

            BoxLayout:
                orientation: "horizontal"
                size_hint_x: None
                width: self.minimum_width
                spacing: dp(6)
                padding: [0, 0, dp(10), 0]
                IconBadge:
                    icon_source: app.back_icon if hasattr(app, 'back_icon') and app.back_icon else "images/back.png"
                    on_release: root.parent_screen.go_back() if root.parent_screen else None

        # ---------- CONTENIDO PRINCIPAL ----------
        AnchorLayout:
            size_hint: 1, 1
            canvas.before:
                Color:
                    rgba: 1,1,1,0.85
                RoundedRectangle:
                    size: self.size
                    pos: self.pos
                    radius: [R_CARD,]

            BoxLayout:
                orientation: "vertical"
                size_hint: 0.96, 0.90
                spacing: dp(30)
                padding: dp(40)

                Widget:
                    size_hint_y: 0.3

                # ---------- BOTÓN FRANÇAIS ----------
                Button:
                    id: btn_french
                    text: "Français"
                    font_size: sp(32)
                    size_hint_y: None
                    height: dp(120)
                    background_color: 0,0,0,0
                    canvas.before:
                        Color:
                            rgba: (0.15, 0.55, 0.95, 1) if root.parent_screen and root.parent_screen.selected_lang == "fr" else (1, 1, 1, 1)
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [dp(16),]
                        Color:
                            rgba: 0,0,0,0.85
                        Line:
                            width: 3
                            rounded_rectangle: (self.x, self.y, self.width, self.height, dp(16))
                    color: (1, 1, 1, 1) if root.parent_screen and root.parent_screen.selected_lang == "fr" else C_BLACK
                    on_release: root.parent_screen.select_language("fr") if root.parent_screen else None

                Widget:
                    size_hint_y: 0.1

                # ---------- BOTÓN ESPAÑOL ----------
                Button:
                    id: btn_spanish
                    text: "Español"
                    font_size: sp(32)
                    size_hint_y: None
                    height: dp(120)
                    background_color: 0,0,0,0
                    canvas.before:
                        Color:
                            rgba: (0.15, 0.55, 0.95, 1) if root.parent_screen and root.parent_screen.selected_lang == "es" else (1, 1, 1, 1)
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [dp(16),]
                        Color:
                            rgba: 0,0,0,0.85
                        Line:
                            width: 3
                            rounded_rectangle: (self.x, self.y, self.width, self.height, dp(16))
                    color: (1, 1, 1, 1) if root.parent_screen and root.parent_screen.selected_lang == "es" else C_BLACK
                    on_release: root.parent_screen.select_language("es") if root.parent_screen else None

                Widget:
                    size_hint_y: 0.3

                # ---------- BOTÓN GUARDAR ----------
                Button:
                    id: btn_save
                    text: ""
                    font_size: sp(24)
                    size_hint_y: None
                    height: dp(70)
                    background_color: 0,0,0,0
                    canvas.before:
                        Color:
                            rgba: 0.2, 0.7, 0.2, 1
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [dp(12),]
                    on_release: root.parent_screen.on_save() if root.parent_screen else None

                Widget:
                    size_hint_y: 0.3
"""

Builder.load_string(KV)

# ----------------- SCREEN PRINCIPALE -----------------

class LanguageScreen(Screen):
    selected_lang = StringProperty("es")
    
    def __init__(self, sm, cfg, **kwargs):
        super().__init__(**kwargs)
        self.sm = sm
        self.cfg = cfg

        # -------- Traduction --------
        app = App.get_running_app()
        lang = app.cfg.data.get("language", "es")
        self.selected_lang = lang

        self.root_view = Factory.LanguageRoot()
        self.root_view.parent_screen = self
        self.add_widget(self.root_view)

        # Mettre à jour les labels
        self.update_labels()

    def go_back(self):
        """Retour à l'écran settings"""
        self.sm.current = "settings"

    def select_language(self, lang):
        """Sélectionne une langue"""
        self.selected_lang = lang
        # Forcer le rafraîchissement visuel
        self.root_view.property('parent_screen').dispatch(self.root_view)

    def on_save(self):
        """Sauvegarde la langue sélectionnée et recharge l'interface"""
        print(f"[LANGUAGE] 💾 Sauvegarde langue: {self.selected_lang}")
        
        # 1. Get the app
        app = App.get_running_app()
        
        # 2. Save to config
        app.cfg.data["language"] = self.selected_lang
        app.cfg.save()
        
        # 3. ✅ Changer langue via module centralisé
        change_language(self.selected_lang)
        
        # 4. Test immédiat
        print(f"[LANGUAGE] Test: _('Tiempo') = {_('Tiempo')}")
        
        # 5. Recharger interface
        if hasattr(app, "reset_assistant"):
            app.reset_assistant()
        app.reload_main_screen()
        
        # 6. Mettre à jour cet écran
        self.update_labels()
        
        print(f"[LANGUAGE] ✅ Langue appliquée: {self.selected_lang}")


    def update_labels(self):
        """Met à jour les labels avec les traductions"""
        if not hasattr(self.root_view, 'ids'):
            return
        
        self.root_view.ids.lbl_title.text = _("Configuración de Idioma")
        self.root_view.ids.btn_save.text = _("Guardar Configuración")

        print(f"[LANGUAGE] Labels mis à jour: '{_('Configuración de Idioma')}'")

    def on_pre_enter(self, *args):
        """Mise à jour avant d'entrer dans l'écran"""
        app = App.get_running_app()
        lang = app.cfg.data.get("language", "es")
        self.selected_lang = lang
        
        # Mettre à jour les labels
        self.update_labels()

Factory.register("LanguageScreen", cls=LanguageScreen)
