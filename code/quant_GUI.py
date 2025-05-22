# quant_GUI.py
from quant_main_window import QuantAssistantMainWindow
from quant_logic import QuantLogicMixin
from quant_utils import collect_all_info_as_json, package_position_and_main_output, get_position_info_text
from quant_actions import gemini_advice_action, save_api_key, get_api_key, closeEvent
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QPushButton, QFrame, QVBoxLayout, QHBoxLayout, QMessageBox

class QuantAssistant(QuantAssistantMainWindow, QuantLogicMixin):
    collect_all_info_as_json = collect_all_info_as_json
    package_position_and_main_output = package_position_and_main_output
    get_position_info_text = get_position_info_text
    gemini_advice_action = gemini_advice_action
    save_api_key = save_api_key
    get_api_key = get_api_key
    closeEvent = closeEvent

    def __init__(self):
        super().__init__()
        import os
        from PyQt6.QtGui import QGuiApplication
        from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QFrame, QPushButton
        # 信号与槽绑定
        self.empty_pos_checkbox.stateChanged.connect(self.toggle_position_inputs)
        self.pos_dir_checkbox.stateChanged.connect(
            lambda state: self._handle_pos_dir_change(self.pos_dir_checkbox, self.pos_dir_checkbox2, state)
        )
        self.pos_dir_checkbox2.stateChanged.connect(
            lambda state: self._handle_pos_dir_change(self.pos_dir_checkbox2, self.pos_dir_checkbox, state)
        )
        # 按钮重构
        self.run_button = QPushButton("1. 运行宏观因子与技术指标采集")
        self.run_button.clicked.connect(self.run_main_scripts)
        self.upload_button = QPushButton("2. 从剪切板获取截图")
        self.upload_button.clicked.connect(self.upload_screenshot_from_clipboard)
        self.gemini_advice_button = QPushButton("3. 让Gemini给出操作建议")
        self.gemini_advice_button.clicked.connect(self.gemini_advice_action)
        # 重新布局按钮
        btn_card = QFrame()
        btn_card.setObjectName("Card")
        btn_card_layout = QVBoxLayout(btn_card)
        btn_row1_layout = QHBoxLayout()
        btn_row1_layout.addWidget(self.run_button)
        btn_card_layout.addLayout(btn_row1_layout)
        btn_row2_layout = QHBoxLayout()
        btn_row2_layout.addWidget(self.upload_button)
        btn_row2_layout.addWidget(self.gemini_advice_button)
        btn_card_layout.addLayout(btn_row2_layout)
        # 重新插入到布局
        if hasattr(self, 'main_layout') and hasattr(self, 'left_col'):
            self.left_col.addWidget(btn_card)
        # api_key自动保存
        self.api_key_input.textChanged.connect(self.save_api_key)

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

    def gemini_advice_action(self):
        import os
        from PyQt6.QtGui import QGuiApplication
        from PyQt6.QtWidgets import QMessageBox
        self.log("正在准备向Gemini请求建议...")
        # 1. 运行main.py采集数据
        self.run_main_scripts()
        # 2. 等待脚本执行完毕（同步/异步处理）
        import time
        for _ in range(30):
            if self.last_script_stdout:
                break
            time.sleep(0.2)
        if not self.last_script_stdout:
            self.log("未获取到脚本输出，无法继续。")
            return
        # 3. 复制数据到剪切板
        QGuiApplication.clipboard().setText(self.last_script_stdout)
        self.log("脚本输出已复制到剪切板。")
        # 4. 检查截图
        screenshot_path = self.temp_screenshot_path
        if not screenshot_path or not os.path.exists(screenshot_path):
            ret = QMessageBox.warning(self, "缺少截图", "未检测到截图，Gemini多模态推理建议配合K线图片。\n如执意继续请点击“确定”，否则请先上传截图。", QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
            if ret == QMessageBox.StandardButton.Cancel:
                self.log("用户取消了无图推理。")
                return
            else:
                self.log("用户选择无图继续推理。")
                screenshot_path = None
        # 5. 打包数据并调用Gemini
        if hasattr(self, 'package_position_and_main_output'):
            packaged = self.package_position_and_main_output()
        else:
            packaged = self.collect_all_info_as_json()
        api_key = self.get_api_key() if hasattr(self, 'get_api_key') else None
        try:
            import sys
            import importlib
            base_dir = os.path.dirname(os.path.abspath(__file__))
            sys.path.insert(0, base_dir)
            gemini_api_caller = importlib.import_module("gemini_api_caller")
            call_gemini_api = gemini_api_caller.call_gemini_api
            self.log("正在调用Gemini API...")
            reply = call_gemini_api(packaged, screenshot_path=screenshot_path, api_key=api_key)
            self.gemini_reply_box.setPlainText(reply)
            self.log("Gemini回复已显示。")
        except Exception as e:
            self.gemini_reply_box.setPlainText(f"Gemini 操作建议功能出错: {e}\n收集到的信息已打印到日志。")
            self.log(f"[Gemini] 操作建议功能出错: {e}")

if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    print("main entry")
    app = QApplication(sys.argv)
    win = QuantAssistant()
    win.show()
    sys.exit(app.exec())
