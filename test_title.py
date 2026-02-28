import sys
from PyQt6.QtWidgets import QApplication, QVBoxLayout, QWidget, QLabel
from qframelesswindow import FramelessWindow
from qfluentwidgets import setTheme, Theme

class TestWindow(FramelessWindow):
    def __init__(self):
        super().__init__()
        setTheme(Theme.DARK)
        self.resize(600, 400)
        self.setStyleSheet("TestWindow { background: #1a1a1a; }")

        layout = QVBoxLayout(self)
        # titlebar height is usually handled by FramelessWindow implicitly 
        layout.setContentsMargins(0, 40, 0, 0)
        layout.addWidget(QLabel("Hello Dark Title Bar", self, styleSheet="color: white;"))

        # Try to use standard titlebar 
        from qfluentwidgets import MSFluentTitleBar
        self.setTitleBar(MSFluentTitleBar(self))
        # self.titleBar.titleLabel.setStyleSheet("color: white;")  <-- StandardTitleBar has a titleLabel

if __name__ == '__main__':
    app = QApplication(sys.argv)
    w = TestWindow()
    w.show()
    sys.exit(app.exec())
