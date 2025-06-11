.
├── config
│   ├── config.json
│   ├── history.json
│   └── system_prompt_config.md
├── data
│   ├── cache_screenshot
│   ├── data.json
│   └── gemini_answer.json
├── function
│   ├── get_time_module
│   │   └── __init__.py
│   ├── get_transaction_history.py
│   ├── __init__.py
│   ├── kline_pattern_analyzer.py
│   ├── list.py
│   ├── logs
│   │   └── trade.log
│   ├── __pycache__
│   │   ├── get_time.cpython-313.pyc
│   │   ├── get_transaction_history.cpython-313.pyc
│   │   ├── __init__.cpython-313.pyc
│   │   ├── kline_pattern_analyzer.cpython-313.pyc
│   │   ├── place_order.cpython-313.pyc
│   │   └── tp_sl.cpython-313.pyc
│   ├── tp_sl.py
│   ├── trade
│   │   ├── data_consistency.py
│   │   ├── __init__.py
│   │   ├── monitor.py
│   │   ├── okx_client.py
│   │   ├── place_algo_order.py
│   │   ├── place_order.py
│   │   ├── __pycache__
│   │   │   ├── data_consistency.cpython-313.pyc
│   │   │   ├── __init__.cpython-313.pyc
│   │   │   ├── monitor.cpython-313.pyc
│   │   │   ├── okx_client.cpython-313.pyc
│   │   │   ├── place_order.cpython-313.pyc
│   │   │   ├── retry.cpython-313.pyc
│   │   │   ├── risk_control.cpython-313.pyc
│   │   │   ├── tp_sl.cpython-313.pyc
│   │   │   └── trade_history.cpython-313.pyc
│   │   ├── retry.py
│   │   ├── risk_control.py
│   │   ├── tp_sl.py
│   │   ├── trade_history.py
│   │   └── trade_logger.py
│   ├── trade_logger.py
│   ├── utils
│   │   ├── __init__.py
│   │   └── __pycache__
│   │       └── __init__.cpython-313.pyc
│   └── utils.py
├── logs
│   ├── main.log
│   ├── think_log.md
│   ├── trade_auto.log
│   ├── trade_history.json
│   ├── trade.log
│   └── trade_log.json
├── merge_screenshots.py
├── output_tree.txt
├── pyproject.toml
├── README.md
├── requirements.txt
├── src
│   ├── auto_trader.py
│   ├── data_server.py
│   ├── downloads
│   │   ├── ETHUSD.P_2025-06-11_22-11-31.png
│   │   ├── ETHUSD.P_2025-06-11_22-11-35.png
│   │   └── ETHUSD.P_2025-06-11_22-11-38.png
│   ├── gemini_api_caller.py
│   ├── get_data
│   │   ├── get_positions.py
│   │   ├── macro_factor_collector.py
│   │   ├── position_info_widget.py
│   │   ├── __pycache__
│   │   │   ├── get_positions.cpython-313.pyc
│   │   │   ├── macro_factor_collector.cpython-311.pyc
│   │   │   ├── macro_factor_collector.cpython-313.pyc
│   │   │   ├── technical_indicator_collector.cpython-313.pyc
│   │   │   └── tradingview_auto_screenshot.cpython-313.pyc
│   │   ├── technical_indicator_collector.py
│   │   └── tradingview_auto_screenshot.py
│   ├── main_get.py
│   ├── main.py
│   ├── __pycache__
│   │   ├── auto_trader.cpython-313.pyc
│   │   ├── get_positions.cpython-313.pyc
│   │   ├── macro_factor_collector.cpython-313.pyc
│   │   ├── main.cpython-313.pyc
│   │   ├── main_get.cpython-313.pyc
│   │   ├── technical_indicator_collector.cpython-312.pyc
│   │   └── technical_indicator_collector.cpython-313.pyc
│   ├── reply_cache
│   │   ├── gemini.json
│   │   └── gemini.txt
│   ├── screenshots
│   │  
│   └── taishang.egg-info
│       ├── dependency_links.txt
│       ├── PKG-INFO
│       ├── SOURCES.txt
│       └── top_level.txt
├── taishang.egg-info
│   ├── dependency_links.txt
│   ├── PKG-INFO
│   ├── requires.txt
│   ├── SOURCES.txt
│   └── top_level.txt
├── tests
│   ├── __pycache__
│   │   ├── test_main.cpython-313.pyc
│   │   └── test_screenshot_client.cpython-313-pytest-8.4.0.pyc
│   ├── test_main.py
│   └── test_screenshot_client.py
├── todo.md
├── uv.lock