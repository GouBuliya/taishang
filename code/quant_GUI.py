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
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication, QPixmap, QIcon


from position_info_widget import PositionInfoWidget


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
        self.upload_button = QPushButton("3. 从剪切板获取截图")
        self.upload_button.clicked.connect(self.upload_screenshot_from_clipboard)
        self.gemini_advice_button = QPushButton("4. 让Gemini给出操作建议")
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
        btn_row1_layout = QHBoxLayout()
        btn_row1_layout.addWidget(self.run_button)
        btn_row1_layout.addWidget(self.copy_output_button)
        btn_card_layout.addLayout(btn_row1_layout)
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
        self.log_output.append(f"[{now}] {message}")
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
        current_stdout = None
        total_fake_steps = 5

        try:
            self._show_fake_progress_bar(0, total_fake_steps, "(初始化...)")
            time.sleep(0.15)

            BASE_DIR = os.path.dirname(os.path.abspath(__file__))
            main_path = os.path.join(BASE_DIR, "main.py")

            if not os.path.exists(main_path):
                self.log(f"错误: 脚本 'main.py' 未在路径 '{main_path}' 找到。")
                self._show_fake_progress_bar(total_fake_steps, total_fake_steps, "(脚本未找到 - 失败!)")
                return

            self._show_fake_progress_bar(1, total_fake_steps, "(准备启动脚本...)")
            time.sleep(0.15)

            process = subprocess.Popen(
                [sys.executable, main_path],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                encoding='utf-8'
            )
            
            self._show_fake_progress_bar(2, total_fake_steps, "(脚本已启动，等待执行完成...)")
            stdout, stderr = process.communicate(timeout=60)

            self._show_fake_progress_bar(3, total_fake_steps, "(脚本执行完毕，处理结果...)")
            time.sleep(0.15)

            if stdout:
                current_stdout = stdout.strip()
                self.last_script_stdout = current_stdout
            
            self.show_script_output(current_stdout if current_stdout is not None else "")

            if stderr:
                self.log(f"脚本错误输出 (stderr):\n{stderr.strip()}")
            
            self._show_fake_progress_bar(4, total_fake_steps, "(检查执行状态...)")
            time.sleep(0.15)

            if process.returncode == 0:
                self.log("脚本执行成功。")
                self._show_fake_progress_bar(total_fake_steps, total_fake_steps, "(成功完成)")
            else:
                self.log(f"脚本执行失败，返回码: {process.returncode}")
                self._show_fake_progress_bar(total_fake_steps, total_fake_steps, "(执行失败)")

        except FileNotFoundError:
            self.log(f"错误: 无法找到Python解释器或脚本。")
            self._show_fake_progress_bar(total_fake_steps, total_fake_steps, "(文件未找到 - 失败!)")
        except subprocess.TimeoutExpired:
            self.log("脚本执行超时。")
            if 'process' in locals() and process: process.kill()
            self.show_script_output(None)
            self._show_fake_progress_bar(total_fake_steps, total_fake_steps, "(超时 - 失败!)")
        except Exception as e:
            self.log(f"运行脚本时发生异常: {e}")
            self.show_script_output(None)
            self._show_fake_progress_bar(total_fake_steps, total_fake_steps, "(发生异常 - 失败!)")

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

    def closeEvent(self, event):
        if self.temp_screenshot_path and os.path.exists(self.temp_screenshot_path):
            try: os.remove(self.temp_screenshot_path)
            except Exception as e: self.log(f"关闭时清理临时截图失败: {e}")
        super().closeEvent(event)

    def gemini_advice_action(self):
        self.log("正在准备向Gemini请求建议...")
        all_info = self.collect_all_info_as_json()
        import json
        self.log(f"收集到的信息: {json.dumps(all_info, indent=2, ensure_ascii=False)}")
        self.gemini_reply_box.setPlainText("Gemini 操作建议功能暂未实现。\n收集到的信息已打印到日志。")
        self.log("[Gemini] 操作建议功能暂未实现。")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = QuantAssistant()
    win.show()
    sys.exit(app.exec())