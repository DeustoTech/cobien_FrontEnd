import os
import requests
import chess
from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.uix.gridlayout import GridLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.graphics import Color, Rectangle

from config_runtime import load_section

class ChessSquare(Button):
    def __init__(self, square_index, is_light, **kwargs):
        super().__init__(**kwargs)
        self.square_index = square_index
        self.is_light = is_light
        self.background_normal = ''
        self.background_down = ''
        self.base_color = (0.9, 0.9, 0.8, 1) if is_light else (0.4, 0.6, 0.4, 1)
        self.background_color = self.base_color
        
        self.piece_image = Image(allow_stretch=True, keep_ratio=True)
        self.add_widget(self.piece_image)
        self.bind(pos=self._update_img, size=self._update_img)

    def _update_img(self, *args):
        self.piece_image.pos = self.pos
        self.piece_image.size = self.size

    def set_piece(self, piece_symbol):
        if not piece_symbol:
            self.piece_image.source = ""
            self.piece_image.opacity = 0
            return
            
        color = 'w' if piece_symbol.isupper() else 'b'
        piece = piece_symbol.upper()
        img_name = f"{color}{piece}.png"
        img_path = os.path.join(os.path.dirname(__file__), "images", img_name)
        if os.path.exists(img_path):
            self.piece_image.source = img_path
            self.piece_image.opacity = 1
        else:
            self.piece_image.source = ""
            self.piece_image.opacity = 0

    def highlight(self, active=True):
        if active:
            self.background_color = (0.8, 0.8, 0.2, 1)
        else:
            self.background_color = self.base_color

class ChessScreen(Screen):
    def __init__(self, sm, **kwargs):
        super().__init__(**kwargs)
        self.sm = sm
        self.board = chess.Board()
        self.selected_square = None
        
        # Load configuration
        services_cfg = load_section("services", {})
        self.backend_base_url = (services_cfg.get("backend_base_url", "") or "http://localhost:8000").strip().rstrip("/")
        
        self.squares = {}
        self.poll_event = None
        
        self._build_ui()

    def _build_ui(self):
        main_layout = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(10))
        
        # Header
        head = BoxLayout(size_hint_y=None, height=dp(60), spacing=dp(10))
        back_btn = Button(text="← Volver", size_hint_x=None, width=dp(120), font_size=dp(20))
        back_btn.bind(on_release=self.go_back)
        self.status_label = Label(text="Cargando partida...", font_size=dp(28), color=(0,0,0,1), bold=True)
        head.add_widget(back_btn)
        head.add_widget(self.status_label)
        main_layout.add_widget(head)
        
        # Board container
        board_container = AnchorLayout(anchor_x='center', anchor_y='center')
        self.grid = GridLayout(cols=8, rows=8, size_hint=(None, None))
        
        # We want the board to be square and fit in the container
        def _update_grid_size(*args):
            s = min(board_container.width, board_container.height) - dp(20)
            self.grid.size = (s, s)
            
        board_container.bind(size=_update_grid_size)
        
        # Draw squares from top-left (a8 to h1)
        for rank in range(7, -1, -1):
            for file in range(8):
                sq_idx = chess.square(file, rank)
                is_light = (rank + file) % 2 != 0
                sq_btn = ChessSquare(sq_idx, is_light)
                sq_btn.bind(on_release=self.on_square_click)
                self.squares[sq_idx] = sq_btn
                self.grid.add_widget(sq_btn)
                
        board_container.add_widget(self.grid)
        main_layout.add_widget(board_container)
        
        with main_layout.canvas.before:
            Color(0.95, 0.95, 0.95, 1)
            self.bg_rect = Rectangle(size=self.size, pos=self.pos)
        self.bind(size=self._update_bg, pos=self._update_bg)
        
        self.add_widget(main_layout)

    def _update_bg(self, *args):
        self.bg_rect.size = self.size
        self.bg_rect.pos = self.pos

    def on_enter(self):
        app = App.get_running_app()
        try:
            self.device_id = app.root.get_screen('main').DEVICE_ID
        except:
            self.device_id = "default_device"
            
        self.poll_state()
        self.poll_event = Clock.schedule_interval(self.poll_state, 2.0)
        self.update_ui()

    def on_leave(self):
        if self.poll_event:
            self.poll_event.cancel()
            self.poll_event = None

    def go_back(self, *args):
        self.sm.current = 'main'

    def update_ui(self):
        # Update pieces
        for sq_idx, sq_btn in self.squares.items():
            piece = self.board.piece_at(sq_idx)
            if piece:
                sq_btn.set_piece(piece.symbol())
            else:
                sq_btn.set_piece(None)
                
            sq_btn.highlight(self.selected_square == sq_idx)
            
        # Update status
        if self.board.is_checkmate():
            self.status_label.text = "¡Jaque Mate!"
        elif self.board.is_game_over():
            self.status_label.text = "Partida Terminada"
        else:
            turn_str = "Blancas" if self.board.turn == chess.WHITE else "Negras"
            self.status_label.text = f"Turno de las {turn_str}"
            if self.board.is_check():
                self.status_label.text += " (Jaque)"

    def on_square_click(self, instance):
        if self.board.is_game_over(): return
        
        if self.selected_square is None:
            # Select
            piece = self.board.piece_at(instance.square_index)
            if piece and piece.color == self.board.turn:
                self.selected_square = instance.square_index
        else:
            # Move
            move = chess.Move(self.selected_square, instance.square_index)
            # handle promotion
            if self.board.piece_at(self.selected_square) and self.board.piece_at(self.selected_square).piece_type == chess.PAWN:
                if chess.square_rank(instance.square_index) in [0, 7]:
                    move = chess.Move(self.selected_square, instance.square_index, promotion=chess.QUEEN)
                    
            if move in self.board.legal_moves:
                self.board.push(move)
                self.selected_square = None
                self.send_move(move.uci())
                self.update_ui()
            else:
                piece = self.board.piece_at(instance.square_index)
                if piece and piece.color == self.board.turn:
                    self.selected_square = instance.square_index
                else:
                    self.selected_square = None
        self.update_ui()

    def poll_state(self, dt=None):
        import threading
        def _poll():
            try:
                url = f"{self.backend_base_url}/pizarra/api/chess/state/{self.device_id}/"
                res = requests.get(url, timeout=3)
                data = res.json()
                if data.get("ok"):
                    fen = data["game"]["fen"]
                    if fen != self.board.fen():
                        def _update(*args):
                            self.board.set_fen(fen)
                            self.update_ui()
                        Clock.schedule_once(_update, 0)
            except Exception as e:
                pass
        threading.Thread(target=_poll, daemon=True).start()

    def send_move(self, move_str):
        import threading
        fen = self.board.fen()
        def _send():
            try:
                url = f"{self.backend_base_url}/pizarra/api/chess/move/{self.device_id}/"
                requests.post(url, json={"fen": fen, "move": move_str}, timeout=3)
            except Exception as e:
                pass
        threading.Thread(target=_send, daemon=True).start()
