# src/core/path_manager.py
import os
import json
from typing import Dict, Any, Optional, List
from .config_loader import get_project_root

# TODO: 考虑将PathManager实现为单例模式，以确保在整个应用程序中只有一个实例。
# 目前的实现方式（在模块级别创建实例）在大多数情况下是有效的，但单例模式会更明确。
class PathManager:
    """
    路径管理器，统一管理项目中的所有路径。
    
    该类从 `config/paths.json` 加载路径配置。如果配置文件不存在，
    它会使用一组硬编码的默认值。
    
    它还负责在启动时确保所有在配置中定义的目录都存在。
    """
    
    def __init__(self):
        self.project_root = get_project_root()
        self._paths_config = self._load_paths_config()
        self._ensure_directories()
    
    def _load_paths_config(self) -> Dict[str, Any]:
        """
        加载路径配置文件。
        
        如果 `config/paths.json` 不存在，将返回一个硬编码的默认配置。
        
        Returns:
            Dict[str, Any]: 加载的路径配置。
        """
        config_path = os.path.join(self.project_root, "config/paths.json")
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            # TODO: 将这个硬编码的默认配置提取到一个单独的默认配置文件中 (e.g., `paths.default.json`)。
            # 这样可以更容易地管理和查看默认设置，而不是将其隐藏在代码中。
            # 如果配置文件不存在，返回默认配置
            return {
                "browser_profiles": {
                    "base_dir": "data/browser_profiles",
                    "chrome_profile": "data/browser_profiles/chrome_profile",
                    "chrome_profile_copy": "data/browser_profiles/chrome_profile_copy", 
                    "chrome_profiles": "data/browser_profiles/chrome_profiles"
                },
                "data": {
                    "downloads": "data/downloads",
                    "screenshots": "data/screenshots"
                },
                "cache": {
                    "reply": "cache/reply"
                },
                "logs": {
                    "base_dir": "logs",
                    "main_log": "logs/main.log",
                    "trade_log": "logs/trade.log",
                    "effective_log": "logs/effective_communication.log"
                }
            }
    
    def _ensure_directories(self):
        """
        确保所有在路径配置中定义的目录都存在。
        
        这个方法会递归地扫描路径配置字典，并为所有以 `_dir` 结尾
        或在 `directories_to_create` 列表中明确指定的键创建目录。
        """
        directories_to_create = [
            "downloads", 
            "screenshots",
            "reply"
        ]
        
        # TODO: 这个目录发现逻辑仍然有些复杂。一个更简单的设计可能是在配置文件中
        # 使用一个特殊的键（如 `__directories__`）来明确列出所有需要创建的目录。
        # 这样可以消除基于键名的猜测。
        
        def collect_directories_recursive(config_dict: Dict[str, Any], path_parts: List[str]):
            """递归地从配置中收集目录路径。"""
            for key, value in config_dict.items():
                if isinstance(value, str):
                    # 检查键是否表示一个需要创建的目录
                    current_path_key = ".".join(path_parts + [key])
                    if key.endswith("_dir") or key in directories_to_create:
                        dir_path = os.path.join(self.project_root, value)
                        os.makedirs(dir_path, exist_ok=True)
                elif isinstance(value, dict):
                    collect_directories_recursive(value, path_parts + [key])

        collect_directories_recursive(self._paths_config, [])
    
    def get_path(self, category: str, key: str) -> str:
        """
        获取指定分类和键的绝对路径。

        Args:
            category (str): 路径分类 (例如, 'logs', 'data')。
            key (str): 分类下的具体路径键 (例如, 'main_log', 'downloads')。

        Returns:
            str: 计算出的绝对路径。
            
        Raises:
            ValueError: 如果分类或键在配置中不存在。
        """
        if category not in self._paths_config:
            raise ValueError(f"未知的路径分类: {category}")
        
        category_config = self._paths_config[category]
        if not isinstance(category_config, dict) or key not in category_config:
            raise ValueError(f"未知的路径key: {category}.{key}")
        
        relative_path = category_config[key]
        return os.path.join(self.project_root, relative_path)
    
    def get_browser_profile_path(self, profile_name: str = "chrome_profile") -> str:
        """获取浏览器配置文件路径"""
        return self.get_path("browser_profiles", profile_name)
    
    def get_downloads_path(self) -> str:
        """获取下载目录路径"""
        return self.get_path("data", "downloads")
    
    def get_screenshots_path(self) -> str:
        """获取截图目录路径"""
        return self.get_path("data", "screenshots")
    
    def get_cache_path(self, cache_type: str = "reply") -> str:
        """获取缓存目录路径"""
        # TODO: 这里的 'cache' 和 'reply' 是硬编码的，如果 paths.json 结构改变，这里可能会出错。
        # 考虑让这个函数更通用，或者确保文档中明确指出依赖关系。
        return self.get_path("cache", cache_type)
    
    def get_log_path(self, log_type: str = "main_log") -> str:
        """获取日志文件路径"""
        return self.get_path("logs", log_type)

# 全局路径管理器实例
# 这种在模块级别创建实例的方式是一种常见的简化版单例模式，
# 因为Python的模块导入机制确保了这个代码块只在第一次导入时执行一次。
path_manager = PathManager() 