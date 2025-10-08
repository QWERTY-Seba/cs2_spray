# gsi_server.py

import http.server
import socketserver
import json
import threading
from functools import partial
from PyQt5.QtCore import QObject, pyqtSignal

class GsiHandler(http.server.BaseHTTPRequestHandler):

    current_weapon = None
    callback = None

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        try:
            data = json.loads(post_data)
            active_weapon_name = None
            
            # Navega por el JSON para encontrar el arma activa
            if data and "player" in data:
                for weapon in data["player"].get("weapons", {}).values():
                    if weapon.get("state") == "active":
                        active_weapon_name = weapon.get("name")
                        break
            
            # Si el arma cambió, notifica a la instancia principal del servidor
            if active_weapon_name and active_weapon_name != GsiHandler.current_weapon:
                GsiHandler.callback(active_weapon_name)
                GsiHandler.current_weapon = active_weapon_name

        except (json.JSONDecodeError, KeyError):
            # Ignora errores si el JSON es inválido o no tiene la estructura esperada
            pass

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        # Suprime los logs de la consola para mantenerla limpia
        pass



