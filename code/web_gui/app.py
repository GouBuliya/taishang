# Gemini Web GUI 后端
from flask import Flask, jsonify, request, send_from_directory
import subprocess
import os
import json
os.environ['GEMINI_API_KEY'] = "AIzaSyAP8WsfGTPJ2TOB8Hlnqcby6VZzlUXMQpg"

app = Flask(__name__, static_folder='static')

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/api/gemini_advice', methods=['POST'])
def gemini_advice():
    # 运行 main.py 采集数据
    base_dir = os.path.dirname(os.path.abspath(__file__))
    main_path = os.path.join(base_dir, '../main.py')
    result = subprocess.run(['python3', main_path], capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        return jsonify({'msg': f'采集失败: {result.stderr}'})
    data_path = os.path.join(base_dir, '../data.json')
    if not os.path.exists(data_path):
        return jsonify({'msg': '未找到 data.json'})
    with open(data_path, 'r', encoding='utf-8') as f:
        packaged = json.load(f)
    # 调用 Gemini API
    import sys
    sys.path.insert(0, os.path.join(base_dir, '..'))
    import gemini_api_caller
    reply = gemini_api_caller.call_gemini_api(packaged)
    return jsonify({'msg': reply})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
