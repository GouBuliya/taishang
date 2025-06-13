# tests/unit/core/test_path_manager.py
import pytest
import json
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, mock_open

from src.core.path_manager import PathManager


class TestPathManager:
    """路径管理器测试类"""
    
    def test_init_creates_directories(self, temp_path_manager):
        """测试初始化时创建必要目录"""
        pm = temp_path_manager
        
        # 验证基础目录已创建
        assert os.path.exists(pm.get_path("browser_profiles"))
        assert os.path.exists(pm.get_downloads_path())
        assert os.path.exists(pm.get_screenshots_path())
        assert os.path.exists(pm.get_cache_path())
        assert os.path.exists(pm.get_path("logs"))
    
    def test_get_path_with_category_only(self, temp_path_manager):
        """测试只提供分类的路径获取"""
        pm = temp_path_manager
        
        # 测试有base_dir的分类
        browser_path = pm.get_path("browser_profiles")
        assert browser_path.endswith("data/browser_profiles")
        
        logs_path = pm.get_path("logs")
        assert logs_path.endswith("logs")
    
    def test_get_path_with_category_and_key(self, temp_path_manager):
        """测试提供分类和键的路径获取"""
        pm = temp_path_manager
        
        # 测试具体的配置路径
        chrome_path = pm.get_path("browser_profiles", "chrome_profile")
        assert chrome_path.endswith("data/browser_profiles/chrome_profile")
        
        downloads_path = pm.get_path("data", "downloads")
        assert downloads_path.endswith("data/downloads")
    
    def test_get_path_invalid_category(self, temp_path_manager):
        """测试无效分类的错误处理"""
        pm = temp_path_manager
        
        with pytest.raises(ValueError) as exc_info:
            pm.get_path("invalid_category")
        
        assert "未知的路径分类" in str(exc_info.value)
    
    def test_get_path_invalid_key(self, temp_path_manager):
        """测试无效键的错误处理"""
        pm = temp_path_manager
        
        with pytest.raises(ValueError) as exc_info:
            pm.get_path("browser_profiles", "invalid_key")
        
        assert "未知的路径key" in str(exc_info.value)
    
    def test_convenience_methods(self, temp_path_manager):
        """测试便利方法"""
        pm = temp_path_manager
        
        # 测试浏览器配置路径
        default_profile = pm.get_browser_profile_path()
        assert default_profile.endswith("data/browser_profiles/chrome_profile")
        
        # 测试下载路径
        downloads = pm.get_downloads_path()
        assert downloads.endswith("data/downloads")
        
        # 测试截图路径
        screenshots = pm.get_screenshots_path()
        assert screenshots.endswith("data/screenshots")
        
        # 测试缓存路径
        cache = pm.get_cache_path()
        assert cache.endswith("cache/reply")
        
        # 测试日志路径
        log_path = pm.get_log_path()
        assert log_path.endswith("logs/test.log")
    
    def test_load_default_config_when_file_missing(self):
        """测试配置文件缺失时使用默认配置"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # 不创建paths.json文件
            temp_path = Path(temp_dir)
            (temp_path / "config").mkdir()
            
            with patch('src.core.path_manager.get_project_root', return_value=str(temp_path)):
                pm = PathManager()
                
                # 应该使用默认配置
                browser_path = pm.get_browser_profile_path()
                assert browser_path.endswith("data/browser_profiles/chrome_profile")
    
    def test_absolute_paths_returned(self, temp_path_manager):
        """测试返回的路径都是绝对路径"""
        pm = temp_path_manager
        
        paths_to_test = [
            pm.get_browser_profile_path(),
            pm.get_downloads_path(),
            pm.get_screenshots_path(),
            pm.get_cache_path(),
            pm.get_log_path()
        ]
        
        for path in paths_to_test:
            assert os.path.isabs(path), f"路径 {path} 不是绝对路径"
    
    def test_project_root_property(self, temp_path_manager):
        """测试项目根目录属性"""
        pm = temp_path_manager
        
        assert hasattr(pm, 'project_root')
        assert isinstance(pm.project_root, str)
        assert os.path.isabs(pm.project_root)


@pytest.mark.unit
class TestPathManagerEdgeCases:
    """路径管理器边界情况测试"""
    
    def test_path_with_special_characters(self):
        """测试包含特殊字符的路径"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "config").mkdir()
            
            # 创建包含特殊字符的路径配置
            special_config = {
                "special": {
                    "path_with_spaces": "data/path with spaces",
                    "path_with_unicode": "data/路径中文",
                    "path_with_symbols": "data/path@#$%"
                }
            }
            
            with open(temp_path / "config" / "paths.json", "w", encoding="utf-8") as f:
                json.dump(special_config, f, ensure_ascii=False, indent=2)
            
            with patch('src.core.path_manager.get_project_root', return_value=str(temp_path)):
                pm = PathManager()
                
                # 测试特殊字符路径
                space_path = pm.get_path("special", "path_with_spaces")
                assert "path with spaces" in space_path
                
                unicode_path = pm.get_path("special", "path_with_unicode")
                assert "路径中文" in unicode_path
    
    def test_nested_directory_creation(self):
        """测试深层嵌套目录的创建"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "config").mkdir()
            
            # 创建深层嵌套路径配置
            nested_config = {
                "deep": {
                    "base_dir": "level1/level2/level3/level4"
                }
            }
            
            with open(temp_path / "config" / "paths.json", "w") as f:
                json.dump(nested_config, f, indent=2)
            
            with patch('src.core.path_manager.get_project_root', return_value=str(temp_path)):
                pm = PathManager()
                
                # 深层目录应该被创建
                deep_path = pm.get_path("deep")
                assert os.path.exists(deep_path)
                assert deep_path.endswith("level1/level2/level3/level4")
    
    def test_concurrent_path_manager_instances(self):
        """测试并发创建路径管理器实例"""
        import threading
        
        results = []
        errors = []
        
        def create_path_manager():
            try:
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_path = Path(temp_dir)
                    (temp_path / "config").mkdir()
                    
                    # 创建基础配置
                    basic_config = {
                        "test": {
                            "base_dir": "test_dir"
                        }
                    }
                    
                    with open(temp_path / "config" / "paths.json", "w") as f:
                        json.dump(basic_config, f)
                    
                    with patch('src.core.path_manager.get_project_root', return_value=str(temp_path)):
                        pm = PathManager()
                        results.append(pm.project_root)
            except Exception as e:
                errors.append(e)
        
        # 创建多个线程
        threads = [threading.Thread(target=create_path_manager) for _ in range(5)]
        
        # 启动所有线程
        for thread in threads:
            thread.start()
        
        # 等待所有线程完成
        for thread in threads:
            thread.join()
        
        # 验证没有错误
        assert len(errors) == 0, f"并发测试中出现错误: {errors}"
        assert len(results) == 5, "并发创建的实例数量不正确" 