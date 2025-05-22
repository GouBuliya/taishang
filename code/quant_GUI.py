# QuantAssistant.py
import sys
import os
import subprocess
import tempfile
from datetime import datetime
import time 
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout,
    QLineEdit, QTextEdit, QCheckBox, QHBoxLayout, QSizePolicy, QFrame,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QGuiApplication, QPixmap, QIcon


from position_info_widget import PositionInfoWidget


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

class QuantAssistant(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("gemini金融智能体")
        # 修正：用绝对路径加载icon.png
        base_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(base_dir, "icon.png")
        self.setWindowIcon(QIcon(icon_path))
        self.resize(1592, 928)

        self.temp_screenshot_path = None
        self.last_script_stdout = None

        self.empty_pos_checkbox = QCheckBox("空仓（无持仓）")
        self.empty_pos_checkbox.setChecked(True)
        self.empty_pos_checkbox.stateChanged.connect(self.toggle_position_inputs)
        
        self.position_info_widget = PositionInfoWidget()

        self.total_usdt_input = self.position_info_widget.total_usdt_input
        self.pos_percent_input = self.position_info_widget.pos_percent_input
        self.pos_dir_checkbox = self.position_info_widget.pos_dir_checkbox
        self.pos_dir_checkbox2 = self.position_info_widget.pos_dir_checkbox2
        self.open_price_input = self.position_info_widget.open_price_input
        self.stop_loss_input = self.position_info_widget.stop_loss_input

        self.pos_dir_checkbox.stateChanged.connect(
            lambda state: self._handle_pos_dir_change(self.pos_dir_checkbox, self.pos_dir_checkbox2, state)
        )
        self.pos_dir_checkbox2.stateChanged.connect(
            lambda state: self._handle_pos_dir_change(self.pos_dir_checkbox2, self.pos_dir_checkbox, state)
        )

        self.run_button = QPushButton("1. 运行指标及宏观因子脚本")
        self.run_button.clicked.connect(self.run_main_scripts)
        self.copy_output_button = QPushButton("2. 复制脚本输出到剪切板")
        self.copy_output_button.clicked.connect(self.copy_script_output_to_clipboard)
        self.upload_button = QPushButton("从剪切板获取截图")
        self.upload_button.clicked.connect(self.upload_screenshot_from_clipboard)
        self.gemini_advice_button = QPushButton("让Gemini给出操作建议")
        self.gemini_advice_button.clicked.connect(self.gemini_advice_action)
        
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)

        main_layout = QHBoxLayout()
        main_layout.setSpacing(24)
        main_layout.setContentsMargins(20, 20, 20, 20)

        left_col = QVBoxLayout()
        left_col.setSpacing(18)
        left_col.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        main_title = QLabel("Gemini金融智能体")
        main_title.setObjectName("MainTitle")
        left_col.addWidget(main_title, alignment=Qt.AlignmentFlag.AlignHCenter)
        
        input_card = QFrame()
        input_card.setObjectName("Card")
        input_card_layout = QVBoxLayout(input_card)
        input_card_layout.addWidget(self.empty_pos_checkbox)
        input_card_layout.addWidget(self.position_info_widget)
        left_col.addWidget(input_card)
        
        btn_card = QFrame()
        btn_card.setObjectName("Card") 
        btn_card_layout = QVBoxLayout(btn_card)
        btn_row2_layout = QHBoxLayout()
        btn_row2_layout.addWidget(self.upload_button)
        btn_row2_layout.addWidget(self.gemini_advice_button)
        btn_card_layout.addLayout(btn_row2_layout)
        left_col.addWidget(btn_card)
        
        log_card = QFrame()
        log_card.setObjectName("Card")
        log_card_layout = QVBoxLayout(log_card)
        log_title = QLabel("日志与脚本输出：")
        log_title.setObjectName("SectionTitle")
        log_card_layout.addWidget(log_title)
        self.log_output.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.log_output.setMinimumHeight(150)
        log_card_layout.addWidget(self.log_output)
        left_col.addWidget(log_card)
        
        # API Key输入框及自动保存
        from PyQt6.QtCore import QSettings
        self.settings = QSettings("GeminiQuant", "GeminiQuantApp")
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("输入Gemini API Key（已废用）")
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        saved_key = self.settings.value("gemini_api_key", "")
        self.api_key_input.setText(saved_key)
        self.api_key_input.textChanged.connect(self.save_api_key)
        
        left_col.addWidget(QLabel("Gemini API Key:"))
        left_col.addWidget(self.api_key_input)
        
        left_col.addStretch(1)

        right_col = QVBoxLayout()
        right_col.setSpacing(18)
        right_col.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        img_card = QFrame()
        img_card.setObjectName("Card")
        img_card_layout = QVBoxLayout(img_card)
        img_title = QLabel("Gemini对话区：")
        img_title.setObjectName("SectionTitle")
        img_card_layout.addWidget(img_title)
        
        self.gemini_reply_box = QTextEdit()
        self.gemini_reply_box.setReadOnly(True)
        self.gemini_reply_box.setMinimumHeight(220)
        self.gemini_reply_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.gemini_reply_box.setPlaceholderText("此处将显示Gemini的AI回复/建议……")
        img_card_layout.addWidget(self.gemini_reply_box)
        
        right_col.addWidget(img_card, 1) 
        right_col.addStretch(0) 

        main_layout.addLayout(left_col, 2)
        main_layout.addLayout(right_col, 3)
        self.setLayout(main_layout)

        self.setStyleSheet('''
            QWidget {
                font-family: 'Segoe UI', 'Microsoft YaHei', Arial, sans-serif;
                font-size: 15px;
                background: #ECF0F1; 
                color: #2C3E50; 
            }
            QFrame#Card {
                background: #FFFFFF; 
                border-radius: 10px; 
                border: 1px solid #D5D8DC; 
                padding: 16px 22px;
                margin-bottom: 16px;
            }
            /* Removed: QFrame#Card QWidget { background-color: #FFFFFF; border: none; } */
            /* Child QWidgets inside QFrame#Card will now inherit or have transparent background by default,
               showing the #FFFFFF of the QFrame#Card. Specific widgets like PositionInfoWidget
               should appear correctly on the white card background. */

            QLabel#MainTitle {
                color: #2C3E50; 
                font-size: 26px;
                font-weight: 600;
                letter-spacing: 1px;
                margin-bottom: 16px;
                background: transparent; 
            }
            QLabel#SectionTitle {
                color: #E74C3C; 
                font-size: 17px;
                font-weight: 600;
                margin-bottom: 6px;
                background: transparent; 
            }
            QPushButton {
                background-color: #E74C3C; /* Explicitly background-color */
                color: #FFFFFF; 
                border: 1px solid #C0392B; 
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: 600;
                font-size: 15px;
                margin: 6px 4px; 
            }
            QPushButton:hover {
                background-color: #C0392B; 
                border-color: #A93226; 
            }
            QPushButton:pressed {
                background-color: #A93226; 
            }
            QTextEdit, QLineEdit {
                border: 1px solid #95A5A6; 
                border-radius: 6px;
                background: #FFFFFF; 
                color: #2C3E50; 
                font-size: 15px;
                padding: 7px 10px;
            }
            QTextEdit:focus, QLineEdit:focus {
                border-color: #E74C3C; 
                box-shadow: 0 0 0 0.2rem rgba(231, 76, 60, 0.25); 
            }
            QTextEdit[readOnly="true"] {
                background: #FDFEFE; 
                color: #34495E; 
                border: 1px solid #BDC3C7; 
            }
            QCheckBox {
                font-size: 15px;
                color: #2C3E50; 
                spacing: 5px;
                background: transparent; 
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            QLabel { 
                font-size: 15px;
                color: #2C3E50; 
                padding-top: 2px;
                padding-bottom: 2px;
                background: transparent; 
            }
        ''')
        self.log_output.setStyleSheet( 
            "background: #34495E; " 
            "border: 1px solid #2C3E50; " 
            "border-radius: 6px; "
            "font-size: 14px; "
            "padding: 8px 12px; "
            "color: #ECF0F1; " 
            "font-family: 'Consolas', 'Courier New', monospace;"
        )
        self.gemini_reply_box.setStyleSheet(
            "background: #FFFFFF; " 
            "border: 1px solid #95A5A6; "
            "color: #2C3E50; "
            "border-radius: 6px; "
            "font-size: 15px; "
            "padding: 7px 10px;"
        )

    def _handle_pos_dir_change(self, changed_checkbox, other_checkbox, state):
        if state == Qt.CheckState.Checked.value:
            if changed_checkbox.isChecked():
                other_checkbox.setChecked(False)

    def toggle_position_inputs(self, state):
        is_empty_pos = (state == Qt.CheckState.Checked.value)
        
        self.total_usdt_input.setEnabled(not is_empty_pos)
        self.pos_percent_input.setEnabled(not is_empty_pos)
        self.pos_dir_checkbox.setEnabled(not is_empty_pos)
        self.pos_dir_checkbox2.setEnabled(not is_empty_pos)
        self.open_price_input.setEnabled(not is_empty_pos)
        self.stop_loss_input.setEnabled(not is_empty_pos)
        
        if is_empty_pos:
            self.total_usdt_input.clear()
            self.pos_percent_input.clear()
            self.open_price_input.clear()
            self.stop_loss_input.clear()
            self.pos_dir_checkbox.setChecked(True)
            self.pos_dir_checkbox2.setChecked(False)
            self.log("已选择空仓，持仓输入已禁用并清空。")
        else:
            self.log("取消空仓选项，可以填写持仓信息。")

    def log(self, message):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{now}] {message}"
        self.log_output.append(log_line)
        print(log_line)
        QApplication.processEvents()

    def show_script_output(self, output):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if output and output.strip():
            self.log_output.append(f"[{now}] --- SCRIPT OUTPUT START ---")
            self.log_output.append(output)
            self.log_output.append(f"[{now}] --- SCRIPT OUTPUT END ---")
        elif output == "":
            self.log_output.append(f"[{now}] --- SCRIPT OUTPUT (EMPTY) ---")
        QApplication.processEvents()

    def _show_fake_progress_bar(self, current_step, total_steps, message=""):
        bar_length = 20
        actual_step = min(current_step, total_steps)
        filled_length = int(bar_length * actual_step / total_steps)
        bar = '█' * filled_length + '░' * (bar_length - filled_length)
        progress_percentage = int((actual_step / total_steps) * 100)
        self.log(f"进度: [{bar}] {progress_percentage}% {message}")

    def run_main_scripts(self):
        self.log("开始运行主脚本 (指标收集和宏观因子)...")
        self.last_script_stdout = None
        self._progress_timer = QTimer(self)
        self._progress_timer.timeout.connect(self._on_progress_timer)
        self._progress_value = 0
        self._progress_max = 80  # 脚本执行期间最多推进到80%
        self._progress_timer.start(180)  # 每180ms推进一次
        self._show_fake_progress_bar(self._progress_value, 100, "(初始化...)")
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        main_path = os.path.join(BASE_DIR, "main.py")
        if not os.path.exists(main_path):
            self.log(f"错误: 脚本 'main.py' 未在路径 '{main_path}' 找到。")
            self._progress_timer.stop()
            self._show_fake_progress_bar(100, 100, "(脚本未找到 - 失败!)")
            return
        self.script_thread = ScriptRunnerThread(main_path)
        self.script_thread.result_signal.connect(self._on_script_finished)
        self.script_thread.start()

    def _on_progress_timer(self):
        if self._progress_value < self._progress_max:
            self._progress_value += 2
            if self._progress_value > self._progress_max:
                self._progress_value = self._progress_max
            self._show_fake_progress_bar(self._progress_value, 100, "(执行中...)")
        else:
            self._progress_timer.stop()

    def _on_script_finished(self, stdout, stderr, returncode):
        self._progress_timer.stop()
        self._progress_value = 80
        self._show_fake_progress_bar(self._progress_value, 100, "(脚本执行完毕，处理结果...)")
        if stdout:
            self.last_script_stdout = stdout.strip()
            self.show_script_output(self.last_script_stdout)
        else:
            self.show_script_output("")
        if stderr:
            self.log(f"脚本错误输出 (stderr):\n{stderr.strip()}")
        self._progress_value = 100
        self._show_fake_progress_bar(self._progress_value, 100, "(成功完成)" if returncode == 0 else "(执行失败)")
        if returncode == 0:
            self.log("脚本执行成功。")
        else:
            self.log(f"脚本执行失败，返回码: {returncode}")

    def copy_script_output_to_clipboard(self):
        output_to_copy = self.last_script_stdout
        if output_to_copy and output_to_copy.strip():
            try:
                QGuiApplication.clipboard().setText(output_to_copy)
                self.log("最后一次脚本输出已成功复制到剪切板。")
            except Exception as e: self.log(f"复制到剪切板失败: {e}")
        else:
            self.log("没有可复制的脚本输出 (最后一次脚本运行无输出、未运行或运行失败)。")

    def upload_screenshot_from_clipboard(self):
        clipboard = QGuiApplication.clipboard()
        mime_data = clipboard.mimeData()

        if mime_data.hasImage():
            qimage = clipboard.image()
            if not qimage.isNull():
                if self.temp_screenshot_path and os.path.exists(self.temp_screenshot_path):
                    try: os.remove(self.temp_screenshot_path)
                    except Exception as e: self.log(f"删除旧临时截图失败: {e}")
                
                temp_dir = tempfile.gettempdir()
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                self.temp_screenshot_path = os.path.join(temp_dir, f"cs_{timestamp}.png")
                
                try:
                    if qimage.save(self.temp_screenshot_path):
                        self.log(f"剪切板图片已保存: {self.temp_screenshot_path}")
                    else:
                        self.log("错误：保存剪切板图片失败。")
                        self.temp_screenshot_path = None
                except Exception as e:
                    self.log(f"保存图片错误: {e}")
                    self.temp_screenshot_path = None
            else:
                self.log("剪切板图片无效。")
        else:
            self.log("剪切板中无图片。")

    def get_position_info_text(self):
        if hasattr(self.position_info_widget, 'get_position_info_text'):
            return self.position_info_widget.get_position_info_text()
        
        if self.empty_pos_checkbox.isChecked(): return "空仓（无持仓）"
        direction = "做多" if self.pos_dir_checkbox.isChecked() else "做空" if self.pos_dir_checkbox2.isChecked() else "未指定"
        return (f"总资金: {self.total_usdt_input.text()} USDT, 仓位: {self.pos_percent_input.text()}%, "
                f"方向: {direction}, 开仓价: {self.open_price_input.text()}, 止损价: {self.stop_loss_input.text()}")

    def collect_all_info_as_json(self):
        info = {
            "total_usdt": self.total_usdt_input.text().strip(),
            "position_percent": self.pos_percent_input.text().strip(),
            "direction": "long" if self.pos_dir_checkbox.isChecked() else ("short" if self.pos_dir_checkbox2.isChecked() else "none"),
            "open_price": self.open_price_input.text().strip(),
            "stop_loss": self.stop_loss_input.text().strip(),
            "is_empty": self.empty_pos_checkbox.isChecked(),
            "clipboard_image_path": self.temp_screenshot_path,
            "script_output": self.last_script_stdout,
            "timestamp": datetime.now().isoformat(),
        }
        return info

    def package_position_and_main_output(self, main_output_json_str=None):
        """
        将当前持仓信息和 main.py 返回的 JSON（字符串）打包成一个总的 JSON 对象。
        main_output_json_str: main.py 脚本输出的 JSON 字符串（如无则取 self.last_script_stdout）
        返回: dict
        """
        import json
        # 1. 获取持仓信息
        position_info = self.collect_all_info_as_json()
        # 2. 获取 main.py 输出
        if main_output_json_str is None:
            main_output_json_str = self.last_script_stdout
        try:
            main_output = json.loads(main_output_json_str) if main_output_json_str else None
        except Exception as e:
            main_output = {"error": f"main.py输出解析失败: {e}", "raw": main_output_json_str}
        # 3. 打包
        result = {
            "position_info": position_info,
            "main_output": main_output,
            "timestamp": datetime.now().isoformat()
        }
        return result

    def closeEvent(self, event):
        if self.temp_screenshot_path and os.path.exists(self.temp_screenshot_path):
            try: os.remove(self.temp_screenshot_path)
            except Exception as e: self.log(f"关闭时清理临时截图失败: {e}")
        super().closeEvent(event)

    def format_gemini_json_reply(self, reply_text):
        import json
        try:
            data = json.loads(reply_text)
        except Exception:
            return reply_text  # 非JSON直接返回
        lines = []
        # 主要字段映射
        mapping = {
            'short_term_reason': '短线分析',
            'mid_term_reason': '中线分析',
            'long_term_reason': '长线分析',
            'vp_analysis': '成交量分布',
            'volume_analysis': '量能分析',
            'price_action': '价格行为',
            'summary': '总结',
            'entry_condition': '入场条件',
            'stop_loss': '止损',
            'take_profit': '止盈目标',
            'risk_management': '风控建议',
            'position_action': '持仓调整',
            'MARKET': '市场状态',
            'symbol': '交易对',
            'timeframe': '周期',
        }
        for k, label in mapping.items():
            v = data.get(k, None)
            if v is not None:
                if isinstance(v, list):
                    v = ', '.join(str(i) for i in v)
                lines.append(f"{label}：{v}")
        # operation子字段
        op = data.get('operation', {})
        if isinstance(op, dict):
            op_map = {
                'type': '操作类型',
                'price': '挂单价格',
                'stop_loss': '止损',
                'take_profit': '止盈目标',
                'size': '仓位大小',
                'expected_winrate': '预计胜率',
                'expected_return': '期望收益',
                'confidence': 'AI置信度',
                'signal_strength': '信号强度',
                'comment': '补充说明',
            }
            for k, label in op_map.items():
                v = op.get(k, None)
                if v is not None:
                    if isinstance(v, list):
                        v = ', '.join(str(i) for i in v)
                    lines.append(f"{label}：{v}")
        return '\n'.join(lines) if lines else reply_text

    def gemini_advice_action(self):
        self.log("正在准备向Gemini请求建议...")
        all_info = self.collect_all_info_as_json()
        import json
        self.log(f"收集到的信息: {json.dumps(all_info, indent=2, ensure_ascii=False)}")
        screenshot_path = all_info.get("clipboard_image_path") if all_info.get("clipboard_image_path") else None
        if hasattr(self, 'package_position_and_main_output'):
            packaged = self.package_position_and_main_output()
        else:
            packaged = all_info
        api_key = self.get_api_key() if hasattr(self, 'get_api_key') else None
        self.log(f"[DEBUG] 当前API Key: {api_key}")
        self.log("正在调用Gemini API...")
        self.gemini_reply_box.setPlainText("Gemini正在推理中，请稍候...")
        self.gemini_thread = GeminiAPICallThread(packaged, screenshot_path, api_key)
        self.gemini_thread.result_signal.connect(self.on_gemini_reply)
        self.gemini_thread.start()

    def on_gemini_reply(self, reply, error):
        if error:
            self.gemini_reply_box.setPlainText(f"Gemini 操作建议功能出错: {error}")
            self.log(f"[Gemini] 操作建议功能出错: {error}")
        else:
            try:
                import importlib.util
                import os
                import json
                base_dir = os.path.dirname(os.path.abspath(__file__))
                md_path = os.path.join(base_dir, "gemini_json_to_markdown.py")
                spec = importlib.util.spec_from_file_location("gemini_json_to_markdown", md_path)
                md_mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(md_mod)
                # 保证 reply 一定是 str
                if not isinstance(reply, str):
                    reply = json.dumps(reply, ensure_ascii=False, indent=2)
                markdown = md_mod.gemini_json_to_markdown(reply)
                self.gemini_reply_box.setMarkdown(markdown)
            except Exception as e:
                self.gemini_reply_box.setPlainText(f"[格式化/渲染Markdown失败] 原始回复如下:\n{reply}\n错误: {e}")
            self.log("Gemini回复已显示。")

    def save_api_key(self, key):
        self.settings.setValue("gemini_api_key", key)
        # 自动设置为环境变量（仅当前进程有效）
        import os
        os.environ["GEMINI_API_KEY"] = key

    def get_api_key(self):
        return self.api_key_input.text().strip()

if __name__ == "__main__":
    print("main entry")
    app = QApplication(sys.argv)
    win = QuantAssistant()
    win.show()
    sys.exit(app.exec())
