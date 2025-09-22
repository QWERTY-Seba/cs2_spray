from PyQt5 import QtWidgets, QtGui, QtCore
import numpy as np
import cv2

WIDTH, HEIGHT = 300, 300

class OverlayWindow(QtWidgets.QWidget):
    def __init__(self, canvas, position, sensitivity=0.35, invert_y=True, borderless=True):
        super().__init__()
        self.canvas = canvas
        self.position = position  # Lista [x, y]
        self.sensitivity = sensitivity
        self.invert_y = invert_y
        self.grosor_linea = 2
        # Configurar ventana
        if borderless:
            self.set_overlay_flags()
        else:
            self.setWindowTitle("Debug Overlay")  # ventana normal para debug

        self.setFixedSize(WIDTH, HEIGHT)

        # Centrar ventana en pantalla
        self.center_on_screen()

        # Label para mostrar el pixmap
        self.label = QtWidgets.QLabel(self)
        self.pixmap = QtGui.QPixmap(WIDTH, HEIGHT)
        self.pixmap.fill(QtCore.Qt.transparent)
        self.label.setPixmap(self.pixmap)
        self.label.show()

        # Timer para refrescar la ventana
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.refresh)
        self.timer.start(16)  # ~60 FPS

    def set_overlay_flags(self):
        """Configura la ventana para que sea transparente, click-through y sin bordes."""
        self.setWindowFlags(
            QtCore.Qt.WindowStaysOnTopHint |
            QtCore.Qt.FramelessWindowHint |
            QtCore.Qt.Tool
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)

    def center_on_screen(self):
        """Centra el overlay en el monitor principal."""
        screen_geometry = QtWidgets.QApplication.primaryScreen().availableGeometry()
        center_x = screen_geometry.x() + (screen_geometry.width() - WIDTH) // 2
        center_y = screen_geometry.y() + (screen_geometry.height() - HEIGHT) // 2
        self.move(center_x, center_y)

    def refresh(self):
        """Refresca el overlay a partir del canvas RGBA."""
        height, width, channel = self.canvas.shape
        bytes_per_line = channel * width
        image = QtGui.QImage(self.canvas.data, width, height, bytes_per_line, QtGui.QImage.Format_RGBA8888)
        self.pixmap = QtGui.QPixmap.fromImage(image)
        self.label.setPixmap(self.pixmap)
        self.label.update()

    def draw_line_from_delta(self, dx, dy):
        """Dibuja una línea desde la posición actual usando dx/dy."""
        if self.invert_y:
            dy = -dy
        nx = self.position[0] + dx * self.sensitivity
        ny = self.position[1] + dy * self.sensitivity
        nx = max(0, min(WIDTH-1, nx))
        ny = max(0, min(HEIGHT-1, ny))
        cv2.line(self.canvas, (int(self.position[0]), int(self.position[1])), (int(nx), int(ny)), (0,255,0,255), self.grosor_linea)
        self.position[0], self.position[1] = nx, ny

    def reset_position(self):
        """Resetea la posición al centro del overlay."""
        self.position[0] = WIDTH // 2
        self.position[1] = HEIGHT // 2
