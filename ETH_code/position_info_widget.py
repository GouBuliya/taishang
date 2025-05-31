from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QCheckBox
from PyQt6.QtCore import Qt
from datetime import datetime

class PositionInfoWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.total_usdt_input = QLineEdit()
        self.total_usdt_input.setPlaceholderText("如 10000")
        total_usdt_hbox = QHBoxLayout()
        total_usdt_label = QLabel("总仓位（USDT）：")
        total_usdt_hbox.addWidget(total_usdt_label)
        total_usdt_hbox.addWidget(self.total_usdt_input)
        self.layout.addLayout(total_usdt_hbox)

        self.pos_percent_input = QLineEdit()
        self.pos_percent_input.setPlaceholderText("如 30，代表30%")
        pos_percent_hbox = QHBoxLayout()
        pos_percent_label = QLabel("当前仓位百分比：")
        pos_percent_hbox.addWidget(pos_percent_label)
        pos_percent_hbox.addWidget(self.pos_percent_input)
        self.layout.addLayout(pos_percent_hbox)

        self.pos_dir_checkbox = QCheckBox("多仓")
        self.pos_dir_checkbox.setChecked(True)
        self.pos_dir_checkbox2 = QCheckBox("空仓")
        self.pos_dir_checkbox2.setChecked(False)
        self.pos_dir_checkbox.stateChanged.connect(lambda s: self._sync_dir_checkbox(True))
        self.pos_dir_checkbox2.stateChanged.connect(lambda s: self._sync_dir_checkbox(False))
        pos_dir_hbox = QHBoxLayout()
        pos_dir_label = QLabel("方向：")
        pos_dir_hbox.addWidget(pos_dir_label)
        pos_dir_hbox.addWidget(self.pos_dir_checkbox)
        pos_dir_hbox.addWidget(self.pos_dir_checkbox2)
        self.layout.addLayout(pos_dir_hbox)

        self.open_price_input = QLineEdit()
        self.open_price_input.setPlaceholderText("如 2500.00")
        open_price_hbox = QHBoxLayout()
        open_price_label = QLabel("开仓均价：")
        open_price_hbox.addWidget(open_price_label)
        open_price_hbox.addWidget(self.open_price_input)
        self.layout.addLayout(open_price_hbox)

        self.stop_loss_input = QLineEdit()
        self.stop_loss_input.setPlaceholderText("如 2400.00，可不填")
        stop_loss_hbox = QHBoxLayout()
        stop_loss_label = QLabel("当前止损价（可选）：")
        stop_loss_hbox.addWidget(stop_loss_label)
        stop_loss_hbox.addWidget(self.stop_loss_input)
        self.layout.addLayout(stop_loss_hbox)

    def _sync_dir_checkbox(self, is_long):
        if is_long:
            if self.pos_dir_checkbox.isChecked():
                self.pos_dir_checkbox2.setChecked(False)
        else:
            if self.pos_dir_checkbox2.isChecked():
                self.pos_dir_checkbox.setChecked(False)

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
        
    def get_position_info_text(self):
        # 由主界面统一控制空仓逻辑，这里不再判断self.empty_pos_checkbox
        total_usdt_str = self.total_usdt_input.text().strip()
        percent_str = self.pos_percent_input.text().strip()
        open_price_str = self.open_price_input.text().strip()
        stop_loss_str = self.stop_loss_input.text().strip()
        direction = None
        if self.pos_dir_checkbox.isChecked():
            direction = "多"
        elif self.pos_dir_checkbox2.isChecked():
            direction = "空"
        else:
            direction = "未选择方向"
        if not total_usdt_str:
            return "当前持仓：[未填写总仓位USDT]"
        try:
            total_usdt_val = float(total_usdt_str)
        except ValueError:
            return "当前持仓：[总仓位USDT无效]"
        if not percent_str:
            return f"当前持仓：总仓位 {total_usdt_val} USDT，当前仓位百分比[未填写]"
        try:
            percent_val = float(percent_str)
        except ValueError:
            return f"当前持仓：总仓位 {total_usdt_val} USDT，当前仓位百分比[无效]"
        if not open_price_str:
            return f"当前持仓：总仓位 {total_usdt_val} USDT，{direction} 仓位 {percent_val}% ，开仓均价 [未填写]"
        try:
            open_price_val = float(open_price_str)
        except ValueError:
            return f"当前持仓：总仓位 {total_usdt_val} USDT，{direction} 仓位 {percent_val}% ，开仓均价 [无效]"
        info = f"当前持仓：总仓位 {total_usdt_val} USDT，{direction} 仓位 {percent_val}% ，开仓均价 {open_price_val}"
        if stop_loss_str:
            try:
                stop_loss_val = float(stop_loss_str)
                info += f"，当前止损 {stop_loss_val}"
            except ValueError:
                info += f"，当前止损 [无效]"
        return info

    def collect_info_as_json(self):
        return {
            "total_usdt": self.total_usdt_input.text().strip(),
            "position_percent": self.pos_percent_input.text().strip(),
            "direction": "long" if self.pos_dir_checkbox.isChecked() else ("short" if self.pos_dir_checkbox2.isChecked() else "none"),
            "open_price": self.open_price_input.text().strip(),
            "stop_loss": self.stop_loss_input.text().strip(),
            "is_empty": self.empty_pos_checkbox.isChecked(),
        }
