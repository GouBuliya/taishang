from PyQt6.QtCore import QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QGuiApplication
import tempfile
import os
from datetime import datetime

class ScriptRunnerThread(QThread):
    result_signal = pyqtSignal(str, str, int)
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

class QuantLogicMixin:
    def log(self, message):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_output.append(f"[{now}] {message}")
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()

    def show_script_output(self, output):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if output and output.strip():
            self.log_output.append(f"[{now}] --- SCRIPT OUTPUT START ---")
            self.log_output.append(output)
            self.log_output.append(f"[{now}] --- SCRIPT OUTPUT END ---")
        elif output == "":
            self.log_output.append(f"[{now}] --- SCRIPT OUTPUT (EMPTY) ---")
        from PyQt6.QtWidgets import QApplication
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
        self._progress_max = 80
        self._progress_timer.start(180)
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
