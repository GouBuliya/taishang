# config.py
# 用于集中管理API Key等敏感信息
import os

QWEN_API_KEY = os.getenv('QWEN_API_KEY', 'sk-2f17c724d71e448fac1b20ac1c8e09db')
DASHSCOPE_API_KEY = os.getenv('DASHSCOPE_API_KEY', QWEN_API_KEY)
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', 'AIzaSyCkBZzYyaSvLzHRWGEsoabZbyNzlvAxa98')

# 你可以扩展更多key

