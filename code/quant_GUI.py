# QuantAssistant.py
import sys
import os
import subprocess
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout,
    QLineEdit, QTextEdit, QCheckBox, QHBoxLayout, QSizePolicy, QFrame,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QGuiApplication, QPixmap, QIcon

class ScriptRunnerThread(QThread):
    result_signal = pyqtSignal(str, str, int)  # stdout, stderr, returncode
    def __init__(self, main_path):
        super().__init__()
        self.main_path = main_path
    def run(self):
        import sys
        import subprocess
        try:
            process = subprocess.Popen(
                [sys.executable, self.main_path],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                encoding='utf-8'
            )
            stdout, stderr = process.communicate(timeout=60)
            self.result_signal.emit(stdout or '', stderr or '', process.returncode)
        except Exception as e:
            self.result_signal.emit('', str(e), -1)

class GeminiAPICallThread(QThread):
    result_signal = pyqtSignal(str, str)  # reply, error
    def __init__(self, packaged, screenshot_path, api_key, model_name=None):
        super().__init__()
        self.packaged = packaged
        self.screenshot_path = screenshot_path
        self.api_key = api_key
        self.model_name = model_name
    def run(self):
        try:
            import sys
            import importlib
            base_dir = os.path.dirname(os.path.abspath(__file__))
            sys.path.insert(0, base_dir)
            gemini_api_caller = importlib.import_module("gemini_api_caller")
            call_gemini_api = gemini_api_caller.call_gemini_api
            reply = call_gemini_api(self.packaged, screenshot_path=self.screenshot_path, api_key=self.api_key, model_name=self.model_name)
            self.result_signal.emit(reply, "")
        except Exception as e:
            self.result_signal.emit("", str(e))

class GeminiMainAndApiThread(QThread):
    result_signal = pyqtSignal(str, str)  # reply, error
    def __init__(self, main_path, api_key):
        super().__init__()
        self.main_path = main_path
        self.api_key = api_key
    def run(self):
        import subprocess, os, json, importlib.util
        try:
            result = subprocess.run([sys.executable, self.main_path], capture_output=True, text=True, timeout=90)
            if result.returncode != 0:
                self.result_signal.emit("", f"main.py 执行失败: {result.stderr.strip()}")
                return
            main_output = result.stdout.strip()
        except Exception as e:
            self.result_signal.emit("", f"运行main.py异常: {e}")
            return
        try:
            packaged = json.loads(main_output)
        except Exception as e:
            self.result_signal.emit("", f"main.py输出解析失败: {e}\n原始输出:\n{main_output}")
            return
        screenshot_path = packaged.get("clipboard_image_path")
        base_dir = os.path.dirname(os.path.abspath(__file__))
        try:
            api_path = os.path.join(base_dir, "gemini_api_caller.py")
            spec = importlib.util.spec_from_file_location("gemini_api_caller", api_path)
            api_mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(api_mod)
            reply = api_mod.call_gemini_api(packaged, screenshot_path, self.api_key)
            md_path = os.path.join(base_dir, "gemini_json_to_markdown.py")
            spec_md = importlib.util.spec_from_file_location("gemini_json_to_markdown", md_path)
            md_mod = importlib.util.module_from_spec(spec_md)
            spec_md.loader.exec_module(md_mod)
            # Gemini回复区直接输出json字符串，不再转markdown
            if not isinstance(reply, str):
                reply = json.dumps(reply, ensure_ascii=False, indent=2)
            self.result_signal.emit(reply, "")
        except Exception as e:
            self.result_signal.emit("", f"[Gemini调用或渲染失败] 错误: {e}")

class QuantAssistant(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gemini金融智能体")
        base_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(base_dir, "icon.png")
        self.setWindowIcon(QIcon(icon_path))
        self.resize(1920, 1080)

        # 只保留一个按钮
        self.gemini_advice_button = QPushButton("让Gemini给出操作建议")
        self.gemini_advice_button.clicked.connect(self.gemini_advice_action)

        # Gemini回复区
        self.gemini_reply_box = QTextEdit()
        self.gemini_reply_box.setReadOnly(True)
        self.gemini_reply_box.setMinimumHeight(220)
        self.gemini_reply_box.setPlaceholderText("此处将显示Gemini的AI回复/建议……")

        # 日志区
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMinimumHeight(100)

        # API Key输入
        from PyQt6.QtCore import QSettings
        self.settings = QSettings("GeminiQuant", "GeminiQuantApp")
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("输入Gemini API Key")
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        saved_key = self.settings.value("gemini_api_key", "")
        self.api_key_input.setText(saved_key)
        self.api_key_input.textChanged.connect(self.save_api_key)

        # 截图预览区
        self.screenshot_label = QLabel("截图预览区：")
        self.screenshot_pixmap = QLabel()
        self.screenshot_pixmap.setFixedSize(640, 360)  # 16:9 比例，适合常见截图
        self.screenshot_pixmap.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.screenshot_pixmap.setStyleSheet("border:1px solid #aaa;background:#fafbfc;")
        # 持仓管理区
        from position_info_widget import PositionInfoWidget
        self.position_info_widget = PositionInfoWidget()
        # 新增：空仓选项
        self.empty_pos_checkbox = QCheckBox("空仓（无持仓）")
        self.empty_pos_checkbox.setChecked(True)
        self.empty_pos_checkbox.stateChanged.connect(self.on_empty_pos_changed)
        # 按钮：保存持仓
        self.save_position_btn = QPushButton("保存持仓信息")
        self.save_position_btn.clicked.connect(self.save_position_info)

        # 布局
        # 黄金分割布局：
        # 左侧为高窗口日志输出（约0.382），中间为操作与持仓（约0.382），右侧为Gemini回复和截图（约0.236）
        # 1. 日志区（最左侧）
        log_col = QVBoxLayout()
        log_label = QLabel("日志输出：")
        log_label.setStyleSheet("font-weight:600;font-size:16px;color:#B9770E;")
        log_col.addWidget(log_label)
        log_col.addWidget(self.log_output)
        log_col.setStretch(0, 0)
        log_col.setStretch(1, 1)

        # 2. 操作与持仓区（中间）
        center_col = QVBoxLayout()
        # 截图预览区放最上面
        center_col.addWidget(self.screenshot_label)
        center_col.addWidget(self.screenshot_pixmap)
        center_col.addWidget(QLabel("Gemini金融智能体"), alignment=Qt.AlignmentFlag.AlignHCenter)
        center_col.addWidget(self.gemini_advice_button)
        center_col.addWidget(QLabel("Gemini API Key:"))
        center_col.addWidget(self.api_key_input)
        center_col.addWidget(QLabel("持仓管理："))
        center_col.addWidget(self.empty_pos_checkbox)
        center_col.addWidget(self.position_info_widget)
        center_col.addWidget(self.save_position_btn)
        center_col.addStretch(1)

        # 3. Gemini回复区（最右侧）
        right_col = QVBoxLayout()
        reply_label = QLabel("Gemini对话区：")
        reply_label.setStyleSheet("font-weight:600;font-size:16px;color:#2471A3;")
        right_col.addWidget(reply_label)
        right_col.addWidget(self.gemini_reply_box)
        right_col.setStretch(1, 1)

        # 黄金分割比例 0.18 : 0.32 : 0.5
        main_layout = QHBoxLayout()
        main_layout.setSpacing(24)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.addLayout(log_col, 18)
        main_layout.addLayout(center_col, 32)
        main_layout.addLayout(right_col, 50)
        self.setLayout(main_layout)
        self.setStyleSheet('''
* {
    font-family: 'Segoe UI', 'Microsoft YaHei', Arial, sans-serif;
    font-size: 14px;
    color: #2E3A47;
    background-color: #FFFFFF;
}
QWidget {
    background-color: #F4F7FA;
    color: #2E3A47;
}
QPushButton {
    background-color: #4A90E2;
    color: #FFFFFF;
    border: 1px solid #357ABD;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #357ABD;
    border-color: #2C6DA5;
}
QPushButton:pressed {
    background-color: #2C6DA5;
}
QTextEdit, QLineEdit {
    border: 1px solid #B2C4D4;
    border-radius: 6px;
    background: #FFFFFF;
    color: #2E3A47;
    padding: 10px;
}
QTextEdit[readOnly="true"] {
    background-color: #F1F6FA;
    color: #5F6C7A;
    border: 1px solid #B2C4D4;
}
QLabel {
    font-size: 15px;
    color: #2E3A47;
    padding: 4px 0;
}
QScrollBar:horizontal {
    height: 8px;
    background: #E1E8ED;
    border-radius: 4px;
}
QScrollBar:vertical {
    width: 8px;
    background: #E1E8ED;
    border-radius: 4px;
}
QScrollBar::handle {
    background: #A9B9C8;
    border-radius: 4px;
}
QScrollBar::handle:hover {
    background: #7F8C99;
}
QHeaderView::section {
    background-color: #F1F6FA;
    color: #2E3A47;
    padding: 6px 12px;
    border: 1px solid #B2C4D4;
}
''')

    def log(self, message):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{now}] {message}"
        self.log_output.append(log_line)
        print(log_line)
        QApplication.processEvents()

    def gemini_advice_action(self):
        self.log("正在调用main.py采集数据...")
        self.gemini_reply_box.setPlainText("Gemini正在推理中，请稍候...")
        base_dir = os.path.dirname(os.path.abspath(__file__))
        main_path = os.path.join(base_dir, "main.py")
        # 用线程避免界面卡死
        self.gemini_thread = GeminiMainAndApiThread(main_path, self.get_api_key())
        self.gemini_thread.result_signal.connect(self.on_gemini_reply)
        self.gemini_thread.start()

    def on_gemini_reply(self, markdown, error):
        if error:
            self.gemini_reply_box.setPlainText(error)
            self.log(error)
            self.update_screenshot_preview()
            return
        # 检查markdown内容是否为main.py原始JSON（即未经过AI处理）
        import json
        try:
            data = json.loads(markdown)
            # 如果能被解析为dict且有indicators等字段，说明是main.py原始输出，非AI回复
            if isinstance(data, dict) and ("indicators" in data or "factors" in data):
                self.gemini_reply_box.setPlainText("[错误] main.py输出被直接显示，未经过Gemini AI推理。\n请检查main.py是否只输出一份JSON，且不要有多余print/调试信息。\n\n原始内容：\n" + markdown)
                self.log("[错误] main.py输出被直接显示，未经过Gemini AI推理。请检查main.py输出格式。")
                self.update_screenshot_preview()
                return
        except Exception:
            pass
        self.gemini_reply_box.setMarkdown(markdown)
        self.log("Gemini回复已显示。")
        self.update_screenshot_preview()

    def update_screenshot_preview(self):
        # 从main.py输出的截图路径加载图片
        import os
        from PyQt6.QtGui import QPixmap
        base_dir = os.path.dirname(os.path.abspath(__file__))
        main_path = os.path.join(base_dir, "main.py")
        try:
            result = subprocess.run([sys.executable, main_path], capture_output=True, text=True, timeout=90)
            import json
            packaged = json.loads(result.stdout.strip())
            img_path = packaged.get("clipboard_image_path")
            if img_path and os.path.exists(img_path):
                pixmap = QPixmap(img_path)
                self.screenshot_pixmap.setPixmap(pixmap.scaledToHeight(160))
            else:
                self.screenshot_pixmap.clear()
        except Exception:
            self.screenshot_pixmap.clear()

    def save_position_info(self):
        if hasattr(self, 'empty_pos_checkbox') and self.empty_pos_checkbox.isChecked():
            self.log("持仓信息已保存: 空仓（无持仓）")
            return
        info = self.position_info_widget.get_position_info_text() if hasattr(self.position_info_widget, 'get_position_info_text') else str(self.position_info_widget)
        self.log(f"持仓信息已保存: {info}")

    def on_empty_pos_changed(self, state):
        is_empty = (state == Qt.CheckState.Checked.value)
        self.position_info_widget.setEnabled(not is_empty)
        if is_empty:
            self.log("已选择空仓，持仓输入已禁用。")
        else:
            self.log("取消空仓选项，可以填写持仓信息。")

    def save_api_key(self, key):
        self.settings.setValue("gemini_api_key", key)
        import os
        os.environ["GEMINI_API_KEY"] = key

    def get_api_key(self):
        return self.api_key_input.text().strip()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = QuantAssistant()
    win.show()
    sys.exit(app.exec())
