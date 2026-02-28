import sys
import os
import json
import shutil
import psutil
import subprocess
import ctypes

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QFont, QPixmap, QPainter, QColor, QBrush, QAction
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QFileDialog, QFrame, QGraphicsDropShadowEffect
)
from qfluentwidgets import (
    SubtitleLabel, setTheme, Theme, TitleLabel, CardWidget, 
    IconWidget, BodyLabel, PushButton, FluentIcon, PrimaryPushButton,
    MessageBox, InfoBar, InfoBarPosition, LineEdit, ToolButton,
    ComboBox, MessageBoxBase, SegmentedWidget, TransparentDropDownPushButton, RoundMenu, Action,
    MSFluentTitleBar
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
        self.initWindow()
        self.initUI()
        self.refresh_accounts_list()
        
        # 在界面初始化完成后检查是否需要首次配置指南
        # 使用 QTimer 稍微延迟触发以确保窗口已经渲染完毕
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(100, self.check_first_run)
        
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

        # 添加一个顶部深色渐变阴影层，用来保证各种鲜艳壁纸下标题栏按钮(关闭/最小化)和字体的可见度
        self.titleShadow = QFrame(self)
        self.titleShadow.setObjectName("TitleShadow")
        self.titleShadow.setStyleSheet("""
            #TitleShadow {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(0, 0, 0, 0.7), stop:1 rgba(0, 0, 0, 0));
            }
        """)
        # 初始化时设定一次坐标，使其铺满顶部区域 (高度约为50)
        self.titleShadow.setGeometry(0, 0, 2000, 50)
        # 将它置于底层之上，但在 titleBar 之下
        self.titleShadow.lower()

        # 强制暗黑流利风格
        setTheme(Theme.DARK)
        self.update_background()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        # 当窗口改变大小时，同步拉伸顶部黑色抗反光层
        if hasattr(self, 'titleShadow'):
            self.titleShadow.setGeometry(0, 0, self.width(), 60)

    def update_background(self):
        bg_path = self.config.get('bg_path', os.path.join(BASE_DIR, 'resources', 'bg.png'))
        # 转换为正斜杠并确保路径存在以正常渲染，如果不存在退回空实现或默认深色
        bg_url = bg_path.replace("\\", "/") if os.path.exists(bg_path) else "none"
        bg_css = f"border-image: url({bg_url}) 0 0 0 0 stretch stretch;" if bg_url != "none" else ""

        # 动态根据壁纸比例调整窗口宽度以防压缩 (将高度固定在 550)
        if os.path.exists(bg_path):
            pixmap = QPixmap(bg_path)
            if not pixmap.isNull():
                ratio = pixmap.width() / pixmap.height()
                target_height = 550
                # 右侧壁纸自适应真实宽度
                right_width = target_height * ratio
                # 总窗口宽度 = 侧边栏的固宽(280) + 右侧完美比例宽度 
                total_width = int(right_width) + 280
                
                # 约束宽度的最小值和最大值，防止界面错乱或超出屏幕 (900是合理的最小宽度)
                total_width = max(900, min(total_width, 1600))
                self.resize(total_width, target_height)

        self.setStyleSheet(f"""
            ModernArknightsLauncher {{
                background-color: #1a1a1a;
            }}
            #LeftSidebar {{
                background-color: rgba(30, 30, 30, 0.7);
                border-right: 1px solid rgba(255, 255, 255, 0.05);
            }}
            #RightContent {{
                {bg_css}
                border-top-left-radius: 12px;
                border-bottom-left-radius: 12px;
            }}
            #WatermarkLabel {{
                color: rgba(255, 255, 255, 0.05);
                font-size: 80px;
                font-weight: bold;
            }}
        """)

    def initUI(self):
        self.mainLayout = QHBoxLayout(self)
        self.mainLayout.setContentsMargins(0, 0, 0, 0)
        self.mainLayout.setSpacing(0)
        
        # ----------------- 左侧边栏 (透明/功能区) -----------------
        self.sidebar = QFrame()
        self.sidebar.setObjectName("LeftSidebar")
        self.sidebar.setFixedWidth(280)
        self.sidebarLayout = QVBoxLayout(self.sidebar)
        self.sidebarLayout.setContentsMargins(20, 30, 20, 30)
        self.sidebarLayout.setSpacing(15)
        
        # APP 标题部分
        self.titleLayout = QHBoxLayout()
        self.iconLabel = IconWidget(OFFICIAL_ICON, self)
        self.iconLabel.setFixedSize(36, 36)
        self.titleLabel = TitleLabel("Arknights", self)
        self.titleLabel.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        self.titleLayout.addWidget(self.iconLabel)
        self.titleLayout.addWidget(self.titleLabel)
        self.titleLayout.addStretch()
        self.sidebarLayout.addLayout(self.titleLayout)
        
        self.sidebarLayout.addSpacing(20)
        
        # 账号管理区
        self.accLabel = SubtitleLabel("当前账号", self)
        self.sidebarLayout.addWidget(self.accLabel)
        
        self.accRow = QHBoxLayout()
        self.accountCombo = ComboBox(self)
        self.accountCombo.setMinimumWidth(180)
        
        self.saveAccBtn = ToolButton(FluentIcon.SAVE, self)
        self.saveAccBtn.setToolTip("将当前游戏的登录状态保存为新账号")
        self.saveAccBtn.clicked.connect(self.on_save_account)
        
        self.accRow.addWidget(self.accountCombo)
        self.accRow.addWidget(self.saveAccBtn)
        self.sidebarLayout.addLayout(self.accRow)
        
        self.sidebarLayout.addSpacing(20)
        
        # 实用工具区
        self.toolsLabel = SubtitleLabel("系统工具", self)
        self.sidebarLayout.addWidget(self.toolsLabel)
        
        self.maaBtn = PushButton('启动 MAA', self, FluentIcon.ROBOT)
        self.maaBtn.clicked.connect(self.on_maa_clicked)
        if os.path.exists(MAA_ICON):
            self.maaBtn.setIcon(QIcon(MAA_ICON))
        self.sidebarLayout.addWidget(self.maaBtn)
        
        self.fixBtn = PushButton('修复记忆模糊', self, FluentIcon.SYNC)
        self.fixBtn.clicked.connect(self.on_fix_clicked)
        self.sidebarLayout.addWidget(self.fixBtn)
        
        self.sidebarLayout.addStretch(1)
        
        # 底部设置区
        self.settingsBtn = PushButton('全局设置', self, FluentIcon.SETTING)
        self.settingsBtn.clicked.connect(self.on_settings_clicked)
        self.sidebarLayout.addWidget(self.settingsBtn)
        
        self.mainLayout.addWidget(self.sidebar)

        # ----------------- 右侧主视窗 (背景 + 大按钮) -----------------
        self.rightContent = QFrame()
        self.rightContent.setObjectName("RightContent")
        self.rightLayout = QVBoxLayout(self.rightContent)
        self.rightLayout.setContentsMargins(40, 40, 40, 40)
        
        # 顶部：服务器切换器
        self.headerRow = QHBoxLayout()
        self.headerRow.addStretch(1)

        self.serverPivot = SegmentedWidget(self.rightContent)

        # 添加带有真实图标的 Server Item
        self.serverPivot.addItem('official', '官方服务器', self.on_server_switched, QIcon(OFFICIAL_ICON))
        self.serverPivot.addItem('bilibili', 'Bilibili 服务器', self.on_server_switched, QIcon(BSERVER_ICON))
        
        # 为了让右侧的 SegmentedWidget 更美观，我们可以增加一点内间距并稍微修改它的层级表现
        self.serverPivot.setStyleSheet("""
            SegmentedWidget {
                background-color: rgba(0, 0, 0, 0.4);
                border-radius: 6px;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }
        """)

        self.headerRow.addWidget(self.serverPivot)
        self.rightLayout.addLayout(self.headerRow)  # 将 headerRow 添加到右侧主布局中
        self.rightLayout.addStretch(1)
        self.watermarkLayout = QHBoxLayout()
        self.watermark = QLabel("RHODES ISLAND", self)
        self.watermark.setObjectName("WatermarkLabel")
        self.watermark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.watermarkLayout.addStretch(1)
        self.watermarkLayout.addWidget(self.watermark)
        self.watermarkLayout.addStretch(1)
        self.rightLayout.addLayout(self.watermarkLayout)
        self.rightLayout.addStretch(1)
        
        # 底部：巨型启动按钮
        self.startBtnLayout = QHBoxLayout()
        self.startBtnLayout.addStretch(1)
        
        self.startBtn = PrimaryPushButton(' 启动游戏  START', self, FluentIcon.PLAY)
        self.startBtn.setFixedSize(300, 70)
        self.startBtn.setFont(QFont("Microsoft YaHei", 18, QFont.Weight.Bold))
        self.startBtn.clicked.connect(self.on_start_game)
        
        # 增加按钮阴影展现质感
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 5)
        self.startBtn.setGraphicsEffect(shadow)
        
        self.startBtnLayout.addWidget(self.startBtn)
        self.rightLayout.addLayout(self.startBtnLayout)
        
        self.mainLayout.addWidget(self.rightContent)
        
        # 默认选中官服
        self.current_server = 'official'
        self.serverPivot.setCurrentItem('official')
        self.on_server_switched('official')

        # 核心修复：将标题栏及控制按钮提升到渲染的最上层，防止被主体背景色覆盖
        self.titleBar.raise_()

    def on_server_switched(self, routeKey):
        self.current_server = routeKey
        if routeKey == 'official':
            self.startBtn.setIcon(QIcon(OFFICIAL_ICON))
        else:
            self.startBtn.setIcon(QIcon(BSERVER_ICON))

    # ================= 功能逻辑 =================
    
    def refresh_accounts_list(self):
        self.accountCombo.clear()
        self.accountCombo.addItem("默认 (不覆盖)")
        if not os.path.exists(ACCOUNTS_DIR):
            os.makedirs(ACCOUNTS_DIR)
        for item in os.listdir(ACCOUNTS_DIR):
            if os.path.isdir(os.path.join(ACCOUNTS_DIR, item)):
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
            
            u8_data = os.path.join(game_path, "U8Data")
            if os.path.exists(u8_data):
                self.copy_tree_overwrite(u8_data, os.path.join(acc_save_path, "U8Data"))
                
            sdk_data = os.path.join(game_path, "sdkdata")
            if os.path.exists(sdk_data):
                self.copy_tree_overwrite(sdk_data, os.path.join(acc_save_path, "sdkdata"))
            
            self.refresh_accounts_list()
            self.accountCombo.setCurrentText(acc_name)
            InfoBar.success('成功', f'当前登录账状态已保存为：{acc_name}', position=InfoBarPosition.TOP, parent=self)

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

        msgBox = MessageBox('修复确认', '是否要强制执行 记忆模糊修复？\n这将关闭游戏并利用初始官方资源覆盖所有冲突客户端文件。', self)
        if msgBox.exec():
            self.kill_process("Arknights.exe")
            try:
                # 删除缓存元凶
                u8_data = os.path.join(game_path, "U8Data")
                if os.path.exists(u8_data): shutil.rmtree(u8_data, ignore_errors=True)
                sdk_data = os.path.join(game_path, "sdkdata")
                if os.path.exists(sdk_data): shutil.rmtree(sdk_data, ignore_errors=True)

                res_path = os.path.join(BASE_DIR, 'resources', 'Payload')
                if os.path.exists(res_path):
                    self.copy_tree_overwrite(res_path, game_path)
                
                InfoBar.success('成功', "记忆模糊清理覆盖完毕！可尝试重新登录。", position=InfoBarPosition.TOP, duration=3000, parent=self)
            except Exception as e:
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
            InfoBar.error('错误', f'启动 MAA 失败: {str(e)}', position=InfoBarPosition.TOP, parent=self)

    def on_start_game(self):
        game_path = self.config.get('game_path', '')
        if not game_path or not os.path.exists(game_path):
            InfoBar.error('未配置!', '请先点击左下角设置游戏根目录。', position=InfoBarPosition.TOP, duration=3000, parent=self)
            return

        self.kill_process("Arknights.exe")

        try:
            # 文件覆盖逻辑
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

            # 执行覆盖
            if os.path.exists(res_path):
                self.copy_tree_overwrite(res_path, game_path)
            else:
                InfoBar.error('资源缺失', f'找不到预配资源包: {res_path}', position=InfoBarPosition.TOP, parent=self)
                return

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
                InfoBar.success('正在进入游戏', f'模块注入成功，正在拉起游戏终端...', position=InfoBarPosition.TOP, duration=2000, parent=self)
            else:
                InfoBar.error('错误', '在游戏目录下未找到 Arknights.exe，请检查游戏是否损坏！', position=InfoBarPosition.TOP, parent=self)

        except Exception as e:
            InfoBar.error('执行中止', str(e), position=InfoBarPosition.TOP, duration=4000, parent=self)

    # ---------------- 辅助方法 ---------------- 
    def kill_process(self, process_name):
        for proc in psutil.process_iter(['name']):
            if proc.info['name'] and proc.info['name'].lower() == process_name.lower():
                try:
                    proc.kill()
                except psutil.AccessDenied:
                    pass

    def copy_tree_overwrite(self, src_dir, dst_dir):
        if not os.path.exists(dst_dir):
            os.makedirs(dst_dir)
        for item in os.listdir(src_dir):
            s = os.path.join(src_dir, item)
            d = os.path.join(dst_dir, item)
            if os.path.isdir(s):
                self.copy_tree_overwrite(s, d)
            else:
                shutil.copy2(s, d)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    w = ModernArknightsLauncher()
    w.show()
    sys.exit(app.exec())
