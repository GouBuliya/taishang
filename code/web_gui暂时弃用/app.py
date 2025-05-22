from flask import Flask, request, jsonify, send_from_directory, render_template
from flask_cors import CORS
import os

app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app)

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/api/indicators", methods=["GET"])
def get_indicators():
    # TODO: 调用采集脚本，返回JSON
    return jsonify({"msg": "采集结果接口待实现"})

@app.route("/api/upload_image", methods=["POST"])
def upload_image():
    # TODO: 实现图片上传与保存
    return jsonify({"msg": "图片上传接口待实现"})

@app.route("/api/gemini_advice", methods=["POST"])
def gemini_advice():
    # TODO: 调用Gemini API，返回建议
    return jsonify({"msg": "Gemini建议接口待实现"})

@app.route("/api/position", methods=["POST"])
def save_position():
    # TODO: 保存持仓信息
    return jsonify({"msg": "持仓信息保存接口待实现"})

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
