# main.py

import sys
import time
import os
import numpy as np
import cv2  # <--- Nuevo import para OpenCV
from skimage.metrics import structural_similarity as ssim # <--- Para la comparación
from ctypes import wintypes
import ctypes
from PyQt5 import QtWidgets
import threading
from overlay import OverlayWindow 
from mouse import RawMouseListener
from servidor_gsi_arma_uso import GsiHandler
from mask_window import MaskWindow
from crear_archivo_gsi import crear_archivo_gsi
import socketserver
crear_archivo_gsi()


# --- Configuración de la Aplicación ---
WIDTH, HEIGHT = 300, 600
CENTER = (WIDTH // 2, HEIGHT // 2)
RECOIL_PATTERNS_DIR = "recoil_json"
COMPARISON_THRESHOLD_MS = 1000  # N ms: tiempo mínimo para activar la comparación

# --- Variables de Estado Global ---
tracking = False
request_reset = False
current_weapon = "weapon_ak47"
position = list(CENTER)
canvas = np.zeros((HEIGHT, WIDTH, 4), dtype=np.uint8)

# --- Nuevas variables para la comparación ---
recoil_patterns = {}         # Diccionario para guardar las imágenes de patrones
click_start_time = 0         # Para medir la duración del clic

# --- Instancias de la UI ---
app = QtWidgets.QApplication(sys.argv)
overlay = OverlayWindow(canvas, position, sensitivity=0.35, invert_y=False)
 

# --- Nuevas Funciones para Carga y Comparación ---

def load_recoil_patterns():
    """
    Carga todas las imágenes .png de la carpeta de patrones al iniciar.
    """
    if not os.path.exists(RECOIL_PATTERNS_DIR):
        print(f"⚠️  Directorio de patrones no encontrado: '{RECOIL_PATTERNS_DIR}'")
        return
    
    print("🔎 Cargando patrones de recoil...")
    for filename in os.listdir(RECOIL_PATTERNS_DIR):
        if filename.endswith(".png"):
            # Extrae el nombre del arma del nombre del archivo (ej: 'weapon_ak47')
            weapon_name = os.path.splitext(filename)[0]
            try:
                # Carga la imagen en escala de grises
                path = os.path.join(RECOIL_PATTERNS_DIR, filename)
                img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
                if img is not None:
                    recoil_patterns[weapon_name] = img
                    print(f"  ✅ Patrón '{weapon_name}' cargado.")
                else:
                    print(f"  ❌ Error al cargar '{filename}'.")
            except Exception as e:
                print(f"  ❌ Error procesando '{filename}': {e}")
    print("-" * 20)

# --- Funciones de Callback (Slots y Handlers) ---

def on_weapon_changed(weapon_name):
    """Slot que actualiza el arma activa."""
    global current_weapon
    current_weapon = weapon_name
    print(f"🔫 Arma activa actualizada: {current_weapon}")


def handle_mouse_move(dx, dy):
    """Guarda los deltas del ratón y actualiza el overlay."""
    if tracking:
        overlay.draw_line_from_delta(dx, dy)

def handle_left_down():
    """Inicia el tracking y el temporizador."""
    global tracking, request_reset, click_start_time
    if current_weapon:
        tracking = True
        request_reset = True
        click_start_time = time.time() # <-- Inicia el cronómetro
        
        print("Tracking iniciado.")
    else:
        print("⚠️ No hay arma activa detectada.")

mask_win = MaskWindow(title="Spray Collage")
mask_win.show()
mask_windows = []
def handle_left_up():
    """Detiene el tracking, realiza la comparación y resetea variables."""
    global tracking, request_reset
    
    if not tracking:
        return
    
    duration_ms = (time.time() - click_start_time) * 1000

    if duration_ms > COMPARISON_THRESHOLD_MS:
        print(f"\nClick mantenido por {int(duration_ms)} ms. Analizando spray...")

        # Guardar el canvas actual
        overlay.save_canvas()

        if current_weapon in recoil_patterns and overlay.saved_canvas is not None:
            # --- Cargar patrón de recoil con transparencia ---
            pattern_img = cv2.imread(f"{RECOIL_PATTERNS_DIR}/{current_weapon}.png", cv2.IMREAD_UNCHANGED)
            if pattern_img.shape[2] == 4:
                pattern_mask = pattern_img[:, :, 3] > 0
            else:
                pattern_mask = pattern_img[:, :, 0] > 0

            ph, pw = pattern_mask.shape
            ch, cw, _ = overlay.saved_canvas.shape

            # === Origen en el patrón: (pw//2, 0)
            pattern_origin = (pw // 2, 0)

            # === Origen en el canvas del usuario: centro del overlay
            user_origin = (cw // 2, ch // 2)

            # --- Calcular límites necesarios para expandir canvas ---
            min_x = min(-pattern_origin[0], -user_origin[0])
            min_y = min(0, -user_origin[1])  # patrón empieza en Y=0
            max_x = max(pw - pattern_origin[0], cw - user_origin[0])
            max_y = max(ph - pattern_origin[1], ch - user_origin[1])

            # Tamaño del canvas expandido
            canvas_w = max_x - min_x
            canvas_h = max_y - min_y

            # Offset para usuario y patrón dentro del canvas expandido
            user_offset_x = -min_x + (0 - user_origin[0])
            user_offset_y = -min_y + (0 - user_origin[1])
            pattern_offset_x = -min_x + (0 - pattern_origin[0])
            pattern_offset_y = -min_y + (0 - pattern_origin[1])

            # --- Canvas expandido del usuario ---
            expanded_user = np.zeros((canvas_h, canvas_w, 4), dtype=np.uint8)
            expanded_user[user_offset_y:user_offset_y+ch, user_offset_x:user_offset_x+cw] = overlay.saved_canvas
            user_mask = expanded_user[:, :, 3] > 0

            # --- Canvas expandido del patrón ---
            expanded_pattern = np.zeros((canvas_h, canvas_w), dtype=np.uint8)
            expanded_pattern[pattern_offset_y:pattern_offset_y+ph, pattern_offset_x:pattern_offset_x+pw] = pattern_mask.astype(np.uint8)


            # --- Crear máscara RGB ---
            mask_img = np.zeros((canvas_h, canvas_w, 4), dtype=np.uint8)

            # Verde donde coinciden (patrón + usuario)
            mask_img[(expanded_pattern > 0) & (user_mask > 0)] = [0, 255, 0, 255]

            # Rojo donde usuario dibujó pero no hay patrón
            mask_img[(expanded_pattern == 0) & (user_mask > 0)] = [255, 0, 0, 255]

            # Azul donde hay patrón pero el usuario no lo tocó (opcional)
            mask_img[(expanded_pattern > 0) & (user_mask == 0)] = [0, 0, 255, 255]

            # --- Mostrar ventana ---
            mask_win.add_image(mask_img)

        else:
            print("❌ No hay patrón de recoil o canvas guardado.")

    # --- Resetear variables ---
    overlay.canvas[:] = 0
    overlay.position[:] = [WIDTH // 2, HEIGHT // 2]
    overlay.reset_position()
    overlay.refresh()
    tracking = False
    request_reset = False





def iniciar_servidor():
    puerto = 54322
    with socketserver.TCPServer(("", puerto), GsiHandler) as httpd:
        print(f"Servidor GSI escuchando en http://localhost:{puerto}")
        httpd.serve_forever()

# --- Función Principal ---

def main():
    global request_reset, tracking
    
    # 0. Cargar los patrones de recoil al inicio
    load_recoil_patterns()
    
    # 1. Iniciar el servidor GSI
    GsiHandler.callback = on_weapon_changed
    threading.Thread(target=iniciar_servidor, daemon=True).start()
    
    # 2. Iniciar el listener del ratón
    mouse_listener = RawMouseListener(
        on_mouse_move=handle_mouse_move,
        on_left_down=handle_left_down,
        on_left_up=handle_left_up
    )
    mouse_listener.setup()
    
    # 3. Mostrar el overlay
    overlay.show()
    print("Mantén pulsado click izquierdo para controlar el spray.")

    # 4. Bucle principal
    msg = wintypes.MSG()
    user32 = ctypes.windll.user32
    PM_REMOVE = 0x0001
    
    try:
        while overlay.isVisible():
            if user32.PeekMessageA(ctypes.byref(msg), mouse_listener.hwnd, 0, 0, PM_REMOVE):
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageA(ctypes.byref(msg))

            if request_reset:
                # Guardar canvas antes de limpiar si hubo tracking
                canvas[:] = 0
                position[:] = [WIDTH // 2, HEIGHT // 2]
                overlay.reset_position()
                request_reset = False
                overlay.refresh()

            app.processEvents()

    except KeyboardInterrupt:
        print("Saliendo...")
    finally:
        app.quit()

if __name__ == "__main__":
    main()