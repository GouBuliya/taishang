import os
import importlib
import json

def gemini_advice_action(self):
    self.log("正在准备向Gemini请求建议...")
    all_info = self.collect_all_info_as_json()
    self.log(f"收集到的信息: {json.dumps(all_info, indent=2, ensure_ascii=False)}")
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        import sys
        sys.path.insert(0, base_dir)
        gemini_api_caller = importlib.import_module("gemini_api_caller")
        call_gemini_api = gemini_api_caller.call_gemini_api
        screenshot_path = all_info.get("clipboard_image_path") if all_info.get("clipboard_image_path") else None
        if hasattr(self, 'package_position_and_main_output'):
            packaged = self.package_position_and_main_output()
        else:
            packaged = all_info
        api_key = self.get_api_key() if hasattr(self, 'get_api_key') else None
        self.log(f"[DEBUG] 当前API Key: {api_key}")
        self.log("正在调用Gemini API...")
        reply = call_gemini_api(packaged, screenshot_path=screenshot_path, api_key=api_key)
        self.gemini_reply_box.setPlainText(reply)
        self.log("Gemini回复已显示。")
    except Exception as e:
        self.gemini_reply_box.setPlainText(f"Gemini 操作建议功能出错: {e}\n收集到的信息已打印到日志。")
        self.log(f"[Gemini] 操作建议功能出错: {e}")

def save_api_key(self, key):
    self.settings.setValue("gemini_api_key", key)
    import os
    os.environ["GEMINI_API_KEY"] = key

def get_api_key(self):
    return self.api_key_input.text().strip()

def closeEvent(self, event):
    if self.temp_screenshot_path and os.path.exists(self.temp_screenshot_path):
        try: os.remove(self.temp_screenshot_path)
        except Exception as e: self.log(f"关闭时清理临时截图失败: {e}")
    super().closeEvent(event)
