# app.py
from flask import Flask, jsonify, request, render_template, Response, send_from_directory
import subprocess
import os
import json
import logging
import sys
import traceback
from werkzeug.exceptions import UnsupportedMediaType # 导入特定的异常类型
import threading
from telegram_bot_singleton import start_telegram_bot

# 确保可以导入 gemini_api_caller
# 根据您的路径结构，可能需要调整 sys.path
# 假设 app.py 在 web_gui 目录下，gemini_api_caller.py 在 web_gui 的父目录 (code 目录)
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.join(current_dir, '..')
sys.path.insert(0, parent_dir)

import gemini_api_caller # 导入修改后的流式函数

# 将模板文件夹设置为 'templates'，而不是 'static'
app = Flask(__name__, template_folder='templates') 

if not app.debug:
    logging.basicConfig(level=logging.INFO)

# 配置日志
LOG_FILE = os.path.join(parent_dir, "gemini_quant.log")
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8'), logging.StreamHandler()]
)
logger = logging.getLogger("app")

# 移除硬编码的 API Key，只依赖环境变量
# os.environ['GEMINI_API_KEY'] = "AIzaSyBcXoWRghWP1I83qVCDfOddZ7P-lpJg4zk"
os.environ['GEMINI_API_KEY'] = "AIzaSyAP8WsfGTPJ2TOB8Hlnqcby6VZzlUXMQpg"

# 假设您的 main.py 是一个数据采集脚本，这里只是模拟运行
def run_data_collection_script():
    logger.info("正在运行数据采集脚本: %s", os.path.join(parent_dir, 'main.py'))
    # 实际的数据采集逻辑，可能需要 subprocess.run() 或其他方式
    pass

@app.route('/')
def index():
    # 使用 render_template 来渲染 HTML 模板
    return render_template('index.html')

@app.route('/api/gemini_advice', methods=['POST'])
def gemini_advice():
    logger.info("开始 Gemini API 流式推理。")
    try:
        # 尝试获取 JSON 数据，并捕获 UnsupportedMediaType 异常
        try:
            data = request.get_json()
        except UnsupportedMediaType as e:
            logger.error(f"API 调用异常: {e}")
            return jsonify({"error": f"请求 Content-Type 错误: {e.description}"}), 415
        except Exception as e:
            logger.error(f"解析请求 JSON 异常: {e}\n{traceback.format_exc()}")
            return jsonify({"error": f"请求数据解析失败: {e}"}), 400

        # 1. 自动运行 main.py 生成 data.json
        main_py_path = os.path.join(parent_dir, 'main.py')
        data_json_path = os.path.join(parent_dir, 'data.json')
        try:
            logger.info(f"自动运行数据采集脚本: {main_py_path}")
            result = subprocess.run([sys.executable, main_py_path], capture_output=True, text=True, timeout=180)
            if result.returncode != 0:
                logger.error(f"main.py 执行失败: {result.stderr}")
                return jsonify({"error": f"main.py 执行失败: {result.stderr}"}), 500
            if not os.path.exists(data_json_path):
                logger.error("main.py 执行后未生成 data.json")
                return jsonify({"error": "main.py 执行后未生成 data.json"}), 500
            with open(data_json_path, 'r', encoding='utf-8') as f:
                data_json = json.load(f)
        except Exception as e:
            logger.error(f"自动运行 main.py 失败: {e}\n{traceback.format_exc()}")
            return jsonify({"error": f"自动运行 main.py 失败: {e}"}), 500

        # 2. 兼容前端传参和自动采集
        packaged_json = None
        screenshot_path = None
        if data and isinstance(data, dict):
            # 优先用前端传参，否则用 main.py 采集结果
            packaged_json = data.get('packaged_json') or data_json
            screenshot_path = data.get('screenshot_path') or data_json.get('clipboard_image_path')
        else:
            packaged_json = data_json
            screenshot_path = data_json.get('clipboard_image_path')
        if not packaged_json:
            return jsonify({"error": "Missing packaged_json"}), 400

        def generate():
            # 发送一个初始状态消息
            yield f"data: {json.dumps({'type': 'status', 'stage': 'connecting', 'message': '正在连接 Gemini API...'})}\n\n"
            try:
                # 修正：前端已移除图片上传，直接将 screenshot_path 设置为 None
                for chunk in gemini_api_caller.call_gemini_api_stream(packaged_json, screenshot_path):
                    if chunk:
                        # 关键修改：将文本块封装为 {"type": "content", "text": chunk}
                        yield f"data: {json.dumps({'type': 'content', 'text': chunk}, ensure_ascii=False)}\n\n"
            except Exception as e:
                app.logger.error(f"流式推理异常: {e}\n{traceback.format_exc()}")
                # 在流中发送错误信息
                yield f"data: {json.dumps({'type': 'error', 'message': f'[Gemini流式API调用异常] {str(e)}'})}\n\n"
            finally:
                # 流结束时发送一个完成状态消息
                yield f"data: {json.dumps({'type': 'status', 'stage': 'completed', 'message': '数据流已结束。'})}\n\n"

        return Response(generate(), mimetype='text/event-stream')

    except Exception as e:
        # 捕获其他未被 generate() 内部处理的异常
        logger.error(f"API 调用异常: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"服务器内部错误: {e}"}), 500

# 添加静态文件路由，用于访问截图
@app.route('/screenshots/<path:filename>')
def serve_screenshot(filename):
    return send_from_directory('/tmp/tradingview_screenshots', filename)

# 添加路由用于获取 data.json
@app.route('/data.json')
def serve_data_json():
    try:
        with open(os.path.join(parent_dir, 'data.json'), 'r', encoding='utf-8') as f:
            return jsonify(json.load(f))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    if not os.getenv('GEMINI_API_KEY'):
        print("警告：GEMINI_API_KEY 环境变量未设置。API 调用可能会失败。\n请在启动应用前设置该环境变量，例如：export GEMINI_API_KEY=\"YOUR_API_KEY\"")
    # 只在非debug模式下自动启动Bot，开发调试时不自动拉起
    if not app.debug:
        start_telegram_bot()
    # 启动主服务
    app.run(host='0.0.0.0', port=5000, debug=True)