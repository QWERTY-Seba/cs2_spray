import json
import math
import os
import cv2
import numpy as np
from PIL import Image

# Ajustes de tamaño de contornos
MIN_W, MAX_W = 6, 12
MIN_H, MAX_H = 6, 12
IGNORE_BORDER = 100  # opcional, ajustar si quieres ignorar bordes

BACKGROUND_BGR = (32, 20, 22)
BG_TOLERANCE = 3

def dist(p1, p2):
    return ((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)**0.5

def remove_duplicates_keep_first(points):
    seen = set()
    filtered = []
    for pt in points:
        if pt not in seen:
            seen.add(pt)
            filtered.append(pt)
    return filtered


def extract_points_with_roi(gif_path):
    gif = Image.open(gif_path)
    frame_idx = 0
    points = []
    prev_bgr = None
    width, height = gif.size

    lower_bg = np.array([BACKGROUND_BGR[0]-BG_TOLERANCE,
                         BACKGROUND_BGR[1]-BG_TOLERANCE,
                         BACKGROUND_BGR[2]-BG_TOLERANCE], dtype=np.uint8)
    upper_bg = np.array([BACKGROUND_BGR[0]+BG_TOLERANCE,
                         BACKGROUND_BGR[1]+BG_TOLERANCE,
                         BACKGROUND_BGR[2]+BG_TOLERANCE], dtype=np.uint8)

    try:
        while True:
            frame = np.array(gif.convert("RGB"))
            bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

            # máscara ROI
            roi_mask = np.zeros((height, width), dtype=np.uint8)
            roi_mask[IGNORE_BORDER:height-IGNORE_BORDER, :] = 255

            if frame_idx == 0:
                # Primer frame: todo lo que no sea fondo
                mask_bg = cv2.inRange(bgr, lower_bg, upper_bg)
                mask = cv2.bitwise_not(mask_bg)
                
                # Aplicar blur y threshold para reforzar contornos
                mask = cv2.GaussianBlur(mask, (3,3), 0)
                _, mask = cv2.threshold(mask, 10, 255, cv2.THRESH_BINARY)
                
                mask = cv2.bitwise_and(mask, roi_mask)

            else:
                # Frames siguientes: diferencia con frame anterior
                diff = cv2.absdiff(bgr, prev_bgr)
                gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
                _, mask_diff = cv2.threshold(gray_diff, 25, 255, cv2.THRESH_BINARY)
                mask = cv2.bitwise_and(mask_diff, roi_mask)

            # encontrar contornos
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            frame_pts = []
            for cnt in contours:
                x, y, w, h = cv2.boundingRect(cnt)
                if MIN_W <= w <= MAX_W and MIN_H <= h <= MAX_H:
                    M = cv2.moments(cnt)
                    if M["m00"] > 0:
                        cx = int(M["m10"] / M["m00"])
                        cy = int(M["m01"] / M["m00"])
                        frame_pts.append((cx, cy))

            if frame_pts:
                selected = frame_pts[0]
            else:
                # fallback: centro del frame
                selected = (width//2, height//2)
            points.append(selected)


            prev_bgr = bgr.copy()
            frame_idx += 1
            gif.seek(frame_idx)

    except EOFError:
        pass
    points = remove_duplicates_keep_first(points)
    print(f"Se detectaron {len(points)} puntos", gif_path)

    # Normalizar
    if points:
        x0, y0 = points[0]
        normalized = [(x - x0, -(y - y0)) for x, y in points]
    else:
        normalized = []

    # Guardar en JSON
    output_dir = "recoil_json"
    os.makedirs(output_dir, exist_ok=True)
    weapon_name = os.path.splitext(os.path.basename(gif_path))[0]
    json_path = os.path.join(output_dir, f"{weapon_name}.json")
    with open(json_path, "w") as f:
        json.dump(normalized, f, indent=4)

    print(f"[OK] Recoil normalizado guardado en {json_path}")
    return points, normalized


def show_points(points, size):
    width, height = size
    canvas = np.ones((height, width, 3), dtype=np.uint8) * 255
    for i, (x, y) in enumerate(points, 1):
        cv2.circle(canvas, (x, y), 4, (0, 0, 255), -1)
        cv2.putText(canvas, str(i), (x+6, y-6), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0,0,0), 1, cv2.LINE_AA)
    cv2.imshow("Recoil Pattern", canvas)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

# Uso
for archivo in os.listdir("recoils"):
    GIF_PATH = os.path.join("recoils", archivo)
    points, normalized_points = extract_points_with_roi(GIF_PATH)
    
    show_points(points, (600,600))
    

