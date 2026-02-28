# ArknightsLauncher-Py (明日方舟多服切换启动器)

这是一个基于 **PyQt6** 和 **Fluent-Widgets** 构建的《明日方舟》PC 端第三方启动器。它提供了一个现代化的图形界面，并实现了多服务器切换、账号本地保存以及辅助工具快速拉起等便携功能。

## ✨ 核心功能

- **现代化 UI 界面：** 采用无边框与自适应深色标题栏设计，右侧支持自定义高质量游戏背景图。
- **多服务器切换：** 支持在“官方服务器”与“Bilibili 服务器”之间快速切换。自动清理底层互斥文件，并已处理 [WinError 740] UAC 提权错误。
- **账号多开保存：** 支持在本地保存多个服务器的玩家账号缓存凭证。登录时可选择覆盖缓存，实现免扫码免验证的账号秒切。
- **记忆模糊修复：** 支持在文件冲突或发生加载异常时，一键清除关键缓存文件并重新覆盖初始官方资源。
- **MAA 快速启动：** 在左侧边栏内置联动按钮，配置路径后可一键拉起 MAA 辅助工具。

## 💡 安装与运行

### 环境要求
- Windows 10 / Windows 11
- Python 3.8 或以上版本

### 部署步骤
1. 克隆本仓库到本地：
```cmd
git clone https://github.com/qwe4559999/ArknightsLauncher-Py.git
cd ArknightsLauncher-Py
```

2. 推荐创建并进入虚拟环境：
```cmd
python -m venv .venv
.\.venv\Scripts\activate
```

3. 安装依赖包：
```cmd
pip install -r requirements.txt
```

4. 启动应用：
```cmd
python main.py
```

> **免安装版本**：如果您不想配置 Python 环境，可在项目的 Github Releases 页面下载打包好的单文件免安装版本 (`ArknightsLauncher-Py-StandAlone.exe`)，双击即可运行。

## 🛠️ 自定义设置

所有的自定义与路径绑定均可通过启动器左下角的 **全局设置** 完成：
- **游戏客户端路径:** 设定由于本地 `Arknights.exe` 所在的客户端根目录。
- **MAA路径:** 设定本地 `MAA.exe` 的完整路径。
- **自定义背景图:** 可在此选择您设备上的任意 `.jpg` / `.png` 文件作为右侧页面的背景图。

## 🙏 致谢与参考项目

本项目的核心实现机制（包含提权命令、DLL互斥清理与账号提取缓存机制）源于开源社区其他开发者的启发与无私分享，特此致谢：
- 核心思路与账号切换机制参考：[lTinchl/ArknightsLauncher](https://github.com/lTinchl/ArknightsLauncher)
- 相关 UI 控件基础参考项目：[PyQt-Fluent-Widgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets)
- 图像与图标版权均归《明日方舟》及上海鹰角网络科技有限公司所有，本项目仅供学习与技术交流。