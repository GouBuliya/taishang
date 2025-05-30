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
from queue import Queue

#邮件
import smtplib
from email.mime.text import MIMEText
from email.header import Header
#

import time
import datetime  # 新增：导入datetime模块

# 保留parent_dir、current_dir等路径相关变量定义
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.join(current_dir, '..')
sys.path.insert(0, parent_dir)

# 将模板文件夹设置为 'templates'，而不是 'static'
app = Flask(__name__, template_folder='templates') 

if not app.debug:
    logging.basicConfig(level=logging.INFO)



BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = "/root/codespace/Qwen_quant_v1/nohup.out"
logging.basicConfig(
    level=logging.INFO,
    format='[%(filename)s][%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
    handlers=[logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8'), logging.StreamHandler()]
)

logger = logging.getLogger("GeminiQuant")



# 移除硬编码的 API Key，只依赖环境变量
os.environ['GEMINI_API_KEY'] = "AIzaSyCkBZzYyaSvLzHRWGEsoabZbyNzlvAxa98"

os.environ['HTTP_PROXY'] = 'http://127.0.0.1:7890'
os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:7890'#代理

# 假设您的 main.py 是一个数据采集脚本，这里只是模拟运行
def run_data_collection_script():
    logger.info("正在运行数据采集脚本: %s", os.path.join(parent_dir, 'main.py'))
    # 实际的数据采集逻辑，可能需要 subprocess.run() 或其他方式
    pass

@app.route('/') # 主页
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


def send_ai_reply_email(subject, content, to_addrs):#subject: Gemini BTC AI回复, Gemini ETH AI回复 
    # content: Gemini回复内容 
    # to_addrs: ["a528895030@gmail.com", "1528895030@qq.com"]
    smtp_server = 'smtp.gmail.com'  # 例如QQ邮箱
    smtp_port = 465
    from_addr = 'a528895030@gmail.com'  # 替换为你的发件邮箱
    password = 'owuh lyqs bmuh qkde'  # 替换为你的SMTP授权码

    msg = MIMEText(content, 'plain', 'utf-8')
    msg['From'] = Header(from_addr)
    msg['To'] = Header(','.join(to_addrs))
    msg['Subject'] = Header(subject, 'utf-8')

    try:
        server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        server.login(from_addr, password)
        server.sendmail(from_addr, to_addrs, msg.as_string())
        server.quit()
        logger.info(f"AI回复已发送到邮箱：{to_addrs}")
    except Exception as e:
        logger.error(f"发送邮件失败: {e}")

result_queue = Queue()


def coin_task(coin_name, main_py_path, data_json_path, gemini_api_path, reply_cache_dir, mail_subject, mail_receivers):
        try:
            logger.info(f"[{coin_name}] 自动运行数据采集脚本: {main_py_path}")
            # 使用指定的python3.10解释器运行main.py
            subprocess.run(["/usr/local/bin/python3.10", main_py_path], capture_output=True, text=True, timeout=360)
            #检查data.json是否生成
            if not os.path.exists(data_json_path) or os.path.getsize(data_json_path) == 0:
                logger.error(f"[{coin_name}] main.py 执行后未生成或生成空的 data.json: {data_json_path}")
                return
            #检查data.json是否为空
            if os.path.getsize(data_json_path) == 0:
                logger.error(f"[{coin_name}] main.py 执行后未生成或生成空的 data.json: {data_json_path}")
                return

            logger.info(f"[{coin_name}] main.py 执行完成，文件地址：{data_json_path}")
            
            


            # 直接运行 gemini_api_caller.py 脚本
            logger.info(f"[{coin_name}] 自动运行Gemini API调用脚本: {gemini_api_path}")
            # gemini_api_caller.py 的 if __name__ == "__main__": 块应该会读取 data.json 并生成 reply_cache/gemini.txt
            subprocess.run(["/usr/local/bin/python3.10", gemini_api_path], capture_output=True, text=True, timeout=360)
            
            logger.info(f"[{coin_name}] gemini_api_caller.py 执行完成，文件地址：{reply_cache_dir}")

            # 读取 gemini_api_caller.py 生成的回复文件
            reply_file = os.path.join(reply_cache_dir, f'gemini.txt') # 使用coin_name前缀
            if not os.path.exists(reply_file) or os.path.getsize(reply_file) == 0:
                logger.error(f"[{coin_name}] Gemini回复文件未生成或为空: {reply_file}")
                return

            logger.info(f"[{coin_name}] 读取Gemini回复文件: {reply_file}")
            with open(reply_file, 'r', encoding='utf-8') as f:
                reply_text = f.read() # 读取文件内容

            logger.info(f"[{coin_name}] 成功读取Gemini回复内容")

            # 发送邮件
            send_ai_reply_email(
                subject=mail_subject,
                content=reply_text,
                to_addrs=mail_receivers
            )
            logger.info(f"[{coin_name}] Gemini推理结果已发送邮件。")
            result_queue.put({"coin": coin_name, "status": "success"})

        except FileNotFoundError as e:
            logger.error(f"[{coin_name}] 文件未找到错误: {e}")

            result_queue.put({"coin": coin_name, "status": "fail", "msg": f"文件未找到: {e}"})

        except subprocess.TimeoutExpired as e:
            logger.error(f"[{coin_name}] 子进程执行超时: {e}")
            result_queue.put({"coin": coin_name, "status": "fail", "msg": f"子进程执行超时: {e}"})
        except Exception as e:
            logger.error(f"[{coin_name}] 子模块主循环异常: {e}\n{traceback.format_exc()}")
            result_queue.put({"coin": coin_name, "status": "fail", "msg": str(e)})



@app.route('/api/gemini_advice', methods=['POST'])
def gemini_advice():
    """
    启动ETH和BTC两个子模块，依次串行完成数据采集、图片处理、Gemini推理、邮件发送。
    """
    logger.info("收到/api/gemini_advice请求，准备串行执行BTC和ETH子模块流程。")
    result_queue = Queue()

    # 串行执行BTC采集、推理、邮件
    logger.info("[主流程] 串行执行BTC采集、推理、邮件...")
    btc_main_py = '/root/codespace/Qwen_quant_v1/BTC_code/main.py'
    btc_data_json = '/root/codespace/Qwen_quant_v1/BTC_code/data.json'
    coin_task(
        'BTC',
        btc_main_py,
        btc_data_json,
        '/root/codespace/Qwen_quant_v1/BTC_code/gemini_api_caller.py',
        '/root/codespace/Qwen_quant_v1/BTC_code/reply_cache',
        'Gemini BTC AI回复',
        ["a528895030@gmail.com", "1528895030@qq.com"]
    )
    # 串行执行ETH采集、推理、邮件
    logger.info("[主流程] 串行执行ETH采集、推理、邮件...")
    eth_main_py = '/root/codespace/Qwen_quant_v1/code/main.py'
    eth_data_json = '/root/codespace/Qwen_quant_v1/code/data.json'
    coin_task(
        'ETH',
        eth_main_py,
        eth_data_json,
        '/root/codespace/Qwen_quant_v1/code/gemini_api_caller.py',
        '/root/codespace/Qwen_quant_v1/code/reply_cache',
        'Gemini ETH AI回复',
        ["a528895030@gmail.com", "1528895030@qq.com"]
    )
    # 汇总结果
    results = []
    while not result_queue.empty():
        results.append(result_queue.get())
    return jsonify({"status": "done", "results": results})



def schedule_gemini_task():
    """
    每到分钟模15为0时自动依次串行执行BTC和ETH的采集、推理、邮件，整个流程单线程顺序执行。
    """

    while True:
        now = datetime.datetime.now()
        if now.minute % 15 == 0 and now.second < 5:
            # 串行执行BTC采集、推理、邮件
            logger.info("[定时] 串行执行BTC采集、推理、邮件...")
            btc_main_py = '/root/codespace/Qwen_quant_v1/BTC_code/main.py'
            btc_data_json = '/root/codespace/Qwen_quant_v1/BTC_code/data.json'
            coin_task(
                'BTC',
                btc_main_py,
                btc_data_json,
                '/root/codespace/Qwen_quant_v1/BTC_code/gemini_api_caller.py',
                '/root/codespace/Qwen_quant_v1/BTC_code/reply_cache',
                'Gemini BTC AI回复',
                ["a528895030@gmail.com", "1528895030@qq.com","changnikita71@gmail.com"]
            )
            # 串行执行ETH采集、推理、邮件
            logger.info("[定时] 串行执行ETH采集、推理、邮件...")
            eth_main_py = '/root/codespace/Qwen_quant_v1/code/main.py'
            eth_data_json = '/root/codespace/Qwen_quant_v1/code/data.json'
            coin_task(
                'ETH',
                eth_main_py,
                eth_data_json,
                '/root/codespace/Qwen_quant_v1/code/gemini_api_caller.py',
                '/root/codespace/Qwen_quant_v1/code/reply_cache',
                'Gemini ETH AI回复',
                ["a528895030@gmail.com", "1528895030@qq.com","jeffreymcadams750@gmail.com","1837572554@qq.com"]
            )
            time.sleep(60)
        else:
            time.sleep(2)

import gc
import shutil

def clean_memory_on_start():
    logger.info("启动时主动清理内存和缓存...")
    # 主动垃圾回收
    gc.collect()
    # 清理 __pycache__ 目录
    for root, dirs, files in os.walk(parent_dir):
        for d in dirs:
            if d == '__pycache__':
                try:
                    shutil.rmtree(os.path.join(root, d))
                    logger.info(f"已清理缓存目录: {os.path.join(root, d)}")
                except Exception as e:
                    logger.warning(f"清理缓存目录失败: {e}")
    # 尝试释放 Linux 系统缓存（需要root权限）
    try:
        os.system('sync; echo 3 > /proc/sys/vm/drop_caches')
        logger.info("已尝试释放 Linux 系统缓存")
    except Exception as e:
        logger.warning(f"释放系统缓存失败: {e}")

# 在主入口调用
if __name__ == '__main__':
    clean_memory_on_start()
    # Docker环境下不启动SSH隧道
    # 只在非debug模式下自动启动Bot，开发调试时不自动拉起
    # if not app.debug:
    #     start_telegram_bot()
    # 启动定时Gemini任务线程

    # 启动主服务
    
    app.run(host='0.0.0.0', port=5000, debug=True)