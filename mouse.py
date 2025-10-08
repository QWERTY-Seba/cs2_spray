# mouse_listener.py

import ctypes
from ctypes import wintypes

# --- Definiciones y estructuras de la API de Windows ---

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Tipos de datos compatibles con 32/64 bits
LRESULT = ctypes.c_longlong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_long
HWND = wintypes.HWND
UINT = wintypes.UINT
WPARAM = ctypes.c_size_t
LPARAM = ctypes.c_ssize_t

# Constantes de la API de Windows
RIDEV_INPUTSINK = 0x00000100
RID_INPUT = 0x10000003
RIM_TYPEMOUSE = 0
WM_INPUT = 0x00FF
WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
RI_MOUSE_LEFT_BUTTON_DOWN = 0x0001
RI_MOUSE_LEFT_BUTTON_UP = 0x0002

WNDPROC = ctypes.WINFUNCTYPE(LRESULT, HWND, UINT, WPARAM, LPARAM)

class WNDCLASS(ctypes.Structure):
    _fields_ = [
        ("style", UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE),
        ("hIcon", HWND), ("hCursor", HWND), ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCSTR), ("lpszClassName", wintypes.LPCSTR)
    ]

class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [
        ("usUsagePage", ctypes.c_ushort), ("usUsage", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong), ("hwndTarget", HWND)
    ]

class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [
        ("dwType", ctypes.c_ulong), ("dwSize", ctypes.c_ulong),
        ("hDevice", HWND), ("wParam", WPARAM)
    ]

class RAWMOUSE_BUTTONS(ctypes.Structure):
    _fields_ = [
        ("usButtonFlags", ctypes.c_ushort), ("usButtonData", ctypes.c_ushort)
    ]

class RAWMOUSE_UNION(ctypes.Union):
    _fields_ = [("ulButtons", ctypes.c_ulong), ("buttons", RAWMOUSE_BUTTONS)]

class RAWMOUSE(ctypes.Structure):
    _fields_ = [
        ("usFlags", ctypes.c_ushort), ("u", RAWMOUSE_UNION),
        ("ulRawButtons", ctypes.c_ulong), ("lLastX", ctypes.c_long),
        ("lLastY", ctypes.c_long), ("ulExtraInformation", ctypes.c_ulong)
    ]

class RAWINPUT(ctypes.Structure):
    _fields_ = [("header", RAWINPUTHEADER), ("data", RAWMOUSE)]

# --- Declaración de prototipos de funciones de la API ---
user32.DefWindowProcW.restype = LRESULT
user32.DefWindowProcW.argtypes = [HWND, UINT, WPARAM, LPARAM]
user32.RegisterClassA.restype = wintypes.ATOM
user32.RegisterClassA.argtypes = [ctypes.POINTER(WNDCLASS)]
user32.CreateWindowExA.restype = HWND
user32.CreateWindowExA.argtypes = [
    wintypes.DWORD, wintypes.LPCSTR, wintypes.LPCSTR, wintypes.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    HWND, HWND, wintypes.HINSTANCE, wintypes.LPVOID
]
user32.RegisterRawInputDevices.restype = wintypes.BOOL
user32.RegisterRawInputDevices.argtypes = [
    ctypes.POINTER(RAWINPUTDEVICE), UINT, ctypes.c_uint
]
user32.GetRawInputData.restype = ctypes.c_uint
user32.GetRawInputData.argtypes = [
    wintypes.HANDLE, ctypes.c_uint, ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_uint), ctypes.c_uint
]
user32.PostQuitMessage.argtypes = [ctypes.c_int]


class RawMouseListener:
    """
    Una clase para capturar deltas de movimiento del ratón (raw input) en Windows.
    
    Utiliza callbacks para notificar al código cliente sobre eventos del ratón.
    """
    def __init__(self, on_mouse_move=None, on_left_down=None, on_left_up=None):
        """
        Inicializa el listener con funciones de callback opcionales.
        
        :param on_mouse_move: Función a llamar en movimiento. Recibe (dx, dy).
        :param on_left_down: Función a llamar cuando se presiona el botón izquierdo.
        :param on_left_up: Función a llamar cuando se suelta el botón izquierdo.
        """
        self.on_mouse_move = on_mouse_move
        self.on_left_down = on_left_down
        self.on_left_up = on_left_up
        
        self.hwnd = None
        # Mantenemos una referencia al WNDPROC para evitar que el recolector de basura lo elimine
        self.wndproc_ptr = WNDPROC(self._wnd_proc)

    def setup(self):
        """Crea la ventana oculta y registra el dispositivo para raw input."""
        self._create_hidden_window()
        self._register_raw_input()

    def _create_hidden_window(self):
        """Crea una ventana invisible para recibir mensajes de Windows."""
        hInstance = kernel32.GetModuleHandleW(None)
        wndClass = WNDCLASS()
        wndClass.lpfnWndProc = self.wndproc_ptr
        wndClass.lpszClassName = b"RawMouseListenerWindow"
        wndClass.hInstance = hInstance

        if not user32.RegisterClassA(ctypes.byref(wndClass)):
            raise ctypes.WinError()

        self.hwnd = user32.CreateWindowExA(
            0, wndClass.lpszClassName, b"HiddenRawInputSink", 0,
            0, 0, 0, 0, 0, 0, hInstance, None
        )
        if not self.hwnd:
            raise ctypes.WinError()

    def _register_raw_input(self):
        """Registra el ratón como un dispositivo de raw input."""
        rid = RAWINPUTDEVICE()
        rid.usUsagePage = 0x01  # Generic Desktop
        rid.usUsage = 0x02      # Mouse
        rid.dwFlags = RIDEV_INPUTSINK
        rid.hwndTarget = self.hwnd
        
        if not user32.RegisterRawInputDevices(ctypes.byref(rid), 1, ctypes.sizeof(rid)):
            raise ctypes.WinError()

    def _wnd_proc(self, hWnd, msg, wParam, lParam):
        """
        Window Procedure: el corazón del listener. Procesa los mensajes de Windows.
        """
        if msg == WM_INPUT:
            hRawInput = wintypes.HANDLE(lParam)
            dwSize = ctypes.c_uint(0)
            
            # Obtener el tamaño del buffer necesario
            user32.GetRawInputData(hRawInput, RID_INPUT, None, ctypes.byref(dwSize), ctypes.sizeof(RAWINPUTHEADER))
            
            if dwSize.value:
                buf = ctypes.create_string_buffer(dwSize.value)
                # Obtener los datos del raw input
                user32.GetRawInputData(hRawInput, RID_INPUT, buf, ctypes.byref(dwSize), ctypes.sizeof(RAWINPUTHEADER))
                raw = ctypes.cast(buf, ctypes.POINTER(RAWINPUT)).contents

                if raw.header.dwType == RIM_TYPEMOUSE:
                    mouse_data = raw.data
                    dx, dy = mouse_data.lLastX, mouse_data.lLastY
                    flags = mouse_data.u.buttons.usButtonFlags
                    
                    # Invocar callbacks según el evento
                    if flags & RI_MOUSE_LEFT_BUTTON_DOWN and self.on_left_down:
                        self.on_left_down()
                        
                    elif flags & RI_MOUSE_LEFT_BUTTON_UP and self.on_left_up:
                        self.on_left_up()
                    
                    if (dx != 0 or dy != 0) and self.on_mouse_move:
                        self.on_mouse_move(dx, dy)
        
        elif msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            
        return user32.DefWindowProcW(hWnd, msg, wParam, lParam)