import pytest
import os
import json
import logging
from unittest import mock
import sys

# 导入要测试的客户端脚本
# 假设你的客户端脚本在 src/screenshot_client.py
# 为了能够导入，需要将 src 目录添加到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
import screenshot_client as client # 导入并重命名为 client

# 模拟的配置内容
MOCK_CONFIG = {
    "cache_screenshot_path": "/tmp/test_screenshots",
    "main_log_path": "/tmp/test_client.log",
    "proxy": {
        "http_proxy": "http://test_proxy:8080",
        "https_proxy": "https://test_proxy:8080"
    }
}

@pytest.fixture(autouse=True)
def mock_dependencies(monkeypatch, mocker, caplog):
    """
    为每个测试用例自动模拟外部依赖。
    """
    # 模拟 json.load 来提供测试配置
    mocker.patch('builtins.open', mocker.mock_open(read_data=json.dumps(MOCK_CONFIG)))
    mocker.patch('json.load', return_value=MOCK_CONFIG)

    # 模拟 os.makedirs
    mocker.patch('os.makedirs')

    # 模拟 os.environ，防止实际修改环境变量
    mock_environ = {}
    monkeypatch.setattr(os, 'environ', mock_environ)

    # 模拟 requests.get
    mock_requests_get = mocker.patch('requests.get')

    # 捕获日志
    caplog.set_level(logging.INFO)

    return mock_requests_get # 返回 mock 对象，以便在测试中配置其行为

def test_main_success(mock_dependencies, caplog):
    """
    测试 main 函数在服务器成功返回截图路径时的行为。
    """
    mock_requests_get = mock_dependencies
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "success", "filepath": "/tmp/test_screenshots/screenshot_123.png"}
    mock_requests_get.return_value = mock_response

    # 调用 main 函数
    result = client.main()

    # 验证请求是否发送正确
    mock_requests_get.assert_called_once_with("http://127.0.0.1:5002/screenshot", timeout=90)

    # 验证返回值
    assert result == "/tmp/test_screenshots/screenshot_123.png"

    # 验证日志输出
    assert "正在请求截图服务器: http://127.0.0.1:5002/screenshot" in caplog.text
    assert "截图服务器返回成功，图片路径: /tmp/test_screenshots/screenshot_123.png" in caplog.text
    
    # 验证环境变量是否被设置
    assert os.environ["http_proxy"] == MOCK_CONFIG["proxy"]["http_proxy"]
    assert os.environ["https_proxy"] == MOCK_CONFIG["proxy"]["https_proxy"]
    
    # 验证目录是否被创建
    client.os.makedirs.assert_called_once_with(MOCK_CONFIG["cache_screenshot_path"], exist_ok=True)


def test_main_server_error_response(mock_dependencies, caplog):
    """
    测试 main 函数在服务器返回错误状态时的行为。
    """
    mock_requests_get = mock_dependencies
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "error", "message": "Internal server error"}
    mock_requests_get.return_value = mock_response

    result = client.main()

    assert result is None
    assert "截图服务器返回错误或非预期响应: {'status': 'error', 'message': 'Internal server error'}" in caplog.text

def test_main_http_error(mock_dependencies, caplog):
    """
    测试 main 函数在 HTTP 状态码非 2xx 时的行为。
    """
    mock_requests_get = mock_dependencies
    mock_response = mock.Mock()
    mock_response.status_code = 500
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("500 Server Error")
    mock_requests_get.return_value = mock_response

    result = client.main()

    assert result is None
    assert "请求截图服务器异常: 500 Server Error" in caplog.text

def test_main_connection_error(mock_dependencies, caplog):
    """
    测试 main 函数在无法连接到服务器时的行为。
    """
    mock_requests_get = mock_dependencies
    mock_requests_get.side_effect = requests.exceptions.ConnectionError("Connection refused")

    result = client.main()

    assert result is None
    assert "无法连接到截图服务器，请确保服务器正在运行在 http://127.0.0.1:5002/screenshot: Connection refused" in caplog.text

def test_main_timeout(mock_dependencies, caplog):
    """
    测试 main 函数在请求超时时的行为。
    """
    mock_requests_get = mock_dependencies
    mock_requests_get.side_effect = requests.exceptions.Timeout("Request timed out")

    result = client.main()

    assert result is None
    assert "请求截图服务器超时。" in caplog.text

def test_main_json_decode_error(mock_dependencies, caplog):
    """
    测试 main 函数在服务器返回非 JSON 响应时的行为。
    """
    mock_requests_get = mock_dependencies
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "doc", 0)
    mock_response.text = "Not a JSON string" # 模拟响应文本
    mock_requests_get.return_value = mock_response

    result = client.main()

    assert result is None
    assert "截图服务器返回非JSON响应: Not a JSON string" in caplog.text

def test_main_generic_exception(mock_dependencies, caplog):
    """
    测试 main 函数在发生其他未知异常时的行为。
    """
    mock_requests_get = mock_dependencies
    mock_requests_get.side_effect = Exception("Something unexpected happened")

    result = client.main()

    assert result is None
    assert "调用截图服务器异常: Something unexpected happened" in caplog.text

def test_main_script_execution_success(mocker, caplog):
    """
    测试脚本作为主程序执行时，成功情况下的行为。
    """
    # 模拟 main 函数的返回值
    mocker.patch('screenshot_client.main', return_value="/tmp/test_screenshots/screenshot_main.png")
    
    # 模拟 print 函数，捕获其输出
    mock_print = mocker.patch('builtins.print')

    # 模拟 os.path.abspath 和 os.path.dirname，因为它们在顶层被调用
    mocker.patch('os.path.abspath', return_value='/mock/path/to/screenshot_client.py')
    mocker.patch('os.path.dirname', return_value='/mock/path/to')

    # 重新加载模块以触发 __name__ == '__main__' 块
    # 注意：这是一种高级技巧，通常在测试模块的顶层逻辑时使用
    # 确保在测试完成后清理 sys.modules
    with mock.patch.dict(sys.modules, {'screenshot_client': sys.modules['screenshot_client']}):
        # 移除模块以强制重新加载
        if 'screenshot_client' in sys.modules:
            del sys.modules['screenshot_client']
        
        # 重新导入模块，这将执行 __name__ == '__main__' 块
        import screenshot_client as reloaded_client
        
        # 验证 main 函数被调用
        reloaded_client.main.assert_called_once()
        
        # 验证 print 函数被调用并输出正确路径
        mock_print.assert_called_once_with("/tmp/test_screenshots/screenshot_main.png")
        
        # 验证日志
        assert '__main__ 入口被执行 (客户端模式)' in caplog.text

def test_main_script_execution_failure(mocker, caplog):
    """
    测试脚本作为主程序执行时，失败情况下的行为。
    """
    mocker.patch('screenshot_client.main', return_value=None)
    mock_print = mocker.patch('builtins.print')

    mocker.patch('os.path.abspath', return_value='/mock/path/to/screenshot_client.py')
    mocker.patch('os.path.dirname', return_value='/mock/path/to')

    with mock.patch.dict(sys.modules, {'screenshot_client': sys.modules['screenshot_client']}):
        if 'screenshot_client' in sys.modules:
            del sys.modules['screenshot_client']
        
        import screenshot_client as reloaded_client
        
        reloaded_client.main.assert_called_once()
        mock_print.assert_not_called() # 失败时不会调用 print
        assert '截图失败' in caplog.text