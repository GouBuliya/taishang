import subprocess
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, Application
import re
import json
from collections.abc import Mapping

TELEGRAM_BOT_TOKEN = '8046148449:AAF8TnmmoUDxQqTBtaq_MUOftL422mCJsAY'

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

# --- 将字典转换为 Markdown 格式 ---
def format_dict_to_md(data: Mapping, level: int = 0) -> str:
    md_string = ""
    indent = '  ' * level 

    if not isinstance(data, Mapping):
        return f"{indent}• {escape_md_v2(str(data))}\n"

    for key, value in data.items():
        translated = translate_key(str(key))
        escaped_key = escape_md_v2(translated)

        # 保留2位小数（直接截断，不四舍五入）
        def truncate_float(val):
            if isinstance(val, float):
                s = str(val)
                if '.' in s:
                    int_part, dec_part = s.split('.', 1)
                    return int_part + '.' + dec_part[:2]
                else:
                    return s
            return val

        # 资金费率特殊处理为百分号，保留6位小数（直接截断）
        if key == 'funding_rate':
            try:
                val2 = float(value) * 100
                s = str(val2)
                if '.' in s:
                    int_part, dec_part = s.split('.', 1)
                    val2_str = int_part + '.' + dec_part[:6]
                else:
                    val2_str = s
                escaped_value = escape_md_v2(val2_str) + '%'
            except Exception:
                escaped_value = escape_md_v2(str(value))
            md_string += f"{indent}• *{escaped_key}*：{escaped_value}\n"
            continue

        # 超买超卖标注逻辑
        overbought_oversold = ''
        if key.upper() == 'RSI':
            try:
                v = float(value)
                if v >= 70:
                    overbought_oversold = '（超买⚠️）'
                elif v <= 30:
                    overbought_oversold = '（超卖⚠️）'
            except Exception:
                pass
        if key.upper() == 'STOCH_K' or key.upper() == 'STOCH.D' or key.upper() == 'STOCHRSI_K' or key.upper() == 'STOCHRSI_D':
            try:
                v = float(value)
                if v >= 80:
                    overbought_oversold = '（超买⚠️）'
                elif v <= 20:
                    overbought_oversold = '（超卖⚠️）'
            except Exception:
                pass

        if isinstance(value, Mapping):
            md_string += f"{indent}• *{escaped_key}*：\n"
            md_string += format_dict_to_md(value, level + 1)
        elif isinstance(value, list):
            md_string += f"{indent}• *{escaped_key}*：\n"
            for i, item in enumerate(value):
                if isinstance(item, Mapping):
                    md_string += f"{indent}  • `项 {i+1}`：\n"
                    md_string += format_dict_to_md(item, level + 2)
                else:
                    md_string += f"{indent}  • {escape_md_v2(str(truncate_float(item)))}\n"
        else:
            val2 = truncate_float(value)
            escaped_value = escape_md_v2(str(val2))
            md_string += f"{indent}• *{escaped_key}*：{escaped_value}{overbought_oversold}\n"
    return md_string

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    chat_id = update.effective_chat.id

    if text.lower() == '获取data':
        await context.bot.send_message(chat_id=chat_id, text="正在采集数据，请稍候...")
        try:
            result = subprocess.run(
                ['python', 'main.py'],
                capture_output=True,
                text=True,
                cwd=r'd:\基于gemini多模态识别k线的金融智能体\gemini_quant_v1_1\code',
                check=False,
                encoding='utf-8'
            )
        except FileNotFoundError:
            await update.message.reply_text("错误：无法找到 `main.py` 脚本或 Python 解释器。请检查路径配置。")
            return
        except Exception as e:
            await update.message.reply_text(f"执行脚本时发生意外错误：{escape_md_v2(str(e))}", parse_mode='MarkdownV2')
            return

        reply_stdout = result.stdout.strip() if result.stdout else ''
        reply_stderr = result.stderr.strip() if result.stderr else ''
        
        messages_to_send = []

        if not reply_stdout and not reply_stderr:
            messages_to_send.append("采集脚本无任何输出。")
        elif not reply_stdout and reply_stderr:
             messages_to_send.append("采集脚本无标准输出，但有错误信息：")

        if reply_stdout:
            try:
                parsed_data = json.loads(reply_stdout)
                if isinstance(parsed_data, Mapping):
                    if 'indicators' in parsed_data and isinstance(parsed_data['indicators'], Mapping):
                        indicator_data = parsed_data['indicators']
                        for period, p_data in indicator_data.items():
                            period_title = translate_key(period)
                            # Removed the "------------------------------------" line
                            md_block = f"📊 *{escape_md_v2(period_title)} 技术指标*\n\n" 
                            md_block += format_dict_to_md(p_data)
                            messages_to_send.append(md_block)
                    
                    if 'factors' in parsed_data and isinstance(parsed_data['factors'], Mapping):
                        factor_data = parsed_data['factors']
                        # Removed the "------------------------------------" line
                        md_block = f"🌍 *宏观经济因子*\n\n"
                        md_block += format_dict_to_md(factor_data)
                        messages_to_send.append(md_block)
                    
                    other_data_to_format = {k: v for k, v in parsed_data.items() if k not in ['indicators', 'factors']}
                    if other_data_to_format:
                        # Removed the "------------------------------------" line
                        md_block = f"📋 *其他数据*\n\n"
                        md_block += format_dict_to_md(other_data_to_format)
                        messages_to_send.append(md_block)
                else:
                    messages_to_send.append(f"原始输出 (非标准JSON结构):\n```text\n{escape_md_v2(reply_stdout)}\n```") # Use text for non-json

            except json.JSONDecodeError:
                messages_to_send.append(f"原始输出 (JSON解析失败):\n```text\n{escape_md_v2(reply_stdout)}\n```") # Use text for non-json
        
        if reply_stderr:
            messages_to_send.append(f"⚠️ *脚本错误输出 (stderr)*:\n```\n{escape_md_v2(reply_stderr)}\n```")

        if not messages_to_send:
            await update.message.reply_text("未能处理采集到的数据或无有效数据展示。")
            return

        for i, block_content in enumerate(messages_to_send):
            if not block_content.strip():
                continue
            try:
                # Ensure there are no leading/trailing newlines that might affect parsing of the first/last line
                block_to_send = block_content.strip()
                if len(block_to_send) > 4000: # Telegram's limit is 4096
                    await update.message.reply_text(f"警告：第 {i+1} 部分内容过长，将分段发送。", parse_mode='MarkdownV2')
                    parts = [block_to_send[j:j+4000] for j in range(0, len(block_to_send), 4000)]
                    for part_idx, part_content in enumerate(parts):
                        await update.message.reply_text(part_content, parse_mode='MarkdownV2')
                elif block_to_send: # Ensure block is not empty after stripping
                    await update.message.reply_text(block_to_send, parse_mode='MarkdownV2')
            except Exception as e:
                error_msg = f"发送第 {i+1} 部分消息时出错: {escape_md_v2(str(e))}\n内容片段:\n```\n{escape_md_v2(block_content[:200])}...\n```"
                await update.message.reply_text(error_msg, parse_mode='MarkdownV2')
                print(f"Error sending message part {i+1}: {e}\nContent: {block_content[:500]}")

    else:
        await update.message.reply_text("你好！发送 `获取data` 指令，我可以帮你运行脚本并展示最新的宏观因子和技术指标数据。")

async def post_init_actions(application: Application):
    bot_info = await application.bot.get_me()
    print(f"Telegram Bot (ID: {bot_info.id}, Username: @{bot_info.username}) 已成功连接并初始化。")
    print("在 Telegram 中向机器人发送 '获取data' 即可获取 main.py 输出。")

if __name__ == '__main__':
    print("正在启动 Telegram Bot...")
    try:
        app_builder = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN)
        app_builder.post_init(post_init_actions)
        app = app_builder.build()
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
        app.run_polling(allowed_updates=Update.ALL_TYPES)
        print("Telegram Bot 已停止。")
    except Exception as e:
        print(f"启动或运行 Bot 时发生错误: {e}")