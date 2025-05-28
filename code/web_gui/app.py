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
import importlib.util

# 确保可以导入 qwen_api_caller
# 根据您的路径结构，可能需要调整 sys.path
# 假设 app.py 在 web_gui 目录下，qwen_api_caller.py 在 web_gui 的父目录 (code 目录)
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.join(current_dir, '..')
sys.path.insert(0, parent_dir)

import qwen_api_caller # 导入修改后的流式函数

# 将模板文件夹设置为 'templates'，而不是 'static'
app = Flask(__name__, template_folder='templates') 

if not app.debug:
    logging.basicConfig(level=logging.INFO)

# 配置日志
LOG_FILE = os.path.join(parent_dir, "qwen_quant.log")
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8'), logging.StreamHandler()]
)
logger = logging.getLogger("app")

# 移除硬编码的 API Key，只依赖环境变量
os.environ['qwen_API_KEY'] = "sk-2f17c724d71e448fac1b20ac1c8e09db"
os.environ['GEMINI_API_KEY'] = "AIzaSyCkBZzYyaSvLzHRWGEsoabZbyNzlvAxa98"

# os.environ['qwen_API_KEY'] = "AIzaSyAP8WsfGTPJ2TOB8Hlnqcby6VZzlUXMQpg"

# 设置 QWEN_API_KEY 环境变量，确保 Qwen API 能正常调用
os.environ['QWEN_API_KEY'] = os.environ.get('qwen_API_KEY', '')
os.environ['DASHSCOPE_API_KEY'] = os.environ.get('q wen_API_KEY', '')

# 假设您的 main.py 是一个数据采集脚本，这里只是模拟运行
def run_data_collection_script():
    logger.info("正在运行数据采集脚本: %s", os.path.join(parent_dir, 'main.py'))
    # 实际的数据采集逻辑，可能需要 subprocess.run() 或其他方式
    pass

@app.route('/')
def index():
    # 使用 render_template 来渲染 HTML 模板
    return render_template('index.html')

def extract_all_text(data):
    # 递归提取所有字符串
    texts = []
    if isinstance(data, dict):
        for v in data.values():
            texts.append(extract_all_text(v))
    elif isinstance(data, list):
        for item in data:
            texts.append(extract_all_text(item))
    elif isinstance(data, str):
        texts.append(data)
    return '\n'.join([t for t in texts if t])

@app.route('/api/qwen_advice', methods=['POST'])
def qwen_advice():
    logger.info("开始 Qwen API 流式推理。")
    try:
        try:
            data = request.get_json()
        except UnsupportedMediaType as e:
            logger.error(f"API 调用异常: {e}")
            return jsonify({"error": f"请求 Content-Type 错误: {e.description}"}), 415
        except Exception as e:
            logger.error(f"解析请求 JSON 异常: {e}\n{traceback.format_exc()}")
            return jsonify({"error": f"请求数据解析失败: {e}"}), 400

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

        screenshot_path = data_json.get('clipboard_image_path')
        prompt_text = extract_all_text(data_json)
        if not prompt_text:
            return jsonify({"error": "Missing prompt text in data.json"}), 400

        def generate():
            yield f"data: {json.dumps({'type': 'status', 'stage': 'connecting', 'message': '正在连接 Qwen API...'})}\n\n"
            error_occurred = False
            tried_without_image = False
            try:
                for chunk in qwen_api_caller.call_qwen_api_stream(prompt_text, screenshot_path):
                    if chunk and isinstance(chunk, str) and '[Qwen API调用异常]' in chunk and '图片' in chunk:
                        if not tried_without_image:
                            app.logger.warning("图片推理失败，自动降级为无图片模式重试。")
                            tried_without_image = True
                            for chunk2 in qwen_api_caller.call_qwen_api_stream(prompt_text, None):
                                if chunk2:
                                    yield f"data: {json.dumps({'type': 'content', 'text': chunk2}, ensure_ascii=False)}\n\n"
                            break
                    if chunk:
                        if isinstance(chunk, dict):
                            for k, v in chunk.items():
                                yield f"data: {json.dumps({'type': k, 'text': v}, ensure_ascii=False)}\n\n"
                        else:
                            yield f"data: {json.dumps({'type': 'content', 'text': chunk}, ensure_ascii=False)}\n\n"
            except Exception as e:
                error_occurred = True
                app.logger.error(f"流式推理异常: {e}\n{traceback.format_exc()}")
                yield f"data: {json.dumps({'type': 'error', 'message': f'[qwen流式API调用异常] {str(e)}'})}\n\n"
            finally:
                yield f"data: {json.dumps({'type': 'status', 'stage': 'completed', 'message': '数据流已结束。', 'error': error_occurred})}\n\n"

        return Response(generate(), mimetype='text/event-stream')

    except Exception as e:
        logger.error(f"API 调用异常: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"服务器内部错误: {e}"}), 500

# 添加静态文件路由，用于访问截图
@app.route('/cache_screenshots/<path:filename>')
def serve_screenshot(filename):
    return send_from_directory(os.path.join(parent_dir, 'cache_screenshots'), filename)

# 添加路由用于获取 data.json
@app.route('/data.json')
def serve_data_json():
    try:
        with open(os.path.join(parent_dir, 'data.json'), 'r', encoding='utf-8') as f:
            return jsonify(json.load(f))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 移除 Gemini 兼容路由，项目只保留 Qwen 相关API
# @app.route('/api/gemini_advice', methods=['POST'])
# def gemini_advice():
#     return jsonify({"error": "暂未实现 Gemini 推理接口，请使用 /api/qwen_advice。"}), 501

@app.route('/api/gemini_advice', methods=['POST'])
def gemini_advice():
    logger.info("开始 Gemini API 流式推理。")
    try:
        try:
            data = request.get_json()
        except UnsupportedMediaType as e:
            logger.error(f"API 调用异常: {e}")
            return jsonify({"error": f"请求 Content-Type 错误: {e.description}"}), 415
        except Exception as e:
            logger.error(f"解析请求 JSON 异常: {e}\n{traceback.format_exc()}")
            return jsonify({"error": f"请求数据解析失败: {e}"}), 400

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

        screenshot_path = data_json.get('clipboard_image_path')
        prompt_text = extract_all_text(data_json)
        if not prompt_text:
            return jsonify({"error": "Missing prompt text in data.json"}), 400

        def generate():
            logger.info(f"Gemini流式推理参数: prompt_text={prompt_text[:100]}..., screenshot_path={screenshot_path}, reasoning_effort='high'")
            yield f"data: {json.dumps({'type': 'status', 'stage': 'connecting', 'message': '正在连接 Gemini API...'})}\n\n"
            error_occurred = False
            reply_text = ""
            try:
                gemini_path = os.path.join(parent_dir, 'gemini_api_caller.py')
                logger.info(f"动态加载 Gemini API 模块: {gemini_path}")
                spec = importlib.util.spec_from_file_location("gemini_api_caller", gemini_path)
                gemini_api_caller = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(gemini_api_caller)
                logger.info("Gemini API 模块加载完成，开始流式推理...")
                for chunk in gemini_api_caller.call_gemini_api_stream(prompt_text, screenshot_path, reasoning_effort="high"):
                    logger.debug(f"Gemini流式返回: {chunk}")
                    if chunk:
                        reply_text += str(chunk)
                        yield f"data: {json.dumps({'type': 'content', 'text': chunk}, ensure_ascii=False)}\n\n"
                logger.info("Gemini流式推理结束。")
                # 日志同步：将子模块日志同步到主日志
                gemini_log_path = os.path.join(parent_dir, '../gemini_quant.log')
                if os.path.exists(gemini_log_path):
                    with open(gemini_log_path, 'r', encoding='utf-8') as f:
                        gemini_logs = f.readlines()[-20:]
                    for line in gemini_logs:
                        logger.info(f"[Gemini子模块] {line.strip()}")
            except Exception as e:
                error_occurred = True
                app.logger.error(f"流式推理异常: {e}\n{traceback.format_exc()}")
                yield f"data: {json.dumps({'type': 'error', 'message': f'[Gemini流式API调用异常] {str(e)}'})}\n\n"
            finally:
                logger.info(f"Gemini流式推理流程已完成，error_occurred={error_occurred}")
                # 缓存推理结果到 reply_cache 目录
                try:
                    cache_dir = os.path.join(parent_dir, 'reply_cache')
                    os.makedirs(cache_dir, exist_ok=True)
                    import datetime
                    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                    cache_file = os.path.join(cache_dir, f'gemini_reply_{ts}.txt')
                    with open(cache_file, 'w', encoding='utf-8') as f:
                        f.write(reply_text)
                    logger.info(f"Gemini推理结果已缓存到: {cache_file}")
                except Exception as cache_e:
                    logger.warning(f"Gemini推理结果缓存失败: {cache_e}")
                yield f"data: {json.dumps({'type': 'status', 'stage': 'completed', 'message': '数据流已结束。', 'error': error_occurred})}\n\n"

        return Response(generate(), mimetype='text/event-stream')

    except Exception as e:
        logger.error(f"API 调用异常: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"服务器内部错误: {e}"}), 500

# def start_ssh_tunnel_background():
#     """
#     以后台线程方式启动 SSH 隧道，不占用主进程终端。
#     """
#     def tunnel():
#         while True:
#             try:
#                 print("[SSH隧道] 正在建立端口转发: ssh -N -R 5000:localhost:3000 root@114.55.238.254")
#                 proc = subprocess.Popen([
#                     "ssh", "-N", "-o", "ServerAliveInterval=60", "-R", "5000:localhost:3000", "root@114.55.238.254"
#                 ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
#                 proc.wait()
#                 print("[SSH隧道] 连接断开，5秒后重试...")
#                 import time; time.sleep(5)
#             except Exception as e:
#                 print(f"[SSH隧道] 启动失败: {e}")
#                 import time; time.sleep(10)
#     t = threading.Thread(target=tunnel, daemon=True)
#     t.start()

if __name__ == '__main__':
    # Docker环境下不启动SSH隧道
    if not os.getenv('qwen_API_KEY'):
        print("警告：qwen_API_KEY 环境变量未设置。API 调用可能会失败。\n请在启动应用前设置该环境变量，例如：export qwen_API_KEY=\"YOUR_API_KEY\"")
    # 只在非debug模式下自动启动Bot，开发调试时不自动拉起
    # if not app.debug:
    #     start_telegram_bot()
    # 启动主服务
    
    app.run(host='0.0.0.0', port=5000, debug=True)