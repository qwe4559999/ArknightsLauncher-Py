import sys
import os
import json
import shutil
import logging
import psutil
import subprocess
import ctypes
import tempfile
import urllib.request
import re
from packaging.version import Version

from PyQt6.QtCore import Qt, QSize, QTimer, QVariantAnimation, QRect, QThread, pyqtSignal
from PyQt6.QtGui import QIcon, QFont, QPixmap, QPainter, QColor, QPen
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QToolButton, QPushButton,
    QFileDialog, QFrame, QGraphicsDropShadowEffect, QSizePolicy, QSystemTrayIcon, QMenu,
    QProgressBar, QDialog
)
from qfluentwidgets import (
    SubtitleLabel, setTheme, Theme,
    BodyLabel, PushButton, FluentIcon,
    MessageBox, InfoBar, InfoBarPosition, LineEdit, ToolButton,
    ComboBox, MessageBoxBase,
    TransparentToolButton, MSFluentTitleBar, ToolTipFilter, ToolTipPosition
)
from qframelesswindow import FramelessWindow

# PyInstaller 兼容性获取路径基准
if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_PATH = os.path.join(os.getenv('APPDATA'), 'ArknightsLauncher_v2', 'config.json')
ACCOUNTS_DIR = os.path.join(os.getenv('APPDATA'), 'ArknightsLauncher_v2', 'AccountBackups')

OFFICIAL_ICON = os.path.join(BASE_DIR, 'resources', 'Icons', 'official.ico')
BSERVER_ICON = os.path.join(BASE_DIR, 'resources', 'Icons', 'bserver.ico')
MAA_ICON = os.path.join(BASE_DIR, 'resources', 'Icons', 'MAA.ico')

VERSION = 'v1.2.0'
GITHUB_REPO = 'qwe4559999/ArknightsLauncher-Py'
GITHUB_API_URL = f'https://api.github.com/repos/{GITHUB_REPO}/releases/latest'

# ================= 日志系统 =================
LOG_DIR = os.path.join(os.getenv('APPDATA'), 'ArknightsLauncher_v2')
os.makedirs(LOG_DIR, exist_ok=True)
LOG_PATH = os.path.join(LOG_DIR, 'launcher.log')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_PATH, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('ArknightsLauncher')

# ================= 自动更新组件 =================
class UpdateChecker(QThread):
    """后台线程检查 GitHub Releases 最新版本"""
    update_available = pyqtSignal(str, str, str)  # (new_version, changelog, download_url)
    
    def run(self):
        try:
            req = urllib.request.Request(GITHUB_API_URL, headers={'Accept': 'application/vnd.github.v3+json', 'User-Agent': 'ArknightsLauncher'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))
            
            remote_tag = data.get('tag_name', '')
            if not remote_tag:
                return
            
            # 版本比较 (去掉 v 前缀)
            local_ver = Version(VERSION.lstrip('v'))
            remote_ver = Version(remote_tag.lstrip('v'))
            
            if remote_ver > local_ver:
                changelog = data.get('body', '') or '无更新日志'
                # 查找 .exe 下载链接
                download_url = ''
                for asset in data.get('assets', []):
                    if asset['name'].lower().endswith('.exe'):
                        download_url = asset['browser_download_url']
                        break
                if not download_url:
                    download_url = data.get('html_url', '')
                
                self.update_available.emit(remote_tag, changelog, download_url)
            else:
                logger.info(f'已是最新版本 {VERSION}')
        except Exception as e:
            logger.warning(f'检查更新失败: {e}')


class UpdateDownloadDialog(QDialog):
    """下载进度对话框"""
    def __init__(self, download_url, new_version, parent=None):
        super().__init__(parent)
        self.download_url = download_url
        self.new_version = new_version
        self.setWindowTitle(f'正在下载 {new_version}')
        self.setFixedSize(420, 130)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        
        self.label = QLabel(f'正在下载 {new_version} ...', self)
        self.label.setStyleSheet('font-size: 14px;')
        layout.addWidget(self.label)
        
        self.progressBar = QProgressBar(self)
        self.progressBar.setRange(0, 100)
        self.progressBar.setValue(0)
        layout.addWidget(self.progressBar)
        
        self.download_thread = DownloadThread(download_url)
        self.download_thread.progress.connect(self.on_progress)
        self.download_thread.finished_path.connect(self.on_finished)
        self.download_thread.error.connect(self.on_error)
        self.download_thread.start()
        
        self.downloaded_path = None
    
    def on_progress(self, percent):
        self.progressBar.setValue(percent)
    
    def on_finished(self, path):
        self.downloaded_path = path
        self.label.setText('下载完成！即将重启启动器...')
        self.progressBar.setValue(100)
        QTimer.singleShot(800, self.accept)
    
    def on_error(self, msg):
        self.label.setText(f'下载失败: {msg}')
        self.progressBar.setRange(0, 100)
        self.progressBar.setValue(0)
    
    def closeEvent(self, e):
        if self.download_thread.isRunning():
            self.download_thread.terminate()
        super().closeEvent(e)


class DownloadThread(QThread):
    """后台下载线程"""
    progress = pyqtSignal(int)
    finished_path = pyqtSignal(str)
    error = pyqtSignal(str)
    
    def __init__(self, url):
        super().__init__()
        self.url = url
    
    def run(self):
        try:
            req = urllib.request.Request(self.url, headers={'User-Agent': 'ArknightsLauncher'})
            with urllib.request.urlopen(req, timeout=60) as resp:
                total = int(resp.headers.get('Content-Length', 0))
                
                # 下载到临时目录
                tmp_dir = os.path.join(tempfile.gettempdir(), 'ArknightsLauncher_update')
                os.makedirs(tmp_dir, exist_ok=True)
                tmp_path = os.path.join(tmp_dir, 'ArknightsLauncher_new.exe')
                
                downloaded = 0
                block_size = 8192
                with open(tmp_path, 'wb') as f:
                    while True:
                        chunk = resp.read(block_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            self.progress.emit(int(downloaded * 100 / total))
            
            self.finished_path.emit(tmp_path)
        except Exception as e:
            self.error.emit(str(e))


# ================= 颜色插值工具 =================
def lerp_color(c1: QColor, c2: QColor, t: float) -> QColor:
    """线性插值两个 QColor，t 从 0.0 到 1.0"""
    return QColor(
        int(c1.red()   + (c2.red()   - c1.red())   * t),
        int(c1.green() + (c2.green() - c1.green()) * t),
        int(c1.blue()  + (c2.blue()  - c1.blue())  * t),
        int(c1.alpha() + (c2.alpha() - c1.alpha()) * t),
    )

# ================= 自定义动画组件 =================
class AnimatedServerButton(QToolButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_active = False
        self.is_hover = False
        
        self.anim = QVariantAnimation(self)
        self.anim.setDuration(250)
        self.anim.valueChanged.connect(self.update)
        
        self.current_val = 0.0
        
        self.start_border = QColor(255, 255, 255, 0)
        self.start_bg = QColor(255, 255, 255, 0)
        self.end_border = QColor(255, 255, 255, 0)
        self.end_bg = QColor(255, 255, 255, 0)

        self.setStyleSheet("QToolButton { background: transparent; border: none; outline: none; }")

    def set_active(self, active):
        if self.is_active == active: return
        self.is_active = active
        self._start_anim()

    def enterEvent(self, e):
        super().enterEvent(e)
        self.is_hover = True
        self._start_anim()

    def leaveEvent(self, e):
        super().leaveEvent(e)
        self.is_hover = False
        self._start_anim()

    def mousePressEvent(self, e):
        super().mousePressEvent(e)
        self.update()

    def mouseReleaseEvent(self, e):
        super().mouseReleaseEvent(e)
        self.update()

    def _start_anim(self):
        cur_val = self.anim.currentValue() if self.anim.state() == QVariantAnimation.State.Running else self.current_val
        if cur_val is None: cur_val = 1.0

        self.start_bg = lerp_color(self.start_bg, self.end_bg, cur_val)
        self.start_border = lerp_color(self.start_border, self.end_border, cur_val)
        
        if self.is_active:
            self.end_bg = QColor(255, 255, 255, 25)
            self.end_border = QColor(255, 255, 255, 255)
        elif self.is_hover:
            self.end_bg = QColor(255, 255, 255, 10)
            self.end_border = QColor(160, 160, 160, 255)
        else:
            self.end_bg = QColor(255, 255, 255, 0)
            self.end_border = QColor(255, 255, 255, 0)

        self.anim.stop()
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.start()

    def paintEvent(self, e):
        val = self.anim.currentValue() if self.anim.state() == QVariantAnimation.State.Running else 1.0
        self.current_val = val
        if val is None: val = 1.0

        bg = lerp_color(self.start_bg, self.end_bg, val)
        bc = lerp_color(self.start_border, self.end_border, val)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen = QPen(bc)
        pen.setWidth(2)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        rect = self.rect().adjusted(1, 1, -1, -1)
        
        painter.setPen(pen)
        painter.setBrush(bg)
        painter.drawRoundedRect(rect, 12, 12)

        icon = self.icon()
        if not icon.isNull():
            icon_size = self.iconSize()
            icon_rect = QRect(
                (self.width() - icon_size.width()) // 2,
                (self.height() - icon_size.height()) // 2,
                icon_size.width(),
                icon_size.height()
            )
            icon.paint(painter, icon_rect)


class AnimatedStartButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.is_hover = False
        self.is_pressed = False
        
        self.anim = QVariantAnimation(self)
        self.anim.setDuration(200)
        self.anim.valueChanged.connect(self.update)
        self.current_val = 0.0
        
        self.base_color = QColor(0, 152, 234, 255)
        self.hover_color = QColor(51, 161, 244, 255)
        self.press_color = QColor(0, 123, 191, 255)
        self.start_bg = QColor(0, 152, 234, 255)
        self.end_bg = QColor(0, 152, 234, 255)

        self.setStyleSheet("QPushButton { background-color: transparent; border: none; outline: none; }")

    def enterEvent(self, e):
        super().enterEvent(e)
        self.is_hover = True
        self._start_anim()

    def leaveEvent(self, e):
        super().leaveEvent(e)
        self.is_hover = False
        self._start_anim()

    def mousePressEvent(self, e):
        super().mousePressEvent(e)
        self.is_pressed = True
        self._start_anim()

    def mouseReleaseEvent(self, e):
        super().mouseReleaseEvent(e)
        self.is_pressed = False
        self._start_anim()

    def _start_anim(self):
        cur_val = self.anim.currentValue() if self.anim.state() == QVariantAnimation.State.Running else self.current_val
        if cur_val is None: cur_val = 1.0
        
        self.start_bg = lerp_color(self.start_bg, self.end_bg, cur_val)

        if self.is_pressed:
            self.end_bg = self.press_color
        elif self.is_hover:
            self.end_bg = self.hover_color
        else:
            self.end_bg = self.base_color

        self.anim.stop()
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.start()

    def paintEvent(self, e):
        val = self.anim.currentValue() if self.anim.state() == QVariantAnimation.State.Running else 1.0
        self.current_val = val
        if val is None: val = 1.0

        bg = lerp_color(self.start_bg, self.end_bg, val)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg)
        rect = self.rect()
        painter.drawRoundedRect(rect, 12, 12)

        painter.setPen(QColor(255, 255, 255, 255))
        painter.setFont(self.font())
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.text())

    def set_server_theme(self, server):
        """切换服务器主题色"""
        if server == 'official':
            self.base_color = QColor(0, 152, 234, 255)
            self.hover_color = QColor(51, 161, 244, 255)
            self.press_color = QColor(0, 123, 191, 255)
            self.setText(' 启动官服  START')
        else:
            self.base_color = QColor(240, 116, 130, 255)
            self.hover_color = QColor(251, 143, 155, 255)
            self.press_color = QColor(210, 90, 105, 255)
            self.setText(' 启动B服  START')
        self.start_bg = self.base_color
        self.end_bg = self.base_color
        self.update()

class InputDialog(MessageBoxBase):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel("保存账号配置", self)
        self.lineEdit = LineEdit(self)
        self.lineEdit.setPlaceholderText("请输入备注名 (例如：官服-大号)")
        self.lineEdit.setClearButtonEnabled(True)

        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.lineEdit)
        self.widget.setMinimumWidth(300)
        self.viewLayout.setContentsMargins(24, 24, 24, 24)
        self.viewLayout.setSpacing(12)

    def getText(self):
        return self.lineEdit.text().strip()

def load_config():
    if not os.path.exists(os.path.dirname(CONFIG_PATH)):
        os.makedirs(os.path.dirname(CONFIG_PATH))
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {'game_path': '', 'maa_path': ''}

def save_config(config):
    if not os.path.exists(os.path.dirname(CONFIG_PATH)):
        os.makedirs(os.path.dirname(CONFIG_PATH))
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=4)


class SettingsDialog(MessageBoxBase):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.titleLabel = SubtitleLabel("启动器设置", self)
        
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addSpacing(10)
        
        # 游戏路径设置
        self.viewLayout.addWidget(BodyLabel("客户端根目录 (Game Path):", self))
        self.gameRow = QHBoxLayout()
        self.gameInput = LineEdit(self)
        self.gameInput.setText(self.config.get('game_path', ''))
        self.gameInput.setReadOnly(True)
        self.gameBtn = PushButton("浏览", self)
        self.gameBtn.clicked.connect(self.choose_game_path)
        self.gameRow.addWidget(self.gameInput)
        self.gameRow.addWidget(self.gameBtn)
        self.viewLayout.addLayout(self.gameRow)
        
        self.viewLayout.addSpacing(10)
        
        # MAA 路径设置
        self.viewLayout.addWidget(BodyLabel("MAA 核心文件 (MAA.exe):", self))
        self.maaRow = QHBoxLayout()
        self.maaInput = LineEdit(self)
        self.maaInput.setText(self.config.get('maa_path', ''))
        self.maaInput.setReadOnly(True)
        self.maaBtn = PushButton("浏览", self)
        self.maaBtn.clicked.connect(self.choose_maa_path)
        self.maaRow.addWidget(self.maaInput)
        self.maaRow.addWidget(self.maaBtn)
        self.viewLayout.addLayout(self.maaRow)
        
        self.viewLayout.addSpacing(10)
        
        # 背景图设置
        self.viewLayout.addWidget(BodyLabel("自定义启动器背景图:", self))
        self.bgRow = QHBoxLayout()
        self.bgInput = LineEdit(self)
        self.bgInput.setText(self.config.get('bg_path', os.path.join(BASE_DIR, 'resources', 'bg.png')))
        self.bgInput.setReadOnly(True)
        self.bgBtn = PushButton("浏览", self)
        self.bgBtn.clicked.connect(self.choose_bg_path)
        self.bgRow.addWidget(self.bgInput)
        self.bgRow.addWidget(self.bgBtn)
        self.viewLayout.addLayout(self.bgRow)
        
        self.widget.setMinimumWidth(450)
        self.viewLayout.setContentsMargins(24, 24, 24, 24)

    def choose_game_path(self):
        d = QFileDialog.getExistingDirectory(self, "请选择 明日方舟 游戏根目录", self.gameInput.text())
        if d: self.gameInput.setText(d)
        
    def choose_maa_path(self):
        f, _ = QFileDialog.getOpenFileName(self, "请选择 MAA.exe", self.maaInput.text(), "Executable (*.exe)")
        if f: self.maaInput.setText(f)
        
    def choose_bg_path(self):
        f, _ = QFileDialog.getOpenFileName(self, "选择自定义背景图", self.bgInput.text(), "Images (*.png *.jpg *.jpeg)")
        if f: self.bgInput.setText(f)

    def get_result(self):
        return {
            'game_path': self.gameInput.text(),
            'maa_path': self.maaInput.text(),
            'bg_path': self.bgInput.text()
        }

class ModernArknightsLauncher(FramelessWindow):
    def __init__(self):
        super().__init__()
        self.config = load_config()
        self._config_dirty = False
        self.initUI()
        self.initWindow()
        
        # 在界面初始化完成后检查是否需要首次配置指南
        QTimer.singleShot(100, self.check_first_run)
        # 后台检查更新
        QTimer.singleShot(2000, self._check_for_updates)
        
    def check_first_run(self):
        """ 检查是否是首次运行，如果是则强制要求设置游戏路径 """
        game_path = self.config.get('game_path', '')
        if not game_path or not os.path.exists(game_path):
            msgBox = MessageBox('欢迎使用', '检测到您可能是首次使用本启动器，或游戏路径配置已失效。\n请先设置「明日方舟」的客户端根目录以继续。', self)
            if msgBox.exec():
                self.on_settings_clicked()

    def initWindow(self):
        self.setWindowTitle('Arknights Launcher - Modern Edition')
        self.resize(900, 550)
        self.setWindowIcon(QIcon(OFFICIAL_ICON))

        # 自定义暗色无边框标题栏
        self.setTitleBar(MSFluentTitleBar(self))

        # 系统托盘图标
        self.trayIcon = QSystemTrayIcon(QIcon(OFFICIAL_ICON), self)
        trayMenu = QMenu()
        trayMenu.addAction("显示主窗口", self.showNormal)
        trayMenu.addAction("退出启动器", self.quit_app)
        self.trayIcon.setContextMenu(trayMenu)
        self.trayIcon.activated.connect(self.on_tray_activated)
        self.trayIcon.show()

        # 强制暗黑流利风格
        setTheme(Theme.DARK)
        self.update_background()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        # 当窗口改变大小时，同步拉伸右侧内部的顶部抗反光层
        if hasattr(self, 'titleShadow') and hasattr(self, 'rightContent'):
            self.titleShadow.setGeometry(0, 0, self.rightContent.width(), 60)

    def update_background(self):
        bg_path = self.config.get('bg_path', os.path.join(BASE_DIR, 'resources', 'bg.png'))
        bg_url = bg_path.replace("\\", "/") if os.path.exists(bg_path) else "none"
        bg_css = f"border-image: url({bg_url}) 0 0 0 0 stretch stretch;" if bg_url != "none" else ""

        if os.path.exists(bg_path):
            pixmap = QPixmap(bg_path)
            if not pixmap.isNull():
                ratio = pixmap.width() / pixmap.height()
                target_height = 550
                # 取消了外边距，所以右侧宽度 = 总宽 - 边栏宽
                total_width = int(target_height * ratio) + 80
                total_width = max(900, min(total_width, 1600))
                self.resize(total_width, target_height)

        self.setStyleSheet(f"""
            ModernArknightsLauncher {{
                background-color: transparent;
            }}
            #NavBar {{
                background-color: #1a1a1a;
                border-top-left-radius: 12px;
                border-bottom-left-radius: 12px;
            }}
            #RightContent {{
                {bg_css}
                background-color: #2b2b2b;
                border-top-right-radius: 12px;
                border-bottom-right-radius: 12px;
            }}
            #TitleShadow {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(0, 0, 0, 0.7), stop:1 rgba(0, 0, 0, 0));
                border-top-right-radius: 12px;
            }}
            #WatermarkLabel {{
                color: rgba(255, 255, 255, 0.05);
                font-size: 80px;
                font-weight: bold;
                background: transparent;
            }}
            #InfoPanel {{
                border-radius: 12px;
            }}
        """)

    def initUI(self):
        # 去除所有外边距，让 NavBar 和 RightContent 充满窗口
        self.mainLayout = QHBoxLayout(self)
        self.mainLayout.setContentsMargins(0, 0, 0, 0)
        self.mainLayout.setSpacing(0)

        # ----------------- 独立左侧黑色导航栏 -----------------
        self.navBar = QFrame(self)
        self.navBar.setObjectName("NavBar")
        self.navBar.setFixedWidth(80)
        self.navLayout = QVBoxLayout(self.navBar)
        self.navLayout.setContentsMargins(0, 30, 0, 16)
        
        # 官服 / B服 切换按钮（带边框高亮动效）
        self.btnOff = AnimatedServerButton(self.navBar)
        self.btnOff.setIcon(QIcon(OFFICIAL_ICON))
        self.btnOff.setIconSize(QSize(46, 46))
        self.btnOff.setFixedSize(60, 60)
        self.btnOff.setToolTip("明日方舟（官服）")
        self.btnOff.installEventFilter(ToolTipFilter(self.btnOff, 500, ToolTipPosition.RIGHT))
        self.btnOff.clicked.connect(lambda: self.on_server_switched('official'))

        self.btnBili = AnimatedServerButton(self.navBar)
        self.btnBili.setIcon(QIcon(BSERVER_ICON))
        self.btnBili.setIconSize(QSize(46, 46))
        self.btnBili.setFixedSize(60, 60)
        self.btnBili.setToolTip("明日方舟（B服）")
        self.btnBili.installEventFilter(ToolTipFilter(self.btnBili, 500, ToolTipPosition.RIGHT))
        self.btnBili.clicked.connect(lambda: self.on_server_switched('bilibili'))

        self.navLayout.addWidget(self.btnOff, 0, Qt.AlignmentFlag.AlignHCenter)
        self.navLayout.addSpacing(16)
        self.navLayout.addWidget(self.btnBili, 0, Qt.AlignmentFlag.AlignHCenter)
        
        self.navLayout.addStretch()

        # 底部分隔线
        self.navSep = QFrame(self.navBar)
        self.navSep.setFrameShape(QFrame.Shape.HLine)
        self.navSep.setStyleSheet("background-color: rgba(255,255,255,0.06); max-height: 1px; border: none;")
        self.navSep.setFixedWidth(48)
        self.navLayout.addWidget(self.navSep, 0, Qt.AlignmentFlag.AlignHCenter)
        self.navLayout.addSpacing(8)

        # 底部设置按钮
        self.btnSettings = TransparentToolButton(FluentIcon.SETTING, self)
        self.btnSettings.setFixedSize(40, 40)
        self.btnSettings.setIconSize(QSize(18, 18))
        self.btnSettings.setToolTip("全局设置")
        self.btnSettings.clicked.connect(self.on_settings_clicked)
        self.navLayout.addWidget(self.btnSettings, 0, Qt.AlignmentFlag.AlignHCenter)
        self.navLayout.addSpacing(2)

        self.btnAbout = TransparentToolButton(FluentIcon.INFO, self)
        self.btnAbout.setFixedSize(40, 40)
        self.btnAbout.setIconSize(QSize(18, 18))
        self.btnAbout.setToolTip("关于启动器")
        self.btnAbout.clicked.connect(self.on_about_clicked)
        self.navLayout.addWidget(self.btnAbout, 0, Qt.AlignmentFlag.AlignHCenter)

        self.mainLayout.addWidget(self.navBar)

        # ----------------- 右侧主视窗 (承载壁纸) -----------------
        self.rightContent = QFrame(self)
        self.rightContent.setObjectName("RightContent")
        self.rightLayout = QVBoxLayout(self.rightContent)
        self.rightLayout.setContentsMargins(0, 0, 0, 0)
        self.rightLayout.setSpacing(0)
        
        # 顶部防反光层 (绝对布局以悬浮在背景上)
        self.titleShadow = QFrame(self.rightContent)
        self.titleShadow.setObjectName("TitleShadow")
        self.titleShadow.setGeometry(0, 0, 2000, 60)
        self.titleShadow.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        
        self.contentArea = QVBoxLayout()
        self.contentArea.setContentsMargins(30, 10, 30, 30)
        self.contentArea.addStretch(1)
        
        # 水印
        self.watermarkLayout = QHBoxLayout()
        self.watermark = QLabel("RHODES ISLAND", self)
        self.watermark.setObjectName("WatermarkLabel")
        self.watermarkLayout.addStretch(1)
        self.watermarkLayout.addWidget(self.watermark)
        self.watermarkLayout.addStretch(1)
        self.contentArea.addLayout(self.watermarkLayout)
        self.contentArea.addStretch(1)

        # 底部组件 (右侧对齐的垂直统排面板)
        self.bottomLayout = QHBoxLayout()
        self.bottomLayout.addStretch(1)  # 左侧留空，把所有东西推到右边

        self.rightPlayLayout = QVBoxLayout()
        self.rightPlayLayout.setSpacing(10)

        # 悬浮工具与账号信息面板
        self.infoPanel = QFrame()
        self.infoPanel.setObjectName("InfoPanel")
        self.infoPanel.setFixedWidth(380)
        self.infoPanel.setStyleSheet("QFrame#InfoPanel { background-color: rgba(30,30,30,0.85); border-radius: 12px; border: 1px solid rgba(255,255,255,0.1); }")
        
        self.infoLayout = QVBoxLayout(self.infoPanel)
        self.infoLayout.setContentsMargins(20, 20, 20, 20)
        self.infoLayout.setSpacing(12)

        # 0. 服务器指示标签
        self.serverLabel = QLabel("▶ 官方服务器", self)
        self.serverLabel.setStyleSheet("color: #0098EA; font-weight: bold; font-size: 14px; background: transparent;")
        self.infoLayout.addWidget(self.serverLabel)

        # 1. 账号模块布局
        self.accRow = QHBoxLayout()
        self.accLabel = QLabel("游戏账号", self)
        self.accLabel.setStyleSheet("color: #cccccc; font-weight: bold; font-size: 13px; background: transparent;")
        
        self.accountCombo = ComboBox(self)
        self.accountCombo.setMinimumWidth(160)
        self.accountCombo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        
        self.saveAccBtn = ToolButton(FluentIcon.SAVE, self)
        self.saveAccBtn.setToolTip("保存当前状态为新账号")
        self.saveAccBtn.clicked.connect(self.on_save_account)
        
        self.delAccBtn = ToolButton(FluentIcon.DELETE, self)
        self.delAccBtn.setToolTip("删除选中的账号预设")
        self.delAccBtn.clicked.connect(self.on_delete_account)
        
        self.accRow.addWidget(self.accLabel)
        self.accRow.addStretch(1)
        self.accRow.addWidget(self.accountCombo)
        self.accRow.addWidget(self.saveAccBtn)
        self.accRow.addWidget(self.delAccBtn)
        self.infoLayout.addLayout(self.accRow)

        # 账号操作提示
        self.accHint = QLabel("选中的账号将在启动时自动应用", self)
        self.accHint.setStyleSheet("color: rgba(255,255,255,0.3); font-size: 11px; background: transparent;")
        self.infoLayout.addWidget(self.accHint)

        # 分隔线
        self.separator1 = QFrame(self)
        self.separator1.setFrameShape(QFrame.Shape.HLine)
        self.separator1.setStyleSheet("background-color: rgba(255,255,255,0.08); max-height: 1px; border: none;")
        self.infoLayout.addWidget(self.separator1)

        # 2. 工具模块布局
        self.toolsRow = QHBoxLayout()
        self.maaBtn = PushButton('启动 MAA', self, FluentIcon.ROBOT)
        self.maaBtn.clicked.connect(self.on_maa_clicked)
        self.fixBtn = PushButton('修复清理', self, FluentIcon.SYNC)
        self.fixBtn.clicked.connect(self.on_fix_clicked)
        self.toolsRow.addWidget(self.maaBtn)
        self.toolsRow.addWidget(self.fixBtn)
        self.infoLayout.addLayout(self.toolsRow)

        # 版本号
        self.versionLabel = QLabel(VERSION, self)
        self.versionLabel.setStyleSheet("color: rgba(255,255,255,0.2); font-size: 10px; background: transparent;")
        self.versionLabel.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.infoLayout.addWidget(self.versionLabel)

        # --- 巨型启动按钮（带悬浮色变动画）---
        self.startBtn = AnimatedStartButton(' 启动游戏  START', self)
        self.startBtn.setFixedSize(380, 80)
        self.startBtn.setFont(QFont("Microsoft YaHei", 20, QFont.Weight.Bold))
        self.startBtn.clicked.connect(self.on_start_game)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 5)
        self.startBtn.setGraphicsEffect(shadow)

        # 将综合面板和启动按钮加入右侧竖向布局
        self.rightPlayLayout.addWidget(self.infoPanel, 0, Qt.AlignmentFlag.AlignRight)
        self.rightPlayLayout.addWidget(self.startBtn, 0, Qt.AlignmentFlag.AlignRight)

        self.bottomLayout.addLayout(self.rightPlayLayout)
        self.contentArea.addLayout(self.bottomLayout)
        self.rightLayout.addLayout(self.contentArea)
        
        self.mainLayout.addWidget(self.rightContent)

        # 恢复上次选择的服务器
        saved_server = self.config.get('last_server', 'official')
        self.current_server = saved_server
        self.on_server_switched(saved_server)

        self.titleBar.raise_()

    def on_server_switched(self, routeKey):
        self.current_server = routeKey
        self._config_dirty = True
        self.config['last_server'] = routeKey

        if routeKey == 'official':
            self.btnOff.set_active(True)
            self.btnBili.set_active(False)
            self.serverLabel.setText("▶ 官方服务器")
            self.serverLabel.setStyleSheet("color: #0098EA; font-weight: bold; font-size: 14px; background: transparent;")
        else:
            self.btnOff.set_active(False)
            self.btnBili.set_active(True)
            self.serverLabel.setText("▶ Bilibili 服务器")
            self.serverLabel.setStyleSheet("color: #F07482; font-weight: bold; font-size: 14px; background: transparent;")

        self.startBtn.set_server_theme(routeKey)
        self.refresh_accounts_list()

    # ================= 功能逻辑 =================
    
    def refresh_accounts_list(self):
        self.accountCombo.clear()
        self.accountCombo.addItem("默认 (不覆盖)")
        if not os.path.exists(ACCOUNTS_DIR):
            os.makedirs(ACCOUNTS_DIR)
        for item in os.listdir(ACCOUNTS_DIR):
            acc_path = os.path.join(ACCOUNTS_DIR, item)
            if os.path.isdir(acc_path):
                # 按服务器归属过滤账号
                meta_file = os.path.join(acc_path, 'meta.json')
                if os.path.exists(meta_file):
                    try:
                        with open(meta_file, 'r', encoding='utf-8') as f:
                            meta = json.load(f)
                        if meta.get('server') and meta['server'] != self.current_server:
                            continue
                    except Exception:
                        pass
                self.accountCombo.addItem(item)
                
    def on_save_account(self):
        game_path = self.config.get('game_path', '')
        if not game_path or not os.path.exists(game_path):
            InfoBar.error('未配置!', '请先点击左下角设置游戏根目录。', position=InfoBarPosition.TOP, parent=self)
            return
            
        dialog = InputDialog(self)
        if dialog.exec():
            acc_name = dialog.getText()
            if not acc_name:
                InfoBar.error('错误', '账号名不能为空', position=InfoBarPosition.TOP, parent=self)
                return
                
            acc_save_path = os.path.join(ACCOUNTS_DIR, acc_name)
            if os.path.exists(acc_save_path):
                msg_box = MessageBox('覆盖确认', f'账号 "{acc_name}" 已经存在，是否要覆盖？', self)
                if not msg_box.exec():
                    return
                shutil.rmtree(acc_save_path, ignore_errors=True)
                
            os.makedirs(acc_save_path, exist_ok=True)

            # 保存服务器归属元数据
            with open(os.path.join(acc_save_path, 'meta.json'), 'w', encoding='utf-8') as f:
                json.dump({'server': self.current_server}, f, ensure_ascii=False)

            u8_data = os.path.join(game_path, "U8Data")
            if os.path.exists(u8_data):
                self.copy_tree_overwrite(u8_data, os.path.join(acc_save_path, "U8Data"))
                
            sdk_data = os.path.join(game_path, "sdkdata")
            if os.path.exists(sdk_data):
                self.copy_tree_overwrite(sdk_data, os.path.join(acc_save_path, "sdkdata"))
            
            self.refresh_accounts_list()
            self.accountCombo.setCurrentText(acc_name)
            InfoBar.success('成功', f'当前登录账状态已保存为：{acc_name}', position=InfoBarPosition.TOP, parent=self)

    def on_delete_account(self):
        selected_acc = self.accountCombo.currentText()
        if not selected_acc or selected_acc == "默认 (不覆盖)":
            InfoBar.warning('无法删除', '请先选择一个已保存的账号预设。', position=InfoBarPosition.TOP, parent=self)
            return
        
        msg_box = MessageBox('删除确认', f'确定要删除账号预设 "{selected_acc}" 吗？\n此操作不可恢复。', self)
        if msg_box.exec():
            acc_path = os.path.join(ACCOUNTS_DIR, selected_acc)
            if os.path.exists(acc_path):
                shutil.rmtree(acc_path, ignore_errors=True)
                logger.info(f'已删除账号预设: {selected_acc}')
            self.refresh_accounts_list()
            InfoBar.success('已删除', f'账号预设 "{selected_acc}" 已被移除。', position=InfoBarPosition.TOP, parent=self)

    def on_settings_clicked(self):
        dialog = SettingsDialog(self.config, self)
        if dialog.exec():
            new_conf = dialog.get_result()
            self.config.update(new_conf)
            save_config(self.config)
            self.update_background() # 实时刷新背景图
            InfoBar.success('配置已保存', '启动器各项设置已更新！', position=InfoBarPosition.TOP, parent=self)

    def on_fix_clicked(self):
        game_path = self.config.get('game_path', '')
        if not game_path or not os.path.exists(game_path):
            InfoBar.error('未配置!', '请先点击左下角设置游戏根目录。', position=InfoBarPosition.TOP, parent=self)
            return

        server_name = '官服' if self.current_server == 'official' else 'B服'
        msgBox = MessageBox('修复确认', f'是否要对【{server_name}】执行登录数据重置？\n\n• 关闭正在运行的游戏进程\n• 清除已保存的登录状态 (U8Data / sdkdata)\n• 使用当前服务器的原始客户端文件覆盖冲突文件\n\n⚠ 执行后需要重新登录游戏账号。', self)
        if msgBox.exec():
            self.kill_process("Arknights.exe")
            try:
                # 删除缓存元凶
                u8_data = os.path.join(game_path, "U8Data")
                if os.path.exists(u8_data): shutil.rmtree(u8_data, ignore_errors=True)
                sdk_data = os.path.join(game_path, "sdkdata")
                if os.path.exists(sdk_data): shutil.rmtree(sdk_data, ignore_errors=True)

                # 根据当前选择的服务器使用对应资源
                if self.current_server == 'official':
                    res_path = os.path.join(BASE_DIR, 'resources', 'Payload')
                else:
                    res_path = os.path.join(BASE_DIR, 'resources', 'Payload_B')
                if os.path.exists(res_path):
                    self.copy_tree_overwrite(res_path, game_path)
                
                InfoBar.success('成功', f"【{server_name}】环境修复完毕！可尝试重新登录。", position=InfoBarPosition.TOP, duration=3000, parent=self)
            except Exception as e:
                logger.exception('修复清理时发生异常')
                InfoBar.error('修复失败', f"清理时发生错误: {str(e)}", position=InfoBarPosition.TOP, parent=self)

    def on_maa_clicked(self):
        maa_path = self.config.get('maa_path', '')
        if not maa_path or not os.path.exists(maa_path):
            msgBox = MessageBox('未配置 MAA', '您还没有配置 MAA 的核心执行文件路径 (MAA.exe)。\n是否现在前往「全局设置」中进行配置？', self)
            if msgBox.exec():
                self.on_settings_clicked()
            return
        
        try:
            subprocess.Popen(maa_path, cwd=os.path.dirname(maa_path))
            InfoBar.success('启动成功', "成功拉起 MAA 辅助进程", position=InfoBarPosition.TOP, duration=2000, parent=self)
        except Exception as e:
            logger.exception('启动 MAA 失败')
            InfoBar.error('错误', f'启动 MAA 失败: {str(e)}', position=InfoBarPosition.TOP, parent=self)

    def on_start_game(self):
        game_path = self.config.get('game_path', '')
        if not game_path or not os.path.exists(game_path):
            InfoBar.error('未配置!', '请先点击左下角设置游戏根目录。', position=InfoBarPosition.TOP, duration=3000, parent=self)
            return

        # 检测当前游戏目录实际服务器状态
        server_name = '官服' if self.current_server == 'official' else 'B服'
        detected = self._detect_current_server(game_path)
        need_overlay = (detected != self.current_server)
        acc_text = self.accountCombo.currentText()

        # 启动确认
        if need_overlay:
            summary = f'即将切换到【{server_name}】模式，需要覆盖游戏目录中的部分文件。'
        else:
            summary = f'当前游戏文件已是【{server_name}】环境，将直接启动（跳过文件覆盖）。'
        if acc_text and acc_text != "默认 (不覆盖)":
            summary += f'\n将加载账号预设「{acc_text}」。'
        summary += '\n\n是否继续？'
        if not MessageBox('启动确认', summary, self).exec():
            return

        self.kill_process("Arknights.exe")

        try:

            if need_overlay:
                # 文件覆盖逻辑 — 仅在服务器切换时执行
                if self.current_server == 'official':
                    res_path = os.path.join(BASE_DIR, 'resources', 'Payload')
                    # 互斥清理 B 服专属文件
                    pc_game_sdk = os.path.join(game_path, "PCGameSDK.dll")
                    bl_platform = os.path.join(game_path, "BLPlatform64")
                    if os.path.exists(pc_game_sdk): os.remove(pc_game_sdk)
                    if os.path.exists(bl_platform): shutil.rmtree(bl_platform, ignore_errors=True)
                else:
                    res_path = os.path.join(BASE_DIR, 'resources', 'Payload_B')
                    # 互斥清理官服专属文件
                    hg_sdk = os.path.join(game_path, "hgsdk.dll")
                    if os.path.exists(hg_sdk): os.remove(hg_sdk)

                if os.path.exists(res_path):
                    self.copy_tree_overwrite(res_path, game_path)
                else:
                    InfoBar.error('资源缺失', f'找不到预配资源包: {res_path}', position=InfoBarPosition.TOP, parent=self)
                    return
                logger.info(f'服务器文件已切换: {detected} -> {self.current_server}')
            else:
                logger.info(f'当前已是{"官服" if self.current_server == "official" else "B服"}环境，跳过文件覆盖')

            # 应用账号预设
            selected_acc = self.accountCombo.currentText()
            if selected_acc and selected_acc != "默认 (不覆盖)":
                acc_path = os.path.join(ACCOUNTS_DIR, selected_acc)
                if os.path.exists(acc_path):
                    self.copy_tree_overwrite(acc_path, game_path)

            # 借权启动
            exe_path = os.path.join(game_path, "Arknights.exe")
            if os.path.exists(exe_path):
                ctypes.windll.shell32.ShellExecuteW(None, "runas", exe_path, None, game_path, 1)
                InfoBar.success('正在进入游戏', '模块注入成功，正在拉起游戏终端...', position=InfoBarPosition.TOP, duration=2000, parent=self)
                QTimer.singleShot(1500, self._minimize_to_tray)
            else:
                InfoBar.error('错误', '在游戏目录下未找到 Arknights.exe，请检查游戏是否损坏！', position=InfoBarPosition.TOP, parent=self)

        except Exception as e:
            logger.exception('启动游戏时发生异常')
            InfoBar.error('执行中止', str(e), position=InfoBarPosition.TOP, duration=4000, parent=self)

    # ---------------- 辅助方法 ---------------- 
    def kill_process(self, process_name):
        killed = []
        for proc in psutil.process_iter(['name']):
            try:
                if proc.info['name'] and proc.info['name'].lower() == process_name.lower():
                    proc.kill()
                    killed.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        # 等待进程真正退出，避免文件锁冲突
        for proc in killed:
            try:
                proc.wait(timeout=5)
            except (psutil.NoSuchProcess, psutil.TimeoutExpired):
                pass

    def _detect_current_server(self, game_path):
        """检测游戏目录当前实际对应的服务器，通过特征文件判断"""
        has_bilibili = os.path.exists(os.path.join(game_path, 'PCGameSDK.dll'))
        has_official = os.path.exists(os.path.join(game_path, 'hgsdk.dll'))
        if has_bilibili and not has_official:
            return 'bilibili'
        elif has_official and not has_bilibili:
            return 'official'
        # 无法确定或首次使用时，返回 None 强制执行覆盖
        return None

    def copy_tree_overwrite(self, src_dir, dst_dir, exclude=None):
        if exclude is None:
            exclude = {'meta.json'}
        if not os.path.exists(dst_dir):
            os.makedirs(dst_dir)
        for item in os.listdir(src_dir):
            if item in exclude:
                continue
            s = os.path.join(src_dir, item)
            d = os.path.join(dst_dir, item)
            if os.path.isdir(s):
                self.copy_tree_overwrite(s, d, exclude)
            else:
                shutil.copy2(s, d)

    # ================= 关于 / 托盘 / 退出 =================

    def on_about_clicked(self):
        MessageBox(
            f'关于 Arknights Launcher {VERSION}',
            '明日方舟 PC 端官服 / B服 切换启动器\n\n'
            '功能特性:\n'
            '• 一键切换官服 / Bilibili 服务器\n'
            '• 多账号预设保存与加载\n'
            '• MAA 辅助快速启动\n'
            '• 客户端登录数据修复\n'
            '• 自动检查更新\n\n'
            f'项目地址: github.com/{GITHUB_REPO}\n'
            f'版本: {VERSION}',
            self
        ).exec()

    # ================= 自动更新 =================

    def _check_for_updates(self):
        """启动后台更新检查线程"""
        self._update_checker = UpdateChecker()
        self._update_checker.update_available.connect(self._on_update_available)
        self._update_checker.start()

    def _on_update_available(self, new_version, changelog, download_url):
        """发现新版本时显示更新提示"""
        logger.info(f'发现新版本: {new_version}')
        
        # 截取更新日志前 200 字
        short_log = changelog[:200] + ('...' if len(changelog) > 200 else '')
        
        msg = MessageBox(
            f'发现新版本 {new_version}',
            f'当前版本: {VERSION}\n最新版本: {new_version}\n\n'
            f'更新内容:\n{short_log}\n\n'
            '是否立即更新？',
            self
        )
        msg.yesButton.setText('立即更新')
        msg.cancelButton.setText('下次再说')
        
        if msg.exec():
            self._do_update(download_url, new_version)

    def _do_update(self, download_url, new_version):
        """执行下载并替换"""
        # 如果链接是 GitHub Release 页面(非 exe)，直接打开浏览器
        if not download_url.lower().endswith('.exe'):
            os.startfile(download_url)
            return
        
        dialog = UpdateDownloadDialog(download_url, new_version, self)
        if dialog.exec() and dialog.downloaded_path:
            self._apply_update(dialog.downloaded_path)

    def _apply_update(self, new_exe_path):
        """生成替换脚本并重启"""
        if not getattr(sys, 'frozen', False):
            # 开发模式下不执行替换
            InfoBar.success('开发模式', f'新版已下载到: {new_exe_path}', position=InfoBarPosition.TOP, duration=5000, parent=self)
            return
        
        current_exe = sys.executable
        bat_path = os.path.join(tempfile.gettempdir(), 'ArknightsLauncher_update', 'update.bat')
        
        # 生成替换脚本: 等待当前进程退出 -> 替换 exe -> 重启
        bat_content = f"""@echo off
:wait
tasklist /FI "PID eq {os.getpid()}" 2>NUL | find /I "{os.getpid()}" >NUL
if not errorlevel 1 (
    timeout /t 1 /nobreak >NUL
    goto wait
)
copy /Y "{new_exe_path}" "{current_exe}"
if errorlevel 1 (
    echo Update failed!
    pause
    exit /b 1
)
start "" "{current_exe}"
del "{new_exe_path}"
del "%~f0"
"""
        
        with open(bat_path, 'w', encoding='gbk') as f:
            f.write(bat_content)
        
        # 启动替换脚本并退出当前进程
        subprocess.Popen(
            ['cmd', '/c', bat_path],
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        # 强制退出
        if self._config_dirty:
            save_config(self.config)
        self.trayIcon.hide()
        QApplication.quit()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.showNormal()
            self.activateWindow()

    def _minimize_to_tray(self):
        self.hide()
        self.trayIcon.showMessage(
            'Arknights Launcher',
            '启动器已最小化到系统托盘，双击图标可恢复窗口。',
            QSystemTrayIcon.MessageIcon.Information,
            2000
        )

    def quit_app(self):
        if self._config_dirty:
            save_config(self.config)
        self.trayIcon.hide()
        QApplication.quit()

    def closeEvent(self, e):
        if self._config_dirty:
            save_config(self.config)
            self._config_dirty = False
        # 点 X 时最小化到托盘而非退出
        if hasattr(self, 'trayIcon') and self.trayIcon.isVisible():
            e.ignore()
            self._minimize_to_tray()
            return
        super().closeEvent(e)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    w = ModernArknightsLauncher()
    w.show()
    sys.exit(app.exec())
