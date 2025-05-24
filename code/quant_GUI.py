# QuantAssistant.py
# 量化助手主界面
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
import logging

class ScriptRunnerThread(QThread):
    result_signal = pyqtSignal(str, str, int)  # 脚本执行结果信号：标准输出、错误输出、返回码
    def __init__(self, main_path):
        super().__init__()
        self.main_path = main_path  # 主控脚本路径
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
    result_signal = pyqtSignal(str, str)  # Gemini API 调用结果信号：回复、错误
    def __init__(self, packaged, screenshot_path, api_key, model_name=None):
        super().__init__()
        self.packaged = packaged  # 打包后的数据
        self.screenshot_path = screenshot_path  # 截图路径
        self.api_key = api_key  # Gemini API Key
        self.model_name = model_name  # 模型名称
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
    result_signal = pyqtSignal(str, str)  # 主控链路+Gemini API 结果信号：回复、错误
    stream_signal = pyqtSignal(str)  # 新增：流式内容信号
    log_signal = pyqtSignal(str, str)  # 新增：日志信号，参数为(message, level)
    def __init__(self, main_path, api_key):
        super().__init__()
        self.main_path = main_path  # 主控脚本路径
        self.api_key = api_key  # Gemini API Key
        self.log_func = None  # 可选：主界面log方法
    def set_log_func(self, func):
        self.log_func = func
    def emit_log(self, message, level="info"):
        if self.log_func:
            self.log_func(message, level)
        else:
            print(f"[GeminiMainAndApiThread][{level}] {message}")
    def run(self):
        import subprocess, os, json, importlib.util, time
        try:
            self.emit_log("[主控链路] 开始运行main.py采集数据...", level="info")
            result = subprocess.run([sys.executable, self.main_path], capture_output=True, text=True, timeout=90)
            self.emit_log(f"[主控链路] main.py返回码: {result.returncode}, stdout: {result.stdout.strip()[:120]}", level="info")
            if result.returncode != 0 or not result.stdout.strip().startswith("完成"):
                self.result_signal.emit("", f"main.py 执行失败: {result.stderr.strip()}\n输出: {result.stdout.strip()}")
                return
            base_dir = os.path.dirname(os.path.abspath(__file__))
            data_path = os.path.join(base_dir, "data.json")
            self.emit_log(f"[主控链路] 检查data.json: {data_path}", level="info")
            if not os.path.exists(data_path):
                self.result_signal.emit("", "未找到 data.json，数据采集失败。")
                return
            with open(data_path, "r", encoding="utf-8") as f:
                packaged = json.load(f)
            self.emit_log(f"[主控链路] data.json已读取，内容keys: {list(packaged.keys())}", level="info")
        except Exception as e:
            self.emit_log(f"[主控链路] 运行main.py或读取data.json异常: {e}", level="error")
            self.result_signal.emit("", f"运行main.py或读取data.json异常: {e}")
            return
        screenshot_path = packaged.get("clipboard_image_path")
        try:
            self.emit_log("[主控链路] 开始加载gemini_api_caller模块...", level="info")
            api_path = os.path.join(base_dir, "gemini_api_caller.py")
            spec = importlib.util.spec_from_file_location("gemini_api_caller", api_path)
            api_mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(api_mod)
            self.emit_log("[主控链路] 模块加载完成，准备调用Gemini API (流式优先)...", level="info")
            # === 流式调用 ===
            stream_func = getattr(api_mod, "call_gemini_api_stream", None)
            if stream_func:
                buffer = ""
                for chunk in stream_func(
                    packaged_json=packaged,
                    screenshot_path=screenshot_path,
                    api_key=self.api_key,
                    model_name=None
                ):
                    if chunk:
                        buffer += chunk
                        self.stream_signal.emit(buffer)
                        self.emit_log(f"[主控链路] 流式信号已emit，当前长度: {len(buffer)}", level="info")
                        time.sleep(0.02)  # 控制流速，防止刷屏
                self.emit_log("[主控链路] Gemini流式推理结束，emit最终结果", level="info")
                self.result_signal.emit(buffer, "")
                return
            self.emit_log("[主控链路] 未检测到流式API，fallback到同步API...", level="warning")
            # === 兼容：无流式函数时走原同步 ===
            reply = api_mod.call_gemini_api(
                packaged_json=packaged,
                screenshot_path=screenshot_path,
                api_key=self.api_key,
                model_name=None
            )
            if not isinstance(reply, str):
                reply = json.dumps(reply, ensure_ascii=False, indent=2)
            self.emit_log("[主控链路] 同步API调用完成，emit结果", level="info")
            self.result_signal.emit(reply, "")
        except Exception as e:
            self.emit_log(f"[主控链路] Gemini API调用或渲染异常: {e}", level="error")
            self.result_signal.emit("", f"[Gemini调用或渲染失败] 错误: {e}")

class QTextEditLogger(logging.Handler):
    def __init__(self, widget):
        super().__init__()
        self.widget = widget  # 日志输出控件
    def emit(self, record):
        msg = self.format(record)
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, lambda: self.widget.append(msg))

class QuantAssistant(QWidget):
    """主界面类"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gemini金融智能体")  # 窗口标题
        base_dir = os.path.dirname(os.path.abspath(__file__))  # 当前文件目录
        icon_path = os.path.join(base_dir, "icon.png")  # 图标路径
        self.setWindowIcon(QIcon(icon_path))  # 设置窗口图标
        self.resize(1920, 1080)  # 默认窗口大小

        # 只保留一个按钮
        self.gemini_advice_button = QPushButton("让Gemini给出操作建议")  # Gemini建议按钮
        self.gemini_advice_button.clicked.connect(self.gemini_advice_action)

        # Gemini回复区
        self.gemini_reply_box = QTextEdit()  # Gemini回复文本框
        self.gemini_reply_box.setReadOnly(True)
        self.gemini_reply_box.setMinimumHeight(220)
        self.gemini_reply_box.setPlaceholderText("此处将显示Gemini的AI回复/建议……")
        self.gemini_reply_box.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)

        # 日志区
        self.log_output = QTextEdit()  # 日志输出文本框
        self.log_output.setReadOnly(True)
        self.log_output.setMinimumHeight(100)
        self.log_output.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.log_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../gemini_quant.log")
        self.log_file_offset = 0  # 日志文件偏移量
        self.log_typewriter_buffer = ""  # 待逐字输出的内容
        self.log_typewriter_timer = QTimer(self)
        self.log_typewriter_timer.timeout.connect(self._typewriter_tick)
        self.log_file_timer = QTimer(self)
        self.log_file_timer.timeout.connect(self.load_log_file)
        self.log_file_timer.start(1000)  # 每秒刷新一次
        self.load_log_file()  # 启动时立即加载

        # API Key输入
        from PyQt6.QtCore import QSettings
        self.settings = QSettings("GeminiQuant", "GeminiQuantApp")  # 配置存储
        self.api_key_input = QLineEdit()  # API Key输入框
        self.api_key_input.setPlaceholderText("输入Gemini API Key")
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        saved_key = self.settings.value("gemini_api_key", "")  # 读取已保存的API Key
        self.api_key_input.setText(saved_key)
        self.api_key_input.textChanged.connect(self.save_api_key)

        # 截图预览区
        self.screenshot_label = QLabel("截图预览区：")  # 截图区标题
        self.screenshot_pixmap = QLabel()  # 截图显示控件
        self.screenshot_pixmap.setFixedSize(640, 360)  # 16:9 比例，适合常见截图
        self.screenshot_pixmap.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.screenshot_pixmap.setStyleSheet("border:1px solid #aaa;background:#fafbfc;")
        # 持仓管理区
        from position_info_widget import PositionInfoWidget
        self.position_info_widget = PositionInfoWidget()  # 持仓信息控件
        # 新增：空仓选项
        self.empty_pos_checkbox = QCheckBox("空仓（无持仓）")  # 空仓复选框
        self.empty_pos_checkbox.setChecked(True)
        self.empty_pos_checkbox.stateChanged.connect(self.on_empty_pos_changed)
        # 按钮：保存持仓
        self.save_position_btn = QPushButton("保存持仓信息")  # 保存持仓按钮
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

    def load_log_file(self):
        """加载并显示统一日志文件内容，并自动滚动到底部（逐字流式输出）"""
        if not os.path.exists(self.log_file_path):
            self.log_output.setPlainText("[无日志文件]")
            self.log_file_offset = 0
            return
        file_size = os.path.getsize(self.log_file_path)
        # 日志被清空或文件变小，重置
        if file_size < self.log_file_offset:
            self.log_output.clear()
            self.log_file_offset = 0
        # 只读取新追加内容
        with open(self.log_file_path, "r", encoding="utf-8") as f:
            f.seek(self.log_file_offset)
            new_content = f.read()
            self.log_file_offset = f.tell()
        if new_content:
            self.log_typewriter_buffer += new_content
            if not self.log_typewriter_timer.isActive():
                self.log_typewriter_timer.start(6)  # 打字机速度（ms/字）
        # 自动滚动到底部
        cursor = self.log_output.textCursor()
        from PyQt6.QtGui import QTextCursor
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.log_output.setTextCursor(cursor)
        self.log_output.ensureCursorVisible()

    def _typewriter_tick(self):
        """打字机定时器：逐字插入新日志内容"""
        if self.log_typewriter_buffer:
            next_char = self.log_typewriter_buffer[0]
            self.log_typewriter_buffer = self.log_typewriter_buffer[1:]
            self.log_output.moveCursor(self.log_output.textCursor().MoveOperation.End)
            self.log_output.insertPlainText(next_char)
            self.log_output.ensureCursorVisible()
        else:
            self.log_typewriter_timer.stop()

    def closeEvent(self, event):
        """关闭GUI时清空日志文件并停止定时器"""
        self.log_file_timer.stop()
        self.log_typewriter_timer.stop()
        self.log_file_offset = 0
        self.log_typewriter_buffer = ""
        if os.path.exists(self.log_file_path):
            with open(self.log_file_path, "w", encoding="utf-8") as f:
                f.truncate(0)
        self.log_output.clear()
        event.accept()

    def log(self, message, level="info"):
        """日志输出函数，自动刷新日志区为统一日志文件内容"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{now}] {message}"
        print(log_line)
        QApplication.processEvents()
        # 日志同步到 logging
        logger = logging.getLogger("GeminiQuant")
        if level == "error":
            logger.error(message)
        elif level == "warning":
            logger.warning(message)
        else:
            logger.info(message)
        QTimer.singleShot(200, self.load_log_file)  # 延迟刷新，确保文件写入完成

    def gemini_advice_action(self):
        """点击按钮后调用主控链路"""
        self.log("正在调用main.py采集数据...", level="info")
        self.gemini_reply_box.setPlainText("Gemini正在推理中，请稍候...")
        base_dir = os.path.dirname(os.path.abspath(__file__))
        main_path = os.path.join(base_dir, "main.py")
        self.gemini_thread = GeminiMainAndApiThread(main_path, self.get_api_key())
        self.gemini_thread.result_signal.connect(self.on_gemini_reply)
        self.gemini_thread.stream_signal.connect(self.on_gemini_stream)
        self.gemini_thread.set_log_func(self.log)
        self.gemini_thread.start()

    def on_gemini_reply(self, markdown, error):
        self.log(f"[GUI] on_gemini_reply被调用，error={error is not None}, 内容预览: {str(markdown)[:80]}", level="info")
        if error:
            self.log(error, level="error")
            self.gemini_reply_box.setPlainText(error)
            self.update_screenshot_preview()
            return
        import json
        import os
        img_path = None  # 图片路径
        # 尝试格式化为 JSON
        try:
            data = json.loads(markdown)
            # main.py原始输出，非AI回复
            if isinstance(data, dict) and ("indicators" in data or "factors" in data):
                self.gemini_reply_box.setPlainText(
                    "[错误] main.py输出被直接显示，未经过Gemini AI推理。\n请检查main.py是否只输出一份JSON，且不要有多余print/调试信息。\n\n原始内容：\n" +
                    json.dumps(data, ensure_ascii=False, indent=2)
                )
                self.log("[错误] main.py输出被直接显示，未经过Gemini AI推理。请检查main.py输出格式。")
                # 直接读取data.json中的clipboard_image_path
                base_dir = os.path.dirname(os.path.abspath(__file__))
                data_path = os.path.join(base_dir, "data.json")
                if os.path.exists(data_path):
                    with open(data_path, "r", encoding="utf-8") as f:
                        d = json.load(f)
                        img_path = d.get("clipboard_image_path")
                self.update_screenshot_preview(img_path)
                return
            # AI回复时，若AI回复内容中带有图片路径，也可提取
            # 直接读取data.json中的clipboard_image_path
            base_dir = os.path.dirname(os.path.abspath(__file__))
            data_path = os.path.join(base_dir, "data.json")
            if os.path.exists(data_path):
                with open(data_path, "r", encoding="utf-8") as f:
                    d = json.load(f)
                    img_path = d.get("clipboard_image_path")
            self.gemini_reply_box.setPlainText(json.dumps(data, ensure_ascii=False, indent=2))
        except Exception:
            # 不是JSON，尝试用Markdown显示
            self.gemini_reply_box.setMarkdown(markdown)
            # markdown回复时也直接读取data.json中的clipboard_image_path
            base_dir = os.path.dirname(os.path.abspath(__file__))
            data_path = os.path.join(base_dir, "data.json")
            if os.path.exists(data_path):
                with open(data_path, "r", encoding="utf-8") as f:
                    d = json.load(f)
                    img_path = d.get("clipboard_image_path")
        self.log("Gemini回复已显示。", level="info")
        self.update_screenshot_preview(img_path)

    def on_gemini_stream(self, text):
        # 只在内容有变化时输出日志，避免重复刷屏
        if not hasattr(self, '_last_stream_text') or self._last_stream_text != text:
            self.log(f"[GUI] on_gemini_stream被调用，流式内容长度: {len(text)}", level="info")
            self._last_stream_text = text
        self.gemini_reply_box.setPlainText(text)
        cursor = self.gemini_reply_box.textCursor()
        from PyQt6.QtGui import QTextCursor
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.gemini_reply_box.setTextCursor(cursor)
        self.gemini_reply_box.ensureCursorVisible()

    def update_screenshot_preview(self, img_path=None):
        """截图预览区更新函数"""
        import os
        from PyQt6.QtGui import QPixmap
        if not img_path or not isinstance(img_path, str) or not img_path.strip():
            self.screenshot_pixmap.clear()
            return
        img_path = os.path.abspath(img_path)
        if os.path.exists(img_path):
            pixmap = QPixmap(img_path)
            target_size = self.screenshot_pixmap.size()
            scaled_pixmap = pixmap.scaled(target_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.screenshot_pixmap.setPixmap(scaled_pixmap)
        else:
            self.screenshot_pixmap.clear()
            self.log(f"截图文件不存在: {img_path}", level="warning")

    def save_position_info(self):
        """保存持仓信息"""
        if hasattr(self, 'empty_pos_checkbox') and self.empty_pos_checkbox.isChecked():
            self.log("持仓信息已保存: 空仓（无持仓）", level="info")
            return
        info = self.position_info_widget.get_position_info_text() if hasattr(self.position_info_widget, 'get_position_info_text') else str(self.position_info_widget)
        self.log(f"持仓信息已保存: {info}", level="info")

    def on_empty_pos_changed(self, state):
        """空仓复选框状态变更处理"""
        is_empty = (state == Qt.CheckState.Checked.value)
        self.position_info_widget.setEnabled(not is_empty)
        if is_empty:
            self.log("已选择空仓，持仓输入已禁用。", level="info")
        else:
            self.log("取消空仓选项，可以填写持仓信息。", level="info")

    def save_api_key(self, key):
        """保存API Key到本地配置"""
        self.settings.setValue("gemini_api_key", key)
        import os
        os.environ["GEMINI_API_KEY"] = key

    def get_api_key(self):
        """获取API Key"""
        return self.api_key_input.text().strip()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = QuantAssistant()
    win.show()
    sys.exit(app.exec())
