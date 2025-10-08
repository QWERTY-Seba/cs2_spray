import sys
import ctypes
from ctypes import wintypes
from PyQt5 import QtWidgets
from overlay import OverlayWindow
from mouse import RawMouseListener
import numpy as np

# --- Configuración ---
WIDTH, HEIGHT = 300, 600
CENTER = (WIDTH // 2, HEIGHT // 2)
position = list(CENTER)
tracking = False

# --- Instancia de la aplicación ---
app = QtWidgets.QApplication(sys.argv)
overlay = OverlayWindow(canvas=np.zeros((HEIGHT, WIDTH, 4), dtype=np.uint8),
                        position=position,
                        sensitivity=0.4,
                        invert_y=False)

# --- Funciones de callback simplificadas ---

def handle_mouse_move(dx, dy):
    """Dibuja el delta directamente en el overlay."""
    if tracking:
        overlay.draw_line_from_delta(dx, dy)

def handle_left_down():
    """Inicia el tracking."""
    global tracking
    tracking = True

def handle_left_up():
    """Detiene el tracking y limpia el overlay."""
    global tracking
    tracking = False

    # --- Reset del canvas y posición ---
    overlay.canvas[:] = 0  # limpia todo el canvas
    overlay.position[:] = [WIDTH // 2, HEIGHT // 2]
    overlay.reset_position()
    overlay.refresh()

# --- Main simplificado ---

def main():
    global tracking

    # Iniciar listener del mouse
    mouse_listener = RawMouseListener(
        on_mouse_move=handle_mouse_move,
        on_left_down=handle_left_down,
        on_left_up=handle_left_up
    )
    mouse_listener.setup()

    # Mostrar overlay
    overlay.show()

    # Bucle principal Qt + mensajes Windows
    msg = wintypes.MSG()
    user32 = ctypes.windll.user32
    PM_REMOVE = 0x0001

    try:
        while overlay.isVisible():
            if user32.PeekMessageA(ctypes.byref(msg), mouse_listener.hwnd, 0, 0, PM_REMOVE):
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageA(ctypes.byref(msg))
            app.processEvents()
    except KeyboardInterrupt:
        print("Saliendo...")
    finally:
        app.quit()

if __name__ == "__main__":
    main()
