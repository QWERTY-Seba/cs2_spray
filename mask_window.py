from PyQt5 import QtWidgets, QtGui, QtCore
import collections

class MaskWindow(QtWidgets.QWidget):
    MAX_IMAGES = 5
    TARGET_WIDTH = 150
    TARGET_HEIGHT = 200

    def __init__(self, title="Mask Collage"):
        super().__init__()
        self.setWindowTitle(title)
        self.set_overlay_flags()

        # Layout horizontal
        self.layout = QtWidgets.QHBoxLayout()
        self.layout.setContentsMargins(5, 5, 5, 5)
        self.layout.setSpacing(10)
        self.setLayout(self.layout)

        # Deque para mantener labels
        self.image_labels = collections.deque(maxlen=self.MAX_IMAGES)

        # Colocar en esquina inferior derecha
        screen = QtWidgets.QApplication.primaryScreen().geometry()
        self.move(screen.right() - (self.TARGET_WIDTH * self.MAX_IMAGES + 50),
                  screen.bottom() - (self.TARGET_HEIGHT + 50))
    
    def set_overlay_flags(self):
        """Configura la ventana para overlay transparente."""
        self.setWindowFlags(
            QtCore.Qt.WindowStaysOnTopHint |
            QtCore.Qt.FramelessWindowHint |
            QtCore.Qt.Tool |
            QtCore.Qt.WindowDoesNotAcceptFocus |
            QtCore.Qt.WindowTransparentForInput
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating)

    def add_image(self, img):
        h, w, _ = img.shape
        qimg = QtGui.QImage(img.data, w, h, 4 * w, QtGui.QImage.Format_RGBA8888)
        pixmap = QtGui.QPixmap.fromImage(qimg)

        # Redimensionar
        pixmap = pixmap.scaled(self.TARGET_WIDTH, self.TARGET_HEIGHT, QtCore.Qt.KeepAspectRatio,
                               QtCore.Qt.SmoothTransformation)

        # Crear un nuevo QLabel
        label = QtWidgets.QLabel()
        label.setPixmap(pixmap)

        # Si ya tenemos MAX_IMAGES, sacar el más viejo del layout
        if len(self.image_labels) == self.MAX_IMAGES:
            old_label = self.image_labels.popleft()
            self.layout.removeWidget(old_label)
            old_label.deleteLater()

        # Insertar el nuevo label
        self.image_labels.append(label)
        self.layout.addWidget(label)
