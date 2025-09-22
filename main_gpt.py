import ctypes
from ctypes import wintypes
import numpy as np
import cv2
from overlay import OverlayWindow
import sys
from PyQt5 import QtWidgets, QtGui, QtCore



user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# --- Tipos WinAPI (compatible 32/64) ---
if ctypes.sizeof(ctypes.c_void_p) == 8:
    LRESULT = ctypes.c_longlong
else:
    LRESULT = ctypes.c_long

HWND   = wintypes.HWND
UINT   = wintypes.UINT
WPARAM = ctypes.c_size_t
LPARAM = ctypes.c_ssize_t

# --- Constantes ---
RIDEV_INPUTSINK = 0x00000100
RID_INPUT = 0x10000003
RIM_TYPEMOUSE = 0
WM_INPUT = 0x00FF

RI_MOUSE_LEFT_BUTTON_DOWN = 0x0001
RI_MOUSE_LEFT_BUTTON_UP   = 0x0002

MK_LBUTTON = 0x0001     # flag en wParam del header para estado actual del ratón
VK_LBUTTON = 0x01       # código virtual-key para GetAsyncKeyState

WM_DESTROY = 0x0002
WM_CLOSE   = 0x0010
PM_REMOVE  = 0x0001

# --- WNDPROC callback tipo ---
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, HWND, UINT, WPARAM, LPARAM)

# --- Estructuras ---
class WNDCLASS(ctypes.Structure):
    _fields_ = [
        ("style", ctypes.c_uint),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", ctypes.c_void_p),
        ("hIcon", ctypes.c_void_p),
        ("hCursor", ctypes.c_void_p),
        ("hbrBackground", ctypes.c_void_p),
        ("lpszMenuName", ctypes.c_char_p),
        ("lpszClassName", ctypes.c_char_p),
    ]

class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [
        ("usUsagePage", ctypes.c_ushort),
        ("usUsage", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("hwndTarget", ctypes.c_void_p)
    ]

class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [
        ("dwType", ctypes.c_ulong),
        ("dwSize", ctypes.c_ulong),
        ("hDevice", ctypes.c_void_p),
        ("wParam", WPARAM)   # usar WPARAM/size_t para compatibilidad 64-bit
    ]

import ctypes

class RAWMOUSE_BUTTONS(ctypes.Structure):
    _fields_ = [
        ("usButtonFlags", ctypes.c_ushort),
        ("usButtonData", ctypes.c_ushort),
    ]

class RAWMOUSE_UNION(ctypes.Union):
    _fields_ = [
        ("ulButtons", ctypes.c_ulong),
        ("buttons", RAWMOUSE_BUTTONS),
    ]

class RAWMOUSE(ctypes.Structure):
    _fields_ = [
        ("usFlags", ctypes.c_ushort),
        ("u", RAWMOUSE_UNION),
        ("ulRawButtons", ctypes.c_ulong),
        ("lLastX", ctypes.c_long),
        ("lLastY", ctypes.c_long),
        ("ulExtraInformation", ctypes.c_ulong),
    ]


class RAWINPUT(ctypes.Structure):
    _fields_ = [
        ("header", RAWINPUTHEADER),
        ("data", RAWMOUSE)
    ]

# --- Variables globales ---
tracking = False
request_reset = False
WIDTH, HEIGHT = 300, 300
CENTER = (WIDTH // 2, HEIGHT // 2)
sensitivity = 0.2
invert_y = False
position = list(CENTER)
canvas = np.zeros((HEIGHT, WIDTH, 4), dtype=np.uint8)  # RGBA


app = QtWidgets.QApplication(sys.argv)
overlay = OverlayWindow(canvas, position, sensitivity, invert_y)
overlay.show()

# --- Prototipos WinAPI (restype / argtypes) ---
user32.DefWindowProcW.restype = LRESULT
user32.DefWindowProcW.argtypes = [HWND, UINT, WPARAM, LPARAM]

user32.RegisterClassA.restype = wintypes.ATOM
user32.RegisterClassA.argtypes = [ctypes.POINTER(WNDCLASS)]

user32.CreateWindowExA.restype = HWND
user32.CreateWindowExA.argtypes = [
    wintypes.DWORD,     # dwExStyle
    wintypes.LPCSTR,    # lpClassName
    wintypes.LPCSTR,    # lpWindowName
    wintypes.DWORD,     # dwStyle
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,  # x,y,w,h
    HWND, HWND,         # hWndParent, hMenu
    wintypes.HINSTANCE, # hInstance
    wintypes.LPVOID     # lpParam
]

user32.RegisterRawInputDevices.restype = wintypes.BOOL
user32.RegisterRawInputDevices.argtypes = [ctypes.POINTER(RAWINPUTDEVICE),
                                           UINT,
                                           ctypes.c_uint]

user32.GetRawInputData.restype = ctypes.c_uint
user32.GetRawInputData.argtypes = [wintypes.HANDLE, ctypes.c_uint,
                                   ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint),
                                   ctypes.c_uint]

user32.GetAsyncKeyState.restype = ctypes.c_short
user32.GetAsyncKeyState.argtypes = [wintypes.INT]

user32.PeekMessageA.restype = wintypes.BOOL
user32.PeekMessageA.argtypes = [ctypes.POINTER(wintypes.MSG), HWND,
                                wintypes.UINT, wintypes.UINT, wintypes.UINT]

user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.DispatchMessageA.argtypes = [ctypes.POINTER(wintypes.MSG)]

user32.PostQuitMessage.argtypes = [ctypes.c_int]
user32.PostMessageA.argtypes = [HWND, wintypes.UINT, WPARAM, LPARAM]

# --- WindowProc robusto ---
# Constantes para detectar clicks (según MSDN)
RI_MOUSE_LEFT_BUTTON_DOWN = 0x0001
RI_MOUSE_LEFT_BUTTON_UP   = 0x0002

def PyWndProc(hWnd, msg, wParam, lParam):
    global tracking, request_reset, position, canvas

    if msg == WM_INPUT:
        hRawInput = wintypes.HANDLE(lParam)
        dwSize = ctypes.c_uint(0)
        user32.GetRawInputData(hRawInput, RID_INPUT, None, ctypes.byref(dwSize), ctypes.sizeof(RAWINPUTHEADER))
        if dwSize.value:
            buf = ctypes.create_string_buffer(dwSize.value)
            user32.GetRawInputData(hRawInput, RID_INPUT, buf, ctypes.byref(dwSize), ctypes.sizeof(RAWINPUTHEADER))
            raw = ctypes.cast(buf, ctypes.POINTER(RAWINPUT)).contents

            if raw.header.dwType == RIM_TYPEMOUSE:
                flags = raw.data.u.buttons.usButtonFlags
                dx = raw.data.lLastX
                dy = raw.data.lLastY

                # --- Eventos de click (DOWN / UP) ---
                if flags & RI_MOUSE_LEFT_BUTTON_DOWN:
                    tracking = True
                    request_reset = True
                    position[0], position[1] = WIDTH // 2, HEIGHT // 2

                elif flags & RI_MOUSE_LEFT_BUTTON_UP:
                    tracking = False
                    request_reset = True
                    position[0], position[1] = WIDTH // 2, HEIGHT // 2

                # --- Procesar movimiento SOLO si tracking está activo ---
                if tracking and (dx != 0 or dy != 0):
                    overlay.draw_line_from_delta(dx, dy)



    elif msg == WM_DESTROY:
        user32.PostQuitMessage(0)

    return user32.DefWindowProcW(hWnd, msg, wParam, lParam)



# Mantener referencia global del callback (evita GC)
wndproc_ptr = WNDPROC(PyWndProc)

# --- Crear ventana oculta ---
hInstance = kernel32.GetModuleHandleW(None)
wndClass = WNDCLASS()
wndClass.lpfnWndProc = wndproc_ptr
wndClass.lpszClassName = b"RawMouseHidden"
wndClass.hInstance = hInstance

atom = user32.RegisterClassA(ctypes.byref(wndClass))
if not atom:
    raise ctypes.WinError()

hwnd = user32.CreateWindowExA(
    0,
    wndClass.lpszClassName,
    b"RawInputHidden",
    0,
    0, 0, 0, 0,
    0, 0,
    hInstance,
    None
)
if not hwnd:
    raise ctypes.WinError()

# --- Registrar dispositivo raw input ---
rid = RAWINPUTDEVICE()
rid.usUsagePage = 0x01
rid.usUsage = 0x02
rid.dwFlags = RIDEV_INPUTSINK
rid.hwndTarget = hwnd
if not user32.RegisterRawInputDevices(ctypes.byref(rid), 1, ctypes.sizeof(rid)):
    raise ctypes.WinError()

print("Mantén pulsado click izquierdo para dibujar la trayectoria. ESC para salir.")

# --- Loop principal ---
msg = wintypes.MSG()
try:
    while True:
        while user32.PeekMessageA(ctypes.byref(msg), hwnd, 0, 0, PM_REMOVE):
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageA(ctypes.byref(msg))

        if request_reset:
            canvas[:] = 0
            position[:] = CENTER
            request_reset = False
            overlay.refresh()

        QtWidgets.QApplication.processEvents()
except KeyboardInterrupt:  
    user32.PostMessageA(hwnd, WM_CLOSE, 0, 0)
