# Gemini Web GUI 后端
from flask import Flask, jsonify, request, send_from_directory, Response
import subprocess
import os
import json
import logging
import sys
os.environ['GEMINI_API_KEY'] = "AIzaSyAP8WsfGTPJ2TOB8Hlnqcby6VZzlUXMQpg"

app = Flask(__name__, static_folder='static')

if not app.debug:
    logging.basicConfig(level=logging.INFO)

# 设置全局 HTTP/HTTPS 代理（如有需要）
proxy_url = os.getenv('HTTP_PROXY', 'http://127.0.0.1:1080')
https_proxy_url = os.getenv('HTTPS_PROXY', proxy_url)
os.environ['HTTP_PROXY'] = proxy_url
os.environ['HTTPS_PROXY'] = https_proxy_url

base_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.join(base_dir, '..')
sys.path.insert(0, parent_dir)
import gemini_api_caller

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/api/gemini_advice', methods=['POST'])
def gemini_advice():
    main_path = os.path.join(parent_dir, 'main.py')
    app.logger.info(f"正在运行数据采集脚本: {main_path}")
    try:
        result = subprocess.run(['python3', main_path], capture_output=True, text=True, timeout=180)
        if result.returncode != 0:
            app.logger.error(f"数据采集脚本失败: {result.stderr}")
            return jsonify({'type': 'error', 'message': f'数据采集失败: {result.stderr}'}), 500
    except subprocess.TimeoutExpired:
        app.logger.error("数据采集脚本超时。")
        return jsonify({'type': 'error', 'message': '数据采集脚本在180秒后超时。'}), 500
    except Exception as e:
        app.logger.error(f"运行数据采集脚本时出错: {e}")
        return jsonify({'type': 'error', 'message': f'数据采集中发生错误: {str(e)}'}), 500
    data_path = os.path.join(parent_dir, 'data.json')
    if not os.path.exists(data_path):
        app.logger.error("脚本执行后未找到 data.json。")
        return jsonify({'type': 'error', 'message': '采集的数据文件 (data.json) 未找到。'}), 404
    try:
        with open(data_path, 'r', encoding='utf-8') as f:
            packaged_data_from_file = json.load(f)
    except json.JSONDecodeError:
        app.logger.error("解析 data.json 失败。")
        return jsonify({'type': 'error', 'message': '解析采集的数据 (data.json) 失败。'}), 500
    except Exception as e:
        app.logger.error(f"读取 data.json 时出错: {e}")
        return jsonify({'type': 'error', 'message': f'读取采集数据时发生错误: {str(e)}'}), 500
    def generate_gemini_stream():
        try:
            app.logger.info("开始 Gemini API 数据流。")
            for chunk in gemini_api_caller.call_gemini_api_stream(packaged_data_from_file):
                yield chunk
        except Exception as e:
            app.logger.error(f"Gemini 流生成过程中发生错误: {e}")
            error_payload = {"type": "error", "message": f"流生成错误: {str(e)}"}
            # SSE 协议要求每条消息以 data: 开头，结尾两个换行
            yield f"data: {json.dumps(error_payload)}\n\n"
            # 终止生成器，防止后续继续 yield
            return
    return Response(generate_gemini_stream(), mimetype='text/event-stream')

if __name__ == '__main__':
    if not os.getenv('GEMINI_API_KEY'):
        print("警告：GEMINI_API_KEY 环境变量未设置。API 调用可能会失败。\n请在启动应用前设置该环境变量，例如：export GEMINI_API_KEY=\"YOUR_API_KEY\"")
    # 启动主服务
    app.run(host='0.0.0.0', port=5000, debug=True)
