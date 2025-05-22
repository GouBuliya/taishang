from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit, QLineEdit, QCheckBox, QSizePolicy, QFrame
from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QIcon
from position_info_widget import PositionInfoWidget
import os

class QuantAssistantMainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("gemini金融智能体")
        base_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(base_dir, "icon.png")
        self.setWindowIcon(QIcon(icon_path))
        self.resize(1592, 928)
        self.temp_screenshot_path = None
        self.last_script_stdout = None
        self.empty_pos_checkbox = QCheckBox("空仓（无持仓）")
        self.position_info_widget = PositionInfoWidget()
        self.total_usdt_input = self.position_info_widget.total_usdt_input
        self.pos_percent_input = self.position_info_widget.pos_percent_input
        self.pos_dir_checkbox = self.position_info_widget.pos_dir_checkbox
        self.pos_dir_checkbox2 = self.position_info_widget.pos_dir_checkbox2
        self.open_price_input = self.position_info_widget.open_price_input
        self.stop_loss_input = self.position_info_widget.stop_loss_input
        self.run_button = QPushButton("1. 运行指标及宏观因子脚本")
        self.upload_button = QPushButton("2. 从剪切板获取截图")
        self.gemini_advice_button = QPushButton("3. 让Gemini给出操作建议")
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.settings = QSettings("GeminiQuant", "GeminiQuantApp")
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("输入Gemini API Key（自动保存）")
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        saved_key = self.settings.value("gemini_api_key", "")
        self.api_key_input.setText(saved_key)
        left_col = QVBoxLayout()
        left_col.setSpacing(18)
        left_col.setAlignment(Qt.AlignmentFlag.AlignTop)
        main_title = QLabel("Gemini金融智能体")
        main_title.setObjectName("MainTitle")
        left_col.addWidget(main_title, alignment=Qt.AlignmentFlag.AlignHCenter)
        input_card = QFrame()
        input_card.setObjectName("Card")
        input_card_layout = QVBoxLayout(input_card)
        input_card_layout.addWidget(self.empty_pos_checkbox)
        input_card_layout.addWidget(self.position_info_widget)
        left_col.addWidget(input_card)
        # ---按钮布局---
        btn_card = QFrame()
        btn_card.setObjectName("Card")
        btn_card_layout = QVBoxLayout(btn_card)
        btn_row1_layout = QHBoxLayout()
        btn_row1_layout.addWidget(self.run_button)
        btn_card_layout.addLayout(btn_row1_layout)
        btn_row2_layout = QHBoxLayout()
        btn_row2_layout.addWidget(self.upload_button)
        btn_row2_layout.addWidget(self.gemini_advice_button)
        btn_card_layout.addLayout(btn_row2_layout)
        left_col.addWidget(btn_card)
        log_card = QFrame()
        log_card.setObjectName("Card")
        log_card_layout = QVBoxLayout(log_card)
        log_title = QLabel("日志与脚本输出：")
        log_title.setObjectName("SectionTitle")
        log_card_layout.addWidget(log_title)
        self.log_output.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.log_output.setMinimumHeight(150)
        log_card_layout.addWidget(self.log_output)
        left_col.addWidget(log_card)
        left_col.addWidget(QLabel("Gemini API Key:"))
        left_col.addWidget(self.api_key_input)
        left_col.addStretch(1)
        right_col = QVBoxLayout()
        right_col.setSpacing(18)
        right_col.setAlignment(Qt.AlignmentFlag.AlignTop)
        img_card = QFrame()
        img_card.setObjectName("Card")
        img_card_layout = QVBoxLayout(img_card)
        img_title = QLabel("Gemini对话区：")
        img_title.setObjectName("SectionTitle")
        img_card_layout.addWidget(img_title)
        self.gemini_reply_box = QTextEdit()
        self.gemini_reply_box.setReadOnly(True)
        self.gemini_reply_box.setMinimumHeight(220)
        self.gemini_reply_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.gemini_reply_box.setPlaceholderText("此处将显示Gemini的AI回复/建议……")
        img_card_layout.addWidget(self.gemini_reply_box)
        right_col.addWidget(img_card, 1)
        right_col.addStretch(0)
        main_layout = QHBoxLayout()
        main_layout.setSpacing(24)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.addLayout(left_col, 2)
        main_layout.addLayout(right_col, 3)
        self.setLayout(main_layout)
        self.setStyleSheet('''
            QWidget {
                font-family: 'Segoe UI', 'Microsoft YaHei', Arial, sans-serif;
                font-size: 15px;
                background: #ECF0F1; 
                color: #2C3E50; 
            }
            QFrame#Card {
                background: #FFFFFF; 
                border-radius: 10px; 
                border: 1px solid #D5D8DC; 
                padding: 16px 22px;
                margin-bottom: 16px;
            }
            QLabel#MainTitle {
                color: #2C3E50; 
                font-size: 26px;
                font-weight: 600;
                letter-spacing: 1px;
                margin-bottom: 16px;
                background: transparent; 
            }
            QLabel#SectionTitle {
                color: #E74C3C; 
                font-size: 17px;
                font-weight: 600;
                margin-bottom: 6px;
                background: transparent; 
            }
            QPushButton {
                background-color: #E74C3C; /* Explicitly background-color */
                color: #FFFFFF; 
                border: 1px solid #C0392B; 
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: 600;
                font-size: 15px;
                margin: 6px 4px; 
            }
            QPushButton:hover {
                background-color: #C0392B; 
                border-color: #A93226; 
            }
            QPushButton:pressed {
                background-color: #A93226; 
            }
            QTextEdit, QLineEdit {
                border: 1px solid #95A5A6; 
                border-radius: 6px;
                background: #FFFFFF; 
                color: #2C3E50; 
                font-size: 15px;
                padding: 7px 10px;
            }
            QTextEdit:focus, QLineEdit:focus {
                border-color: #E74C3C; 
                box-shadow: 0 0 0 0.2rem rgba(231, 76, 60, 0.25); 
            }
            QTextEdit[readOnly="true"] {
                background: #FDFEFE; 
                color: #34495E; 
                border: 1px solid #BDC3C7; 
            }
            QCheckBox {
                font-size: 15px;
                color: #2C3E50; 
                spacing: 5px;
                background: transparent; 
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            QLabel { 
                font-size: 15px;
                color: #2C3E50; 
                padding-top: 2px;
                padding-bottom: 2px;
                background: transparent; 
            }
        ''')
        self.log_output.setStyleSheet( 
            "background: #34495E; " 
            "border: 1px solid #2C3E50; " 
            "border-radius: 6px; "
            "font-size: 14px; "
            "padding: 8px 12px; "
            "color: #ECF0F1; " 
            "font-family: 'Consolas', 'Courier New', monospace;"
        )
        self.gemini_reply_box.setStyleSheet(
            "background: #FFFFFF; " 
            "border: 1px solid #95A5A6; "
            "color: #2C3E50; "
            "border-radius: 6px; "
            "font-size: 15px; "
            "padding: 7px 10px;"
        )
