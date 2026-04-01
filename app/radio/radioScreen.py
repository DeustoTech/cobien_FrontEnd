from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
import vlc

class RadioScreen(BoxLayout):
    def __init__(self, sm, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.padding = 10
        self.spacing = 10
        self.sm = sm

        self.player = vlc.MediaPlayer()

        btn_back = Button(text="Volver", size_hint=(1, 0.2))
        btn_back.bind(on_press=self.go_back)
        self.add_widget(btn_back)

        ###########
        #
        # LINK TO GET RADIO URLs FROM A FORUM
        #
        # https://www.mundoplus.tv/comunidad/viewtopic.php?t=79165&sid=38033df19e395551fb0b5a4815b1d8b6&start=1005
        #
        ###########
        self.stations = {
            "National Public Radio": "https://npr-ice.streamguys1.com/live.mp3",
            "COPE": "https://flucast-rb01-01.flumotion.com/cope/net1.mp3",
            "Los 40": "https://23543.live.streamtheworld.com/LOS40.mp3",
            "Cadena 100": "https://flucast-rb01-01.flumotion.com/cope/cadena100.mp3",
            "RNE": "http://dispatcher.rndfnk.com/crtve/rne1/main/mp3/high"
        }

        for station_name, station_url in self.stations.items():
            btn_station = Button(text=station_name, size_hint=(1, 0.2))
            btn_station.bind(on_press=lambda instance, url=station_url: self.play_radio(url))
            self.add_widget(btn_station)

    def play_radio(self, url):
        if self.player.is_playing():
            self.player.stop()
        self.player.set_media(vlc.Media(url))
        self.player.play()

    def go_back(self, instance):
        if self.player.is_playing():
            self.player.stop()
        self.sm.current = 'main'