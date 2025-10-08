import os
import cv2
import numpy as np
from PIL import Image, ImageSequence

INPUT_DIR = "./recoils"
OUTPUT_DIR = "./recoil_json"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# parámetros
BACKGROUND_BGR = (32, 20, 22)
TOLERANCE = 40
GREY_DELTA = 25

def remove_background(frame_bgr):
    """Hace transparentes los píxeles cercanos a BACKGROUND_BGR"""
    diff = np.linalg.norm(frame_bgr.astype(np.int16) - np.array(BACKGROUND_BGR, dtype=np.int16), axis=2)
    mask = diff < TOLERANCE
    frame_bgra = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2BGRA)
    frame_bgra[mask, 3] = 0
    return frame_bgra

def remove_text_shadows(frame_bgra):
    """Quita blancos y grises claros (texto + sombra clara)."""
    bgr = cv2.cvtColor(frame_bgra, cv2.COLOR_BGRA2BGR)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)

    lower_white = np.array([0, 0, 180])
    upper_white = np.array([180, 70, 255])
    mask_white = cv2.inRange(hsv, lower_white, upper_white)

    # suavizar la máscara para cubrir sombras pequeñas
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3,3))
    mask_white = cv2.morphologyEx(mask_white, cv2.MORPH_CLOSE, kernel, iterations=1)
    mask_white = cv2.morphologyEx(mask_white, cv2.MORPH_DILATE, kernel, iterations=1)

    frame_bgra[mask_white > 0, 3] = 0
    return frame_bgra

def remove_greys(frame_bgra, delta=GREY_DELTA):
    """Elimina píxeles grisáceos (R≈G≈B)."""
    b, g, r, a = cv2.split(frame_bgra)
    # convertir a int para evitar overflow en la resta
    r_i = r.astype(int); g_i = g.astype(int); b_i = b.astype(int)
    mask_grey = (np.abs(r_i - g_i) < delta) & (np.abs(r_i - b_i) < delta) & (np.abs(g_i - b_i) < delta)
    frame_bgra[mask_grey, 3] = 0
    return frame_bgra

def align_first_row_and_center(frame_bgra, debug=False):
    """
    1) Lleva la primera fila visible a Y=0 (recortando arriba).
    2) Centra esa fila exactamente en el centro horizontal de la imagen final,
       expandiendo el canvas lateralmente si es necesario (sin perder píxeles).
    """
    alpha = frame_bgra[:, :, 3]
    coords = np.argwhere(alpha > 0)
    if coords.size == 0:
        if debug: print("Sin píxeles visibles.")
        return frame_bgra

    y_min = int(coords[:,0].min())

    # 1) Crop vertical: levantar la primera fila a y=0
    cropped = frame_bgra[y_min:, :, :].copy()
    h_c, w_c = cropped.shape[:2]

    # recomputar coordenadas en cropped (ahora la fila superior será y=0)
    coords2 = np.argwhere(cropped[:, :, 3] > 0)
    if coords2.size == 0:
        if debug: print("Después del crop no quedan píxeles visibles.")
        return cropped

    # fila superior en cropped (debería ser 0)
    y0 = int(coords2[:,0].min())  # normalmente 0
    row_coords = coords2[coords2[:,0] == y0]
    x_center_row = int(round(row_coords[:,1].mean()))

    # 2) Calcular dx que coloca ese centro exactamente en el centro final:
    #    dx = w - 2*x_center_row  -> garantiza que en la imagen final el pixel quede en new_w//2
    dx = int(w_c - 2 * x_center_row)

    # calcular nuevo ancho necesario para no perder píxeles
    x_min_new = min(0, dx)
    x_max_new = max(w_c, w_c + dx)
    new_w = int(x_max_new - x_min_new)
    new_h = h_c

    # ajuste de la traslación para las coordenadas del destino (el warpAffine usa coordenadas destino empezando en 0)
    tx = dx - x_min_new
    ty = 0  # ya recortamos verticalmente

    M = np.float32([[1, 0, tx], [0, 1, ty]])
    aligned = cv2.warpAffine(cropped, M, (new_w, new_h),
                             flags=cv2.INTER_NEAREST,
                             borderMode=cv2.BORDER_CONSTANT,
                             borderValue=(0,0,0,0))

    # debug: comprobar posición del primer pixel en la imagen resultante
    if debug:
        coords_dst = np.argwhere(aligned[:, :, 3] > 0)
        if coords_dst.size:
            y_min_dst = int(coords_dst[:,0].min())
            row_dst = coords_dst[coords_dst[:,0] == y_min_dst]
            x_center_dst = int(round(row_dst[:,1].mean()))
            print(f"DEBUG: original y_min={y_min}, x_center_row={x_center_row}, dx={dx}, new_w={new_w}")
            print(f"DEBUG: dst y_min={y_min_dst}  x_center_dst={x_center_dst}  (expected y=0, x={new_w//2})")
    return aligned

def process_gif(path, out_path, debug=False):
    gif = Image.open(path)
    # tomar último frame y convertir a RGBA
    frames = [frame.copy() for frame in ImageSequence.Iterator(gif)]
    last = frames[-1].convert("RGBA")
    arr = np.array(last)  # RGBA numpy (H,W,4) con orden RGBA

    # Convertir RGB->BGR para opencv (sin alpha por ahora)
    rgb = arr[:, :, :3]
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

    # Ignorar 100 pixeles arriba/abajo (si la imagen tiene suficiente altura)
    H, W = bgr.shape[:2]
    if H <= 200:
        cropped_bgr = bgr
    else:
        cropped_bgr = bgr[100:H-100, :]

    frame_bgra = remove_background(cropped_bgr)
    frame_bgra = remove_text_shadows(frame_bgra)
    frame_bgra = remove_greys(frame_bgra)

    aligned = align_first_row_and_center(frame_bgra, debug=debug)

    # Guardar PNG (sobreescribe si existe)
    cv2.imwrite(out_path, aligned)
    if debug:
        print(f"Guardado: {out_path}  -> size={aligned.shape[1]}x{aligned.shape[0]}")

# ---- loop de archivos ----
for file in sorted(os.listdir(INPUT_DIR)):
    if not (file.lower().endswith(".gif") and "(1)" in file):
        continue
    in_path = os.path.join(INPUT_DIR, file)
    out_name = os.path.splitext(file)[0] + ".png"
    out_path = os.path.join(OUTPUT_DIR, out_name)

    # activa debug=True para imprimir coordenadas de verificación
    process_gif(in_path, out_path, debug=True)
