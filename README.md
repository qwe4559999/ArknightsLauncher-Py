# ArknightsLauncher-Py (明日方舟现代化启动器)

这是一个以 **PyQt6** 和 **Fluent-Widgets** 为基础构建的全新《明日方舟》PC 端启动器。提供了完全沉浸式的暗流利 (Dark Fluent) 设计、大图连携的模块化 UI，并且修复和补充了原版客户端部分痛点。

## ✨ 核心特性

- 🎨 **现代化沉浸式 UI：** 采用完全无边框沉浸式设计，支持系统级自适应深色标题栏，右侧完整透出高质量游戏大图作为背景。
- 🔄 **服务器无缝互相切换：** 支持一键在“官方服务器”与“Bilibili 服务器”之间无缝切换，并自动执行底层关联文件的互斥清理（避免跨服启动产生脏数据与 `[WinError 740]` 提权错误）。
- 👥 **无限账号管理器：** 支持保存并命名多个服务器的本地账号票据，实现免扫码验证的“大号/马甲”秒切功能！
- 🔧 **游戏系统急救：** 内置 “记忆模糊修复” 功能，在文件发生冲突时一键拉取初始状态注入恢复，解决卡加载等疑难杂症。
- 🤖 **第三方聚合：** 深度融合对第三方著名辅助工具 —— MAA 的直接调起与路径记忆管理。

## 💡 安装与运行

### 环境要求
- Windows 10 / Windows 11
- Python 3.8 或以上版本

### 部署步骤
1. 克隆本仓库到本地：
```cmd
git clone https://github.com/你的用户名/ArknightsLauncher-Py.git
cd ArknightsLauncher-Py
```

2. 推荐创建并进入虚拟环境：
```cmd
python -m venv .venv
.\.venv\Scripts\activate
```

3. 安装项目必需的依赖包：
```cmd
pip install -r requirements.txt
```

4. 启动应用：
```cmd
python main.py
```

## 🛠️ 关于自定义

所有的修改均可通过启动器左下角的 **全局设置** 按钮完成：
- **游戏客户端路径:** 指向带有 `Arknights.exe` 的客户端根目录。
- **MAA路径:** 指向 `MAA.exe` 以启用一键唤醒。
- **自定义背景图:** 可以在这里选择系统本地的任何 `.jpg` / `.png` 文件一键化身为你喜好的干员壁纸。（默认壁纸位于 `resources/bg.jpg`）

## 🙏 致谢与参考项目 (Credits)

本启动器的部分逆向原理与基础服务端切换机制灵感源于社区作者的无私分享：
- 原版 C# ArknightsLauncher 切换机制参考自：[MaaAssistantArknights / 最初的某个 C# 仓库作者] (如有特定原仓库名字可以在此加链接)
- 特别鸣谢：提供高颜值现代控件基础的开源项目 [PyQt-Fluent-Widgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets)。
- 资源与致谢归原《明日方舟》及鹰角网络所有，仅供学习交流使用。