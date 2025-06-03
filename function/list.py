# ================= 本地 tools (保持不变) =================
def get_transaction_history(target: str) -> dict:
    """
    Args:
        target: 目标（例如，'ETH-USDT'）
    Returns:
        最近3条交易历史记录 (JSON 格式)
    """
    import subprocess
    logger.info(f"{MODULE_TAG}运行本地 get_transaction_history.py")
    try:
        trade_log_process = subprocess.run(
            [config["python_path"]["global"], config["path"]["function_path"]["get_transaction_history"]],
            capture_output=True, text=True, timeout=360, check=True
        )
        trade_log = trade_log_process.stdout
        logger.info(f"{MODULE_TAG}本地获取最后3条交易纪录完成")
        try:
            res = json.loads(trade_log)
        except json.JSONDecodeError:
            res = {"transaction_history": trade_log.strip()}
        return {"transaction_history":res, "source": "local"} # 添加 source
    except subprocess.CalledProcessError as e:
        logger.error(f"{MODULE_TAG}本地 get_transaction_history.py 脚本执行失败: {e.stderr}")
        return {"error": f"本地脚本执行失败: {e.stderr}"}
    except Exception as e:
        logger.error(f"{MODULE_TAG}本地 get_transaction_history 调用异常: {e}")
        return {"error": f"本地调用异常: {e}"}

get_transaction_history_declaration = {
    "name": "get_transaction_history",
    "description": "获取最近3条交易历史记录 (本地执行)",
    "parameters": {
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "description": "要获取交易历史记录的目标（例如，'ETH-USDT'）"
            },
        },
        "required": ["target"]
    }
}

def get_time(target: str) -> dict:
    """
    Args:
        target: 获取时间的上下文目标（例如，'当前时间'）
    Returns:
        当前时间 (JSON 格式)
    """
    import subprocess
    logger.info(f"{MODULE_TAG}运行本地 get_time.py")
    try:
        time_process = subprocess.run(
            [config["python_path"]["global"], config["path"]["function_path"]["get_time"]],
            capture_output=True, text=True, timeout=360, check=True
        )
        current_time = time_process.stdout.strip()
        logger.info(f"{MODULE_TAG}本地获取当前时间完成")
        res =  current_time
        return {"time":res, "source": "local"} # 添加 source
    except subprocess.CalledProcessError as e:
        logger.error(f"{MODULE_TAG}本地 get_time.py 脚本执行失败: {e.stderr}")
        return {"error": f"本地脚本执行失败: {e.stderr}"}
    except Exception as e:
        logger.error(f"{MODULE_TAG}本地 get_time 调用异常: {e}")
        return {"error": f"本地调用异常: {e}"}

get_time_declaration = {
    "name": "get_time",
    "description": "获取当前时间 (本地执行)",
    "parameters": {
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "description": "获取时间的上下文目标（例如，'当前时间'）"
            },
        },
        "required": ["target"]
    }
}

def execute_python_code(code: str) -> dict:
    """
    Executes the given Python code string in a separate process.

    Args:
        code: The Python code to execute as a string.

    Returns:
        A dictionary containing the execution result (stdout, stderr, returncode).
    """
    import subprocess
    import sys
    logger.info(f"{MODULE_TAG}Executing Python code:\n{code}")
    try:
        # Use sys.executable to ensure the same Python interpreter is used
        process = subprocess.run([sys.executable, "-c", code],
                                 capture_output=True,
                                 text=True,
                                 timeout=180, # Set a timeout to prevent infinite loops
                                 check=False) # Don't raise exception on non-zero exit code

        return {
            "stdout": process.stdout,
            "stderr": process.stderr,
            "returncode": process.returncode,
            "source": "local_execution"
        }
    except Exception as e:
        logger.error(f"{MODULE_TAG}Error executing Python code: {e}")
        return {
            "stdout": "",
            "stderr": str(e),
            "returncode": 1,
            "source": "local_execution"
        }

execute_python_code_declaration = {
    "name": "execute_python_code",
    "description": "Executes arbitrary Python code provided as a string. This tool is useful for performing calculations, processing data, or running any standard Python logic. It returns a dictionary containing the standard output (stdout), standard error (stderr), and the return code of the execution. The code should be provided as a single string in the 'code' parameter.",
    "parameters": {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "The Python code to execute as a string."
            },
        },
        "required": ["code"]
    }
}

# ================= 本地 tools END =================

