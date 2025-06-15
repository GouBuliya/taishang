import sys
import os
import psutil # 引入psutil库

# 确保项目根目录在sys.path中（避免重复添加）
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import subprocess
import time
import datetime
import requests
import logging
import json
import argparse
from src.data.collector_service import main as get_main
from src.trading.engine.auto_trader import main as auto_trade_main  # 添加自动交易模块导入
from src.core.retry_manager import retry, RetryManager
from src.core.exception_handler import setup_global_exception_handler, safe_execute
from src.core.path_manager import path_manager
import datetime
from typing import Optional
from src.ai.models.gemini_critic import main as critic_main
from src.data.critic_data_integrator import integrate_data_for_critic

# Configure logging (similar to other scripts for consistency)
# 获取项目根目录
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
config_path = os.path.join(project_root, "config/config.json")
config = json.load(open(config_path, "r"))
LOG_FILE = path_manager.get_log_path("main_log")

# Prevent duplicate handlers
if not logging.getLogger("GeminiQuant").handlers:
    logging.basicConfig(
        level=logging.INFO,
        format='[主控脚本][%(asctime)s] [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S',
        handlers=[logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8'), logging.StreamHandler()]
    )

logger = logging.getLogger("GeminiQuant")

# TODO: 将这些硬编码的URL移到config.json中，提高配置的灵活性
DATA_SERVER_URL = "http://127.0.0.1:5002"
HEALTH_ENDPOINT = f"{DATA_SERVER_URL}/health"

# 全局调试模式标志
DEBUG_MODE = False

def wait_for_server(url: str, timeout: int = 60, retry_interval: int = 5) -> bool:
    """
    等待指定的URL返回健康状态。

    通过轮询健康检查端点来确认服务是否准备就绪。
    这在启动依赖服务（如数据服务器）时非常有用，可以确保主流程在服务可用后才继续。

    Args:
        url (str): 要检查的健康端点URL。
        timeout (int): 等待的總秒数。
        retry_interval (int): 每次重试之间的间隔秒数。

    Returns:
        bool: 如果服务器在超时内返回健康状态，则为True，否则为False。
    """
    logger.info(f"正在等待服务器启动并响应健康检查: {url}")
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get(url, timeout=retry_interval) # Use retry_interval as request timeout
            if response.status_code == 200:
                data = response.json()
                status = data.get("status")
                # 接受 ok, starting, degraded 状态都算成功
                if status in ["ok", "starting", "degraded"]:
                    logger.info(f"服务器健康检查通过，状态: {status}")
                    return True
                else:
                    logger.warning(f"服务器返回未知状态: {status}")
            else:
                logger.warning(f"服务器返回非200状态码: {response.status_code}")
        except requests.exceptions.ConnectionError:
            logger.info(f"无法连接到服务器，等待 {retry_interval} 秒后重试...")
        except requests.exceptions.Timeout:
             logger.warning(f"健康检查请求超时，等待 {retry_interval} 秒后重试...")
        except Exception as e:
            logger.error(f"健康检查过程中发生未知错误: {e}")

        time.sleep(retry_interval)

    logger.error("等待服务器超时，服务器未能成功启动或响应健康检查。")
    return False

# TODO: 重构此函数，使其不依赖于命令行工具（如pkill），而是通过更可靠的进程管理方式（如PID文件）来控制子进程。
def restart_data_server() -> Optional[subprocess.Popen]:
    """
    重启数据服务器。

    该函数首先尝试终止任何现有的数据服务器进程，然后启动一个新的实例。
    这确保了我们总是在一个干净的状态下启动服务。

    Returns:
        Optional[subprocess.Popen]: 如果成功启动，则返回子进程对象，否则返回None。
    """
    logger.info("正在重启数据服务器...")
    # 尝试杀死现有进程
    try:
        # Use pkill with -f to match the full command line
        subprocess.run(['pkill', '-f', 'src/infrastructure/web/data_server.py'], check=False)
        logger.info('已尝试杀死现有数据服务器进程。')
    except Exception as e:
        logger.warning(f'杀死数据服务器进程失败或没有运行中的进程: {e}')

    # 启动新的服务器进程
    # Use subprocess.Popen to run in the background
    try:
        # Assuming uv is in the PATH and the script is run from the workspace root
        server_process = subprocess.Popen(['uv', 'run', 'src/infrastructure/web/data_server.py'])
        logger.info(f"已启动新的数据服务器进程，PID: {server_process.pid}")
        return server_process
    except Exception as e:
        logger.critical(f"启动数据服务器失败: {e}")
        return None

# TODO: 未来可以考虑将gemini_controller重构为一个类，并直接调用其方法，而不是通过子进程。
# 这样可以更好地控制执行、传递参数和处理结果，同时降低进程间通信的开销。
@retry(max_tries=3, delay_seconds=2, backoff=2, exceptions=(subprocess.CalledProcessError, Exception))
def run_gemini_api_caller(prompt_suffix: Optional[str] = None, think_mode: bool = False) -> bool:
    """
    运行 Gemini API 调用脚本。

    Args:
        prompt_suffix (Optional[str]): 要附加到主提示词末尾的额外文本。
        think_mode (bool): 是否开启思考模式。
    
    Returns:
        bool: 脚本是否成功运行。
    """
    logger.info("正在运行 Gemini API 调用脚本...")
    try:
        # Assuming uv is in the PATH and the script is run from the workspace root
        # Run in foreground, wait for completion
        # TODO: 替换为更健壮的Python可执行文件路径发现机制，而不是依赖`uv run`
        command = ['uv', 'run', 'src/ai/models/gemini_controller.py']
        if prompt_suffix:
            command.extend(['--append-prompt', prompt_suffix])
        if think_mode:
            command.append('--think')
        
        result = subprocess.run(command, check=True)
        logger.info(f"Gemini API 调用脚本运行完成，返回码: {result.returncode}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Gemini API 调用脚本运行失败: {e}")
        raise  # 让重试装饰器处理
    except Exception as e:
        logger.error(f"运行 Gemini API 调用脚本时发生未知错误: {e}")
        raise  # 让重试装饰器处理

@retry(max_tries=2, delay_seconds=2, backoff=2, exceptions=(subprocess.CalledProcessError, Exception))
def run_critic_review(current_iteration: int = 1, max_iterations: int = 3) -> bool:
    """
    运行谏官审查模块，对AI决策进行审查。
    
    Args:
        current_iteration: 当前迭代次数
        max_iterations: 最大迭代次数
    
    Returns:
        bool: 审查是否通过（True表示通过，False表示需要修正）。
    """
    logger.info(f"正在运行谏官审查模块（第{current_iteration}次迭代）...")
    try:
        # 读取Controller的决策结果
        controller_answer_path = os.path.join(project_root, config["logs"]["Controller_answer_path"])
        if not os.path.exists(controller_answer_path):
            logger.error(f"Controller决策文件不存在: {controller_answer_path}")
            return False
        
        with open(controller_answer_path, "r", encoding="utf-8") as f:
            controller_decision = json.load(f)
        
        # 使用数据整合器整合完整的谏官输入数据
        logger.info("正在整合谏官所需的完整数据...")
        try:
            integrated_data = integrate_data_for_critic(
                decision_maker_output=controller_decision,
                current_iteration=current_iteration,
                max_iterations=max_iterations
            )
            logger.info("数据整合完成")
        except Exception as e:
            logger.error(f"数据整合失败: {e}")
            # 如果数据整合失败，回退到传统模式
            logger.warning("回退到传统的简单数据格式")
            integrated_data = controller_decision
        
        # 调用谏官模块进行审查
        critic_result = critic_main(integrated_data)
        
        # 保存谏官审查结果
        critic_answer_path = os.path.join(project_root, config["logs"]["Critic_answer_path"])
        
        # 解析谏官的输出
        if critic_result and len(critic_result) > 0:
            # 将输出列表合并为字符串，然后尝试解析JSON
            critic_output = "".join(critic_result)
            try:
                # 尝试从输出中提取JSON
                import re
                json_match = re.search(r'\{.*\}', critic_output, re.DOTALL)
                if json_match:
                    critic_json = json.loads(json_match.group())
                    
                    # 添加迭代信息到审查结果
                    critic_json["iteration_info"] = {
                        "current_iteration": current_iteration,
                        "max_iterations": max_iterations,
                        "timestamp": datetime.datetime.now().isoformat()
                    }
                    
                    # 保存审查结果
                    with open(critic_answer_path, "w", encoding="utf-8") as f:
                        json.dump(critic_json, f, ensure_ascii=False, indent=4)
                    
                    # 检查审查状态 - 修改逻辑：只要没有致命错误就通过
                    status = critic_json.get("status", "Needs Revision")
                    critique_report = critic_json.get("critique_report", [])
                    
                    # 检查是否有致命错误
                    has_critical_error = False
                    for issue in critique_report:
                        severity = issue.get('severity', 'Unknown').lower()
                        description = issue.get('description', 'No description')
                        logger.info(f"审查问题 [{severity.upper()}]: {description}")
                        
                        # 只有Critical级别的错误才被认为是致命错误
                        if severity == 'critical':
                            has_critical_error = True
                            logger.error(f"发现致命错误: {description}")
                    
                    if status == "Approved" or not has_critical_error:
                        if status == "Approved":
                            logger.info(f"谏官审查通过（第{current_iteration}次迭代），决策获得批准。")
                        else:
                            logger.info(f"谏官审查通过（第{current_iteration}次迭代），虽有非致命问题但允许执行。")
                            logger.info(f"发现 {len(critique_report)} 个非致命问题，但系统将继续执行。")
                        return True
                    else:
                        logger.warning(f"谏官审查未通过（第{current_iteration}次迭代），发现致命错误，需要重新决策。")
                        return False
                else:
                    logger.error("无法从谏官输出中提取有效的JSON格式")
                    return False
            except json.JSONDecodeError as e:
                logger.error(f"解析谏官输出JSON失败: {e}")
                logger.error(f"原始输出: {critic_output}")
                return False
        else:
            logger.error("谏官模块返回空结果")
            return False
            
    except Exception as e:
        logger.error(f"运行谏官审查模块时发生异常: {e}")
        raise  # 让重试装饰器处理

def run_auto_trader(dry_run: bool = False) -> bool:
    """
    运行自动交易系统。

    Args:
        dry_run (bool): 是否为模拟运行模式。
    """
    logger.info("正在运行自动交易系统...")
    if dry_run:
        logger.info("模式: Dry Run (模拟运行)")
    try:
        # 注意：这里需要修改 auto_trader.py 的 main 函数来接受 dry_run 参数
        if auto_trade_main(dry_run=dry_run):
            logger.info("自动交易系统运行完成")
            return True
    except Exception as e:
        logger.error(f"执行交易时发生顶层异常: {e}", exc_info=True)
        return False

def parse_arguments() -> argparse.Namespace:
    """
    解析命令行参数。
    
    Returns:
        argparse.Namespace: 解析后的命令行参数对象。
    """
    parser = argparse.ArgumentParser(description='太熵量化交易系统 - 主控制器', formatter_class=argparse.RawTextHelpFormatter)

    # 调试与模式控制
    group_mode = parser.add_argument_group('调试与模式控制')
    group_mode.add_argument('--debug', '-d', action='store_true', 
                       help='启用调试模式：立即执行一次完整交易流程后退出')
    group_mode.add_argument('--debug-loop', action='store_true',
                       help='启用调试循环模式：连续执行交易流程，无时间等待')
    group_mode.add_argument('--dry-run', action='store_true',
                       help='模拟运行模式：执行所有步骤，但不会实际下单交易')
    group_mode.add_argument('--think', action='store_true',
                       help='思考摘要模式：在AI决策时，实时打印模型的思考过程和代码输出')

    # 配置与路径
    group_config = parser.add_argument_group('配置与路径')
    group_config.add_argument('--config', type=str, default=None,
                        help='指定自定义的config.json配置文件路径')
    group_config.add_argument('--log-level', type=str, default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        help='设置日志记录级别 (默认为: INFO)')

    # 服务器与服务
    group_server = parser.add_argument_group('服务器与服务')
    group_server.add_argument('--skip-server', action='store_true',
                       help='跳过数据服务器启动（假设服务器已运行）')
    
    # 帮助
    group_help = parser.add_argument_group('帮助')
    group_help.add_argument('--help-debug', action='store_true',
                       help='显示调试模式详细说明')
    
    # 在测试环境中，sys.argv可能包含pytest的参数，这会导致解析错误。
    # TODO: 考虑使用更灵活的配置方式（如环境变量或配置文件）来代替命令行参数，以简化测试。
    known_args, _ = parser.parse_known_args()
    return known_args

def show_debug_help():
    """显示调试模式帮助信息"""
    help_text = """
🔧 太熵量化交易系统 - 调试模式说明

调试模式选项：
  --debug, -d          : 单次调试模式
                        - 立即启动数据服务器
                        - 执行一次完整的交易流程
                        - 执行完成后退出程序
                        
  --debug-loop         : 循环调试模式  
                        - 连续执行交易流程
                        - 无30分钟时间间隔等待
                        - 适合快速测试和调试
                        
  --skip-server        : 跳过服务器启动
                        - 假设数据服务器已在运行
                        - 直接执行交易流程
                        - 适合服务器已启动的情况

使用示例：
  uv run python3 src/main.py --debug           # 单次调试运行
  uv run python3 src/main.py --debug-loop     # 循环调试运行
  uv run python3 src/main.py --skip-server    # 跳过服务器启动
  uv run python3 src/main.py                  # 正常生产模式

注意：调试模式会跳过时间检查，立即执行交易分析和决策。
"""
    print(help_text)

# 全局变量：累积谏官反馈
cumulative_critic_feedback = []

def add_critic_feedback_to_cumulative(attempt_number: int) -> bool:
    """
    将当前谏官反馈添加到累积反馈列表中。
    
    Args:
        attempt_number (int): 当前尝试次数
    
    Returns:
        bool: 是否成功添加反馈
    """
    global cumulative_critic_feedback
    
    try:
        critic_answer_path = os.path.join(project_root, config["logs"]["Critic_answer_path"])
        if not os.path.exists(critic_answer_path):
            logger.warning(f"第{attempt_number}次：未找到谏官审查结果文件")
            return False
        
        with open(critic_answer_path, "r", encoding="utf-8") as f:
            critic_result = json.load(f)
        
        critique_report = critic_result.get("critique_report", [])
        if not critique_report:
            logger.warning(f"第{attempt_number}次：谏官审查结果为空")
            return False
        
        # 添加当前反馈到累积列表
        feedback_entry = {
            "attempt": attempt_number,
            "timestamp": critic_result.get("timestamp", "未知时间"),
            "status": critic_result.get("status", "Needs Revision"),
            "critique_report": critique_report
        }
        
        cumulative_critic_feedback.append(feedback_entry)
        logger.info(f"已将第{attempt_number}次谏官反馈添加到累积反馈中，当前累积{len(cumulative_critic_feedback)}轮反馈")
        
        return True
        
    except Exception as e:
        logger.error(f"添加第{attempt_number}次谏官反馈时发生异常: {e}")
        return False

def get_cumulative_critic_feedback_as_prompt() -> str:
    """
    从累积的谏官审查结果中生成包含所有历史反馈的提示词。
    
    Returns:
        str: 基于所有历史谏官反馈的提示词
    """
    global cumulative_critic_feedback
    
    if not cumulative_critic_feedback:
        logger.warning("没有累积的谏官反馈，使用通用重试提示")
        return "你的上一个指令在执行时失败，请检查指令的JSON格式、价格、止盈止损等参数的正确性和逻辑合理性，然后重新生成指令。"
    
    try:
        # 构建包含所有历史反馈的提示词
        feedback_parts = [f"根据这一轮交易流程中的{len(cumulative_critic_feedback)}次谏官审查结果，你需要修正以下累积发现的问题：\n"]
        
        issue_counter = 1
        for round_idx, feedback_entry in enumerate(cumulative_critic_feedback, 1):
            attempt = feedback_entry.get("attempt", round_idx)
            critique_report = feedback_entry.get("critique_report", [])
            
            if critique_report:
                feedback_parts.append(f"=== 第{attempt}次决策 - 谏官审查发现的问题 ===")
                
                for issue in critique_report:
                    severity = issue.get('severity', 'Unknown')
                    description = issue.get('description', '未提供描述')
                    suggested_correction = issue.get('suggested_correction', '请重新评估')
                    
                    feedback_parts.append(f"{issue_counter}. [{severity}] {description}")
                    feedback_parts.append(f"   修正建议：{suggested_correction}")
                    issue_counter += 1
                
                feedback_parts.append("")  # 空行分隔
        
        feedback_parts.append("=== 重要提醒 ===")
        feedback_parts.append("以上是这一轮交易流程中所有谏官审查发现的问题。请仔细阅读所有历史反馈，确保：")
        feedback_parts.append("1. 不要重复之前已经发现和指出的错误")
        feedback_parts.append("2. 综合考虑所有反馈，进行全面的修正")
        feedback_parts.append("3. 特别注意Critical级别的问题，必须完全解决")
        feedback_parts.append("4. 学习之前的错误模式，避免类似问题再次出现")
        feedback_parts.append("\n请基于以上完整的历史反馈，重新分析市场数据，修正所有发现的问题，并生成新的交易决策。")
        
        return "\n".join(feedback_parts)
        
    except Exception as e:
        logger.error(f"生成累积谏官反馈提示词时发生异常: {e}")
        return "你的上一个决策未通过谏官审查，请重新分析市场数据并生成更加合理的交易决策。"

def reset_cumulative_critic_feedback():
    """重置累积谏官反馈，用于新的交易流程开始时。"""
    global cumulative_critic_feedback
    cumulative_critic_feedback = []
    logger.info("已重置累积谏官反馈，开始新的交易流程")

def run_full_trade_flow(args: argparse.Namespace) -> bool:
    """
    执行一次完整的交易流程，从数据收集到交易执行。
    
    优化设计：
    - 数据收集只执行一次，确保所有决策尝试基于相同的市场数据
    - 谏官审查失败后直接重新决策，不重新收集数据
    - 交易执行失败后也直接重新决策，不重新收集数据
    
    Args:
        args (argparse.Namespace): 解析后的命令行参数。

    Returns:
        bool: 交易流程是否成功执行。
    """
    try:
        # 0. 重置累积谏官反馈，开始新的交易流程
        reset_cumulative_critic_feedback()
        
        # 1. 运行数据收集（只执行一次，确保所有后续决策基于相同数据）
        logger.info("正在运行数据收集模块...")
        get_main()
        logger.info("数据收集模块运行完成。所有后续决策将基于这份数据进行。")

        # 2. 基于收集的数据进行决策-审查-执行循环
        success = False
        # 交易执行失败后重新决策的通用提示词
        EXECUTION_FAILURE_PROMPT = "你的上一个指令在交易执行时失败，请检查指令的JSON格式、价格、止盈止损等参数的正确性和逻辑合理性，然后重新生成指令。"
        
        # 跟踪上次失败的原因：'critic' 表示谏官审查失败，'execution' 表示交易执行失败
        last_failure_reason = None

        for attempt in range(10):
            if attempt == 0:
                logger.info(f"开始第 {attempt + 1} 次决策尝试（基于已收集的市场数据）...")
            else:
                logger.info(f"开始第 {attempt + 1} 次重新决策（不重新收集数据）...")
            
            # 根据上次失败原因确定提示词
            prompt_to_use = None
            if attempt > 0:
                if last_failure_reason == 'critic':
                    # 使用累积的谏官反馈
                    prompt_to_use = get_cumulative_critic_feedback_as_prompt()
                    logger.info(f"本次为谏官审查失败后重新决策，使用累积谏官反馈作为提示词")
                elif last_failure_reason == 'execution':
                    # 使用执行失败的通用提示词
                    prompt_to_use = EXECUTION_FAILURE_PROMPT
                    logger.info(f"本次为交易执行失败后重新决策，使用执行失败提示词")
                else:
                    # 兜底情况
                    prompt_to_use = EXECUTION_FAILURE_PROMPT
                    logger.info(f"本次为重试，使用通用失败提示词")
                
                logger.info(f"附加提示词: '{prompt_to_use[:200]}...'")

            try:
                # 调用AI决策（基于已收集的数据）
                run_gemini_api_caller(prompt_suffix=prompt_to_use, think_mode=args.think)
                
                # 谏官审查决策
                critic_passed = run_critic_review(current_iteration=attempt + 1, max_iterations=10)
                if not critic_passed:
                    # 将当前谏官反馈添加到累积反馈中
                    add_critic_feedback_to_cumulative(attempt + 1)
                    logger.warning(f"第 {attempt + 1} 次谏官审查未通过，将直接重新决策（不重新收集数据）...")
                    last_failure_reason = 'critic'
                    continue
                
                # 执行交易
                if run_auto_trader(dry_run=args.dry_run):
                    logger.info(f"第 {attempt + 1} 次交易尝试成功。")
                    success = True
                    break
                else:
                    logger.warning(f"第 {attempt + 1} 次自动交易执行失败或返回了否定信号，将直接重新决策（不重新收集数据）...")
                    last_failure_reason = 'execution'
            except Exception as e:
                logger.error(f"第 {attempt + 1} 次尝试过程中发生异常: {e}")
                last_failure_reason = 'execution'
        
        if success:
            logger.info("交易流程执行成功")
        else:
            logger.error("所有重试均失败，交易流程执行失败")
            
        return success
        
    except Exception as e:
        logger.error(f"执行交易流程时发生异常: {e}")
        logger.exception(e)
        return False

def run_debug_loop(args: argparse.Namespace):
    """
    在调试循环模式下运行，连续执行交易流程。
    
    Args:
        args (argparse.Namespace): 解析后的命令行参数。
    """
    run_count = 0
    while True:
        run_count += 1
        logger.info(f"--- 开始第 {run_count} 轮调试循环 ---")
        try:
            run_full_trade_flow(args)
            logger.info(f"--- 第 {run_count} 轮调试循环完成 ---")
        except Exception as e:
            logger.error(f"在第 {run_count} 轮调试循环中发生严重错误: {e}", exc_info=True)
            logger.info("系统将在60秒后尝试重启主循环...")
            time.sleep(60)

def kill_existing_processes():
    """查找并终止任何已在运行的 main_controller.py 进程，防止重复运行。"""
    current_pid = os.getpid()
    script_name = os.path.basename(__file__)
    
    killed_count = 0
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            # 检查进程命令行中是否包含脚本名
            if script_name in proc.info['cmdline'] and proc.info['pid'] != current_pid:
                logger.warning(f"发现已在运行的旧进程: PID={proc.info['pid']}, 命令行: {' '.join(proc.info['cmdline'])}")
                p = psutil.Process(proc.info['pid'])
                p.terminate()  # 发送终止信号
                p.wait(timeout=3) # 等待进程终止
                logger.info(f"已成功终止旧进程 (PID: {proc.info['pid']})")
                killed_count += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired) as e:
            logger.error(f"终止旧进程 (PID: {proc.info.get('pid')}) 时出错: {e}")
        except Exception as e:
            # 捕获其他可能的异常，例如proc.info['cmdline']为空的情况
            continue
            
    if killed_count > 0:
        logger.info(f"共终止了 {killed_count} 个旧的进程实例。")

def main():
    """
    系统主入口函数。
    
    负责初始化、参数解析、模式选择和启动相应的执行循环。
    """
    # 在最开始就执行查杀逻辑
    kill_existing_processes()

    global DEBUG_MODE
    global config
    
    # 解析命令行参数
    args = parse_arguments()
    
    # 1. 根据参数重新加载配置和设置日志级别
    if args.config:
        logger.info(f"加载指定配置文件: {args.config}")
        with open(args.config, "r", encoding="utf-8") as f:
            config = json.load(f)
    
    log_level_map = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }
    effective_log_level = log_level_map.get(args.log_level.upper(), logging.INFO)
    logging.getLogger("GeminiQuant").setLevel(effective_log_level)
    logger.info(f"日志级别已设置为: {args.log_level}")

    # 显示调试帮助
    if args.help_debug:
        show_debug_help()
        return
    
    # 设置调试模式
    DEBUG_MODE = args.debug or args.debug_loop
    
    # 设置全局异常处理器
    setup_global_exception_handler()
    
    logger.info("=== 太熵量化交易系统启动 ===")
    if DEBUG_MODE:
        mode_name = "单次调试模式" if args.debug else "循环调试模式"
        logger.info(f"🔧 运行模式: {mode_name}")
    else:
        logger.info("🚀 运行模式: 生产模式")
    
    # 1. 启动数据服务器（除非跳过）
    if not args.skip_server:
        server_process = restart_data_server()
        if server_process is None:
            logger.critical("数据服务器启动失败，主控脚本退出。")
            exit(1)

        # 等待服务器启动完成并自检通过
        time.sleep(15)  # Initial wait
        if not wait_for_server(HEALTH_ENDPOINT, timeout=120, retry_interval=10):
            logger.critical("数据服务器未能在规定时间内启动并自检通过，主控脚本退出。")
            exit(1)
    else:
        logger.info("跳过数据服务器启动，假设服务器已运行")

    # 4. 根据模式执行
    if args.debug:
        logger.info("启用调试模式，将执行一次完整的交易流程。")
        success = run_full_trade_flow(args)
        logger.info(f"调试模式执行完成，结果: {'成功' if success else '失败'}")
    elif args.debug_loop:
        logger.info("启用调试循环模式，将连续执行交易流程。")
        run_debug_loop(args)
    else:
        logger.info("启用生产模式，将在每30分钟的整点时执行（如9:00、9:30、10:00等）。")
        while True:
            try:
                # 获取当前时间
                now = datetime.datetime.now()
                current_minute = now.minute
                
                # 检查是否是30分钟的整点（分钟数能被30整除）
                if current_minute % 30 == 0:
                    logger.info(f"当前时间 {now.strftime('%H:%M')} 符合执行条件，开始执行交易流程...")
                    run_full_trade_flow(args)
                    logger.info("交易流程执行完成。")
                    
                    # 等待到下一分钟，避免在同一分钟内重复执行
                    time.sleep(60)
                else:
                    # 计算到下一个30分钟整点的等待时间
                    if current_minute < 30:
                        next_target_minute = 30
                    else:
                        next_target_minute = 60
                    
                    wait_minutes = next_target_minute - current_minute
                    wait_seconds = wait_minutes * 60 - now.second
                    
                    next_time = now.replace(minute=next_target_minute % 60, second=0, microsecond=0)
                    if next_target_minute == 60:
                        next_time = next_time.replace(hour=(now.hour + 1) % 24)
                    
                    logger.info(f"当前时间 {now.strftime('%H:%M:%S')}，下次执行时间: {next_time.strftime('%H:%M:%S')}，等待 {wait_seconds} 秒...")
                    time.sleep(wait_seconds)
                    
            except KeyboardInterrupt:
                logger.info("检测到手动中断，正在正常关闭系统...")
                break
            except Exception as e:
                logger.error(f"在主循环中发生未捕获的错误: {e}", exc_info=True)
                logger.info("系统将在60秒后尝试重启主循环...")
                time.sleep(60)

if __name__ == "__main__":
    main()