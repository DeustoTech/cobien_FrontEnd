import json
import os
import random
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.clock import Clock
from kivy.metrics import dp, sp
from translation import _, get_current_language
from app_config import AppConfig

JOKES_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "jokes")

class JokesScreen(Screen):
    def __init__(self, sm, **kwargs):
        super().__init__(**kwargs)
        self.sm = sm
        self.cfg = AppConfig()
        self.jokes = []
        self.last_joke = None
        
        # Layout principal avec style
        self.layout = BoxLayout(
            orientation='vertical', 
            padding=[dp(40), dp(40), dp(40), dp(40)], 
            spacing=dp(30)
        )
        
        # Conteneur pour le chiste avec fond arrondi
        joke_container = BoxLayout(
            orientation='vertical',
            size_hint_y=0.75,
            padding=dp(30)
        )
        
        # Label pour le titre
        self.title_label = Label(
            text=_("Frase del día"),
            size_hint_y=None,
            height=dp(80),
            font_size=sp(50),
            bold=True,
            color=(0, 0, 0, 1),
            halign='center',
            valign='middle'
        )
        self.title_label.bind(size=self.title_label.setter('text_size'))
        joke_container.add_widget(self.title_label)
        
        # Label para mostrar los chistes
        self.joke_label = Label(
            text=_("Cargando chiste..."),
            size_hint_y=1,
            font_size=sp(35),
            color=(0, 0, 0, 1),
            halign='center',
            valign='middle',
            markup=True
        )
        self.joke_label.bind(size=self.joke_label.setter('text_size'))
        joke_container.add_widget(self.joke_label)
        
        self.layout.add_widget(joke_container)
        
        # Conteneur pour les boutons
        button_container = BoxLayout(
            orientation='horizontal',
            size_hint_y=0.2,
            spacing=dp(20)
        )
        
        # Botón "Otro chiste"
        self.next_button = Button(
            text=_("Otro chiste"),
            background_color=(0.2, 0.6, 1.0, 1),
            font_size=sp(40),
            bold=True
        )
        self.next_button.bind(on_press=lambda x: self.show_random_joke())
        button_container.add_widget(self.next_button)
        
        # Botón "Volver"
        self.back_button = Button(
            text=_("Volver"),
            background_color=(1, 0.3, 0.3, 1),
            font_size=sp(40),
            bold=True
        )
        self.back_button.bind(on_press=self.go_back)
        button_container.add_widget(self.back_button)
        
        self.layout.add_widget(button_container)
        self.add_widget(self.layout)
        
        # Cargar chistes inmediatamente
        self.load_jokes()
        if self.jokes:
            self.show_random_joke()
    
    def load_jokes(self):
        """✅ Load jokes according to language AND category."""
        try:
            # Obtenir langue ACTUELLE
            lang = get_current_language()
            category = self.cfg.data.get("joke_category", "general")
            
            # Déterminer le fichier
            jokes_file = f"jokes_{'fr' if lang == 'fr' else 'es'}.json"
            jokes_path = os.path.join(JOKES_DATA_DIR, jokes_file)
            
            print(f"[JOKES] 📖 Loading: {jokes_file} (lang={lang}, cat={category})")
            
            if not os.path.exists(jokes_path):
                print(f"[JOKES] ❌ File not found: {jokes_path}")
                self.load_jokes_fallback()
                return
            
            with open(jokes_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Charger toutes les catégories si demandé
            if category == "all":
                self.jokes = []
                for cat_jokes in data.values():
                    if isinstance(cat_jokes, list):
                        self.jokes.extend(cat_jokes)
            else:
                # Charger catégorie demandée
                self.jokes = data.get(category, [])
            
            # Fallback if category is empty
            if not self.jokes and category not in ("general", "all"):
                print(f"[JOKES] ⚠️ Category '{category}' empty, fallback 'general'")
                self.jokes = data.get("general", [])
            
            # If still empty, take all jokes
            if not self.jokes:
                print(f"[JOKES] ⚠️ Full load")
                self.jokes = []
                for cat_jokes in data.values():
                    if isinstance(cat_jokes, list):
                        self.jokes.extend(cat_jokes)
            
            # ✅ Normaliser format (support texte et setup/punchline)
            normalized = []
            for joke in self.jokes:
                if isinstance(joke, str):
                    normalized.append(joke.strip())
                elif isinstance(joke, dict):
                    if "text" in joke:
                        normalized.append(str(joke["text"]).strip())
                    elif "setup" in joke and "punchline" in joke:
                        normalized.append(f"{joke['setup'].strip()} — {joke['punchline'].strip()}")
            
            self.jokes = [j for j in normalized if j]
            
            print(f"[JOKES] ✅ {len(self.jokes)} jokes loaded ({lang}, {category})")
        
        except Exception as e:
            print(f"[JOKES] ❌ Error: {e}")
            import traceback
            traceback.print_exc()
            self.load_jokes_fallback()
    
    def load_jokes_fallback(self):
        """Default jokes if loading fails."""
        lang = get_current_language()
        if lang == "fr":
            self.jokes = [
                "Qu'est-ce qu'un jardinier dit à un autre ? On se voit quand on peut.",
                "Pourquoi les oiseaux n'utilisent pas Facebook ? Parce qu'ils ont déjà Twitter.",
                "Quel est le comble pour un électricien ? Que sa femme s'appelle Ampoule."
            ]
        else:
            self.jokes = [
                "¿Qué le dice un jardinero a otro? Nos vemos cuando podamos.",
                "¿Por qué los pájaros no usan Facebook? Porque ya tienen Twitter.",
                "¿Cuál es el colmo de un electricista? Que su mujer se llame Luz."
            ]
    
    def show_random_joke(self):
        """✅ IMPROVED: Show a joke different from the previous one"""
        if not self.jokes:
            self.joke_label.text = _("No hay chistes disponibles")
            return
        
        # ✅ Avoid re-displaying the same joke
        if len(self.jokes) > 1 and self.last_joke:
            available = [j for j in self.jokes if j != self.last_joke]
            if available:
                new_joke = random.choice(available)
            else:
                new_joke = random.choice(self.jokes)
        else:
            new_joke = random.choice(self.jokes)
        
        self.last_joke = new_joke
        self.joke_label.text = new_joke
        print(f"[JOKES] 🎭 Joke displayed: {new_joke[:50]}...")
    
    def update_labels(self):
        """✅ Update labels translations AND reload jokes."""
        print("[JOKES] 🔄 update_labels() called")
        
        # Update the button texts
        self.title_label.text = _("Frase del día")
        self.next_button.text = _("Otro chiste")
        self.back_button.text = _("Volver")
        
        # ✅ RELOAD jokes with the new language/category
        self.load_jokes()
        
        # ✅ Afficher un nouveau chiste
        if self.jokes:
            self.show_random_joke()
        else:
            self.joke_label.text = _("No hay chistes disponibles")
    
    def on_pre_enter(self):
        """✅ Called before showing the screen."""
        print("[JOKES] 📺 on_pre_enter() - Pre-show update")
        self.update_labels()
    
    def go_back(self, instance):
        """Return to the main screen."""
        self.sm.current = 'main'
