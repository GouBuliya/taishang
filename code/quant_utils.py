from datetime import datetime
import os
import json

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
    position_info = self.collect_all_info_as_json()
    if main_output_json_str is None:
        main_output_json_str = self.last_script_stdout
    try:
        main_output = json.loads(main_output_json_str) if main_output_json_str else None
    except Exception as e:
        main_output = {"error": f"main.py输出解析失败: {e}", "raw": main_output_json_str}
    result = {
        "position_info": position_info,
        "main_output": main_output,
        "timestamp": datetime.now().isoformat()
    }
    return result

def get_position_info_text(self):
    if hasattr(self.position_info_widget, 'get_position_info_text'):
        return self.position_info_widget.get_position_info_text()
    if self.empty_pos_checkbox.isChecked(): return "空仓（无持仓）"
    direction = "做多" if self.pos_dir_checkbox.isChecked() else "做空" if self.pos_dir_checkbox2.isChecked() else "未指定"
    return (f"总资金: {self.total_usdt_input.text()} USDT, 仓位: {self.pos_percent_input.text()}%, "
            f"方向: {direction}, 开仓价: {self.open_price_input.text()}, 止损价: {self.stop_loss_input.text()}")
