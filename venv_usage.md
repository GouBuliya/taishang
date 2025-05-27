# Qwen_quant_v1 Python 虚拟环境使用说明

本项目推荐使用 Python venv 虚拟环境进行依赖隔离和管理，避免与系统环境冲突。

## 创建虚拟环境

1. 进入项目根目录：
   ```zsh
   cd Qwen_quant_v1
   ```
2. 创建虚拟环境（假设使用 Python 3.9+）：
   ```zsh
   python3 -m venv venv
   ```
   > 如需指定 Python 版本，可用 `python3.9 -m venv venv`

3. 激活虚拟环境：
   - Linux/macOS:
     ```zsh
     source venv/bin/activate
     ```
   - Windows:
     ```bat
     venv\Scripts\activate
     ```

4. 安装依赖：
   ```zsh
   pip install -r requirements.txt
   ```

5. 运行项目：
   ```zsh
   python3 code/web_gui/app.py
   ```

## 退出虚拟环境

```zsh
deactivate
```

---

如需在 Dockerfile 中集成 venv，请在 Dockerfile 相关 RUN 步骤中添加：
```Dockerfile
RUN python3 -m venv /app/venv \
    && . /app/venv/bin/activate \
    && pip install --upgrade pip \
    && pip install -r requirements.txt
```

---

如需自动化脚本或子进程调用，建议用 venv_python 变量指向虚拟环境解释器：
```python
venv_python = os.path.join(os.path.dirname(__file__), '../venv/bin/python')
```

---

如遇依赖冲突或环境问题，优先删除 venv 目录后重新创建。
