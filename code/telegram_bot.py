import subprocess
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, Application
import re
import json
from collections.abc import Mapping
import time
import threading
import os
import importlib
import sys

TELEGRAM_BOT_TOKEN = '8046148449:AAF8TnmmoUDxQqTBtaq_MUOftL422mCJsAY'
REPLY_FILE = os.path.join(os.path.dirname(__file__), '../gemini_reply.txt')  # Gemini回复输出文件
os.environ['GEMINI_API_KEY'] = "AIzaSyAP8WsfGTPJ2TOB8Hlnqcby6VZzlUXMQpg"
REGISTERED_CHAT_IDS = set()

# --- MarkdownV2 特殊字符转义 ---
def escape_md_v2(text: str) -> str:
    if not isinstance(text, str):
        text = str(text)
    # Ensure '-' is definitely in the list of characters to escape if it's not part of intended Markdown syntax
    # The list already includes it.
    escape_chars = r'_*[]()~`>#+-.=|{}!' # '.' and '!' are also important for MarkdownV2
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

# --- 键名翻译 ---
def translate_key(key: str) -> str:
    mapping = {
        'M15': '15分钟周期', 'H1': '1小时周期', 'H4': '4小时周期',
        'indicators': '技术指标', 'factors': '宏观因子',
        'close': '收盘价', 'volume': '成交量', 'RSI': '相对强弱指数 (RSI)',
        'MACD_macd': 'MACD值', 'MACD_signal': 'MACD信号线', 'MACD_hist': 'MACD柱',
        'ATR': '平均真实波幅 (ATR)', 'ADX': '平均趋向指数 (ADX)',
        'Stoch_K': '随机指标K值', 'Stoch_D': '随机指标D值',
        'StochRSI_K': '随机相对强弱指数K值', 'StochRSI_D': '随机相对强弱指数D值',
        'BB_upper': '布林带上轨', 'BB_middle': '布林带中轨', 'BB_lower': '布林带下轨',
        'EMA5': '5周期EMA', 'EMA8': '8周期EMA', 'EMA10': '10周期EMA', 'EMA20': '20周期EMA',
        'EMA50': '50周期EMA', 'EMA100': '100周期EMA', 'EMA200': '200周期EMA',
        'SMA5': '5周期SMA', 'SMA8': '8周期SMA', 'SMA10': '10周期SMA', 'SMA20': '20周期SMA',
        'SMA50': '50周期SMA', 'SMA100': '100周期SMA', 'SMA200': '200周期SMA',
        'VWAP': '成交量加权平均价 (VWAP)',
        'ticker': '交易对', 'name': '名称', 'timestamp': '时间戳',
        'funding_rate': '资金费率', 'fear_greed_index': '恐慌与贪婪指数',
        'open_interest': '未平仓合约量',
    }
    return mapping.get(key, key)

async def handle_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    REGISTERED_CHAT_IDS.add(chat_id)
    await update.message.reply_text(f"已注册，您可以使用 /ask_gemini 主动获取Gemini推理结果。chat_id={chat_id}")

async def send_gemini_reply_to_all(application: Application, text: str):
    # 获取所有活跃对话（可扩展为持久化用户列表）
    # 这里只做简单演示：推送到指定chat_id（可改为配置或动态注册）
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    if not chat_id:
        print("[Bot] 未设置TELEGRAM_CHAT_ID，无法推送Gemini回复。")
        return
    try:
        await application.bot.send_message(chat_id=int(chat_id), text=text[:4096])
    except Exception as e:
        print(f"[Bot] 推送Gemini回复失败: {e}")

async def ask_gemini(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in REGISTERED_CHAT_IDS:
        REGISTERED_CHAT_IDS.add(chat_id)
    await update.message.reply_text("正在采集数据并调用Gemini，请稍候...")
    try:
        # 1. 运行 main.py 采集数据
        base_dir = os.path.dirname(os.path.abspath(__file__))
        main_path = os.path.join(base_dir, "main.py")
        result = subprocess.run(["python3", main_path], capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            await update.message.reply_text(f"数据采集失败: {result.stderr}")
            return
        # 2. 读取 data.json
        data_path = os.path.join(base_dir, "data.json")
        if not os.path.exists(data_path):
            await update.message.reply_text("未找到 data.json，数据采集失败。")
            return
        with open(data_path, "r", encoding="utf-8") as f:
            packaged = json.load(f)
        screenshot_path = packaged.get("clipboard_image_path")
        # 3. 调用 Gemini API
        sys.path.insert(0, base_dir)
        gemini_api_caller = importlib.import_module("gemini_api_caller")
        call_gemini_api = gemini_api_caller.call_gemini_api
        reply = call_gemini_api(packaged, screenshot_path=screenshot_path)
        if not isinstance(reply, str):
            reply = json.dumps(reply, ensure_ascii=False, indent=2)
        # 4. 推送结果
        # 分块推送，防止超长
        max_len = 4000
        for i in range(0, len(reply), max_len):
            await update.message.reply_text(reply[i:i+max_len])
    except Exception as e:
        await update.message.reply_text(f"Gemini推理失败: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 仅用于注册chat_id
    chat_id = update.effective_chat.id
    await update.message.reply_text(f"已注册，后续每次Gemini推理完成后会自动推送到本对话。chat_id={chat_id}")
    # 保存chat_id到环境变量（可扩展为持久化存储）
    os.environ['TELEGRAM_CHAT_ID'] = str(chat_id)

async def post_init_actions(application: Application):
    bot_info = await application.bot.get_me()
    print(f"Telegram Bot (ID: {bot_info.id}, Username: @{bot_info.username}) 已成功连接并初始化。")
    print("请在Telegram中随便发一句话以注册chat_id，之后每次Gemini推理完成后会自动推送到本对话。")

# --- Telegram Bot 主程序 ---
if __name__ == '__main__':
    print("正在启动 Telegram Bot...")
    try:
        app_builder = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN)
        app_builder.post_init(post_init_actions)
        app = app_builder.build()
        app.add_handler(CommandHandler("start", handle_register))
        app.add_handler(CommandHandler("register", handle_register))
        app.add_handler(CommandHandler("ask_gemini", ask_gemini))
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_register))
        print("Bot已启动。请发送 /register 或 /ask_gemini 体验主动推理。")
        app.run_polling(allowed_updates=Update.ALL_TYPES)
        print("Telegram Bot 已停止。")
    except Exception as e:
        print(f"启动或运行 Bot 时发生错误: {e}")