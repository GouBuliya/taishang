# src/core/config_loader.py
import os
import json
from typing import Dict, Any

def get_project_root() -> str:
    """获取项目根目录路径"""
    # 从当前文件位置向上两级到达项目根目录
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def load_config() -> Dict[str, Any]:
    """加载项目配置文件"""
    project_root = get_project_root()
    config_path = os.path.join(project_root, "config/config.json")
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    except json.JSONDecodeError as e:
        raise ValueError(f"配置文件格式错误: {config_path}, 错误: {e}")

def get_config_path(relative_path: str) -> str:
    """根据相对路径获取完整路径"""
    project_root = get_project_root()
    return os.path.join(project_root, relative_path) 