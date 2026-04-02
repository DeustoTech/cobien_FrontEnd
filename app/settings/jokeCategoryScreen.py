from kivy.uix.screenmanager import Screen
from kivy.lang import Builder
from kivy.factory import Factory
from kivy.metrics import dp, sp
from kivy.app import App
from kivy.clock import Clock
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from translation import _, get_current_language

# ✅ Déclarer les classes composites AVANT le KV
class CategoryButton(ButtonBehavior, BoxLayout):
    """Clickable category button"""
    pass

class SettingsButton(ButtonBehavior, BoxLayout):
    """Settings back button"""
    pass

KV = """
#:import dp kivy.metrics.dp
#:import sp kivy.metrics.sp

<CategoryButton>:
    category_id: ""
    category_name: ""
    is_selected: False
    
    padding: dp(20)
    spacing: dp(12)
    canvas.before:
        Color:
            rgba: (0.2, 0.6, 1.0, 1) if self.is_selected else (1, 1, 1, 1)
        RoundedRectangle:
            size: self.size
            pos: self.pos
            radius: [dp(16),]
        Color:
            rgba: 0, 0, 0, 0.28
        Line:
            width: 2.5
            rounded_rectangle: (self.x, self.y, self.width, self.height, dp(16))
    
    Label:
        text: root.category_name
        font_size: sp(40)
        bold: True
        color: (1,1,1,1) if root.is_selected else (0,0,0,1)
        halign: "center"
        valign: "middle"
        text_size: self.size

<JokeCategoryRoot@FloatLayout>:
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
        padding: [0, dp(18), 0, dp(18)]
        spacing: dp(18)

        # Header
        BoxLayout:
            size_hint_y: None
            height: dp(110)
            padding: dp(22), dp(14)
            spacing: dp(18)
            canvas.before:
                Color:
                    rgba: 1,1,1,0.85
                RoundedRectangle:
                    size: self.size
                    pos: self.pos
                    radius: [dp(20),]
            
            Label:
                id: lbl_title
                text: ""
                font_size: sp(60)
                bold: True
                color: 0,0,0,1
                size_hint_x: None
                width: dp(800)
                halign: "left"
                valign: "middle"
                text_size: self.size
            
            Widget:
            
            SettingsButton:
                size_hint_x: None
                width: dp(80)
                padding: dp(6)
                on_release: app.root.current = "settings"
                canvas.before:
                    Color:
                        rgba: 1,1,1,1
                    RoundedRectangle:
                        size: self.size
                        pos: self.pos
                        radius: [dp(16),]
                    Color:
                        rgba: 0,0,0,0.85
                    Line:
                        width: 2
                        rounded_rectangle: (self.x, self.y, self.width, self.height, dp(16))
                Image:
                    source: "data/images/back.png"
                    allow_stretch: True
                    keep_ratio: True

        # Content
        AnchorLayout:
            canvas.before:
                Color:
                    rgba: 1,1,1,0.85
                RoundedRectangle:
                    size: self.size
                    pos: self.pos
                    radius: [dp(20),]
            
            ScrollView:
                size_hint: 0.96, 0.92
                do_scroll_x: False
                bar_width: dp(8)
                
                GridLayout:
                    id: grid_categories
                    cols: 2
                    spacing: dp(20)
                    padding: dp(30)
                    size_hint_y: None
                    height: self.minimum_height
                    row_default_height: dp(120)
                    row_force_default: True
"""

class JokeCategoryScreen(Screen):
    def __init__(self, sm, cfg, **kwargs):
        super().__init__(**kwargs)
        self.sm = sm
        self.cfg = cfg
        
        # ✅ Charger KV une seule fois
        if not hasattr(JokeCategoryScreen, '_kv_loaded'):
            Builder.load_string(KV)
            JokeCategoryScreen._kv_loaded = True
        
        self.root_view = Factory.JokeCategoryRoot()
        self.add_widget(self.root_view)
        
        # ✅ Categories with exact keys matching .po files
        # Format: (technical ID, exact gettext key)
        self.categories = [
            ("all", "Todas las categorías"),
            ("general", "General"),        # ✅ Correspond à msgid "General"
            ("sport", "Deportes"),         # ✅ Correspond à msgid "Deportes"
            ("nature", "Naturaleza"),      # ✅ Correspond à msgid "Naturaleza"
            ("animaux", "Animales"),       # ✅ Correspond à msgid "Animales"
            ("nourriture", "Comida"),      # ✅ Correspond à msgid "Comida"
            ("jeux", "Juegos")             # ✅ Correspond à msgid "Juegos"
        ]
        
        # ✅ Initialize labels and buttons
        Clock.schedule_once(lambda dt: self.update_labels(), 0.1)
    
    def update_labels(self):
        """✅ Update all translations (title + buttons via populate)"""
        print("[JOKE_CATEGORY] 🔄 Updating labels...")
        
        if hasattr(self.root_view, 'ids') and 'lbl_title' in self.root_view.ids:
            # ✅ Page title - Uses "Categoría de Frases"
            # ES: "Categoría de Frases" (Spanish)
            # FR: "Catégorie de Phrases" (French)
            self.root_view.ids.lbl_title.text = _("Categoría de Frases")
        
        # ✅ IMPORTANT: Refresh all category buttons
        self._refresh_all_category_buttons()
        
        print("[JOKE_CATEGORY] ✅ Labels updated")
    
    def _refresh_all_category_buttons(self):
        """Recreate all category buttons with the new translations"""
        print("[JOKE_CATEGORY] 🔄 Refreshing buttons...")
        
        if not hasattr(self.root_view, 'ids') or 'grid_categories' not in self.root_view.ids:
            print("[JOKE_CATEGORY] ⚠️ grid_categories non disponible")
            return
        
        # Recréer tous les boutons avec populate_categories()
        self.populate_categories()
        
        print("[JOKE_CATEGORY] ✅ Buttons refreshed")
    
    def populate_categories(self):
        """✅ Fill the grid with translated buttons (recreates, like NotificationsScreen)"""
        if not hasattr(self.root_view, 'ids') or 'grid_categories' not in self.root_view.ids:
            print("[JOKE_CATEGORY] ⚠️ grid_categories non disponible")
            return
        
        grid = self.root_view.ids.grid_categories
        grid.clear_widgets()
        
        current_category = self.cfg.data.get("joke_category", "general")
        lang = get_current_language()
        
        print(f"[JOKE_CATEGORY] 🌐 Current language: {lang}")
        
        for cat_id, cat_key in self.categories:
            btn = CategoryButton()
            btn.category_id = cat_id
            
            # ✅ Translate with gettext using the exact .po keys
            btn.category_name = _(cat_key)
            
            # 🐛 DEBUG - Show obtained translation
            print(f"[JOKE_CATEGORY] {cat_id}: '{cat_key}' → '{btn.category_name}' (lang={lang})")
            
            btn.is_selected = (cat_id == current_category)
            btn.bind(on_release=lambda x, cid=cat_id: self.select_category(cid))
            grid.add_widget(btn)
        
        print(f"[JOKE_CATEGORY] ✅ {len(self.categories)} buttons created")
    
    def select_category(self, category_id):
        """✅ FIXED: Reload config everywhere before using it"""
        print(f"[JOKE_CATEGORY] 🎯 Category selected: {category_id}")
        
        # 1️⃣ Save to config
        old_category = self.cfg.data.get("joke_category", "general")
        self.cfg.data["joke_category"] = category_id
        self.cfg.save()
        print(f"[JOKE_CATEGORY]    {old_category} → {category_id} (sauvegardé)")
        
        # 2️⃣ ✅ FORCE RELOAD of config in MainScreen
        app = App.get_running_app()
        if hasattr(app, 'main_ref'):
            # ✅ RELOAD the config from disk
            app.main_ref.cfg.load()
            print(f"[JOKE_CATEGORY]    Config rechargée: {app.main_ref.cfg.data.get('joke_category')}")
            
            # ✅ FORCE reload of joke
            if hasattr(app.main_ref, 'reload_joke'):
                app.main_ref.reload_joke()
                print("[JOKE_CATEGORY] ✅ MainScreen rechargé via reload_joke()")
        
        # 3️⃣ Recharger JokesScreen
        if app.root.has_screen("jokes"):
            jokes_screen = app.root.get_screen("jokes")
            if jokes_screen.children:
                jokes_widget = jokes_screen.children[0]
                # ✅ Recharger sa config aussi
                jokes_widget.cfg.load()
                if hasattr(jokes_widget, 'load_jokes'):
                    jokes_widget.load_jokes()
                    if hasattr(jokes_widget, 'show_random_joke'):
                        jokes_widget.show_random_joke()
                    print("[JOKE_CATEGORY] ✅ JokesScreen rechargé")
        
        # 4️⃣ Rafraîchir l'affichage (catégorie en bleu)
        self.populate_categories()
        
        print(f"[JOKE_CATEGORY] ✅ Catégorie changée : {category_id}")
    
    def on_pre_enter(self):
        """✅ Appelé avant d'afficher l'écran - Mise à jour traductions"""
        print("[JOKE_CATEGORY] 📺 on_pre_enter() - Mise à jour traductions")
        self.update_labels()
