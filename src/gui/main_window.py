# gui/main_window.py - 主界面窗口
"""主界面窗口 - 提供所有配置功能"""

from PyQt6.QtCore import Qt, QPoint, QRect
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QStackedWidget,
    QFrame,
    QGroupBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QSlider,
    QComboBox,
    QListWidget,
    QListWidgetItem,
    QTableWidget,
    QHeaderView,
    QTimeEdit,
    QMessageBox,
    QInputDialog,
    QSizePolicy,
    QScrollArea,
)
from PyQt6.QtCore import QTime
from PyQt6.QtGui import QCloseEvent, QMouseEvent, QPixmap

from .toggle_switch import ToggleSwitch

from ..utils import get_market_short_name, get_security_type
from ..data_fetcher import StockNameManager
from ..constants import DEFAULT_GOLD_TARGETS


class MainWindow(QMainWindow):
    """主配置窗口"""
    
    def __init__(self, quote_manager, gold_manager, alert_engine, settings_manager, parent=None):
        super().__init__(parent)
        self.quote_manager = quote_manager
        self.gold_manager = gold_manager
        self.alert_engine = alert_engine
        self.settings_manager = settings_manager
        self.on_settings_applied = None  # 设置应用后的回调
        self.on_gold_settings_applied = None  # 黄金设置应用后的回调（预留接口）
        self._gold_symbol_periods = {}
        self._current_gold_target_key = None
        self.gold_target_switches = {}
        self._syncing_gold_switches = False
        
        self.setWindowTitle("")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window
        )
        self.setMinimumSize(520, 300)
        self.resize(700, 500)
        self._drag_pos = None  # 用于窗口拖动
        self._resize_edge = ""  # 用于窗口拉伸
        self._resize_origin = None
        self._resize_geometry = None
        self.RESIZE_MARGIN = 5
        
        # 创建中心部件
        central_widget = QWidget()
        # 窗口边框 + 圆角
        central_widget.setStyleSheet(
            "QWidget#_central { border: 1px solid #d0d0d0; border-radius: 10px; background-color: #f3f3f3; }"
        )
        central_widget.setObjectName("_central")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)
        
        # 自定义标题栏
        self._title_bar = QWidget()
        self._title_bar.setFixedHeight(18)
        self._title_bar.setStyleSheet(
            "QWidget { background: transparent; }"
        )
        title_bar_layout = QHBoxLayout(self._title_bar)
        title_bar_layout.setContentsMargins(10, 0, 2, 0)
        title_bar_layout.setSpacing(0)
        
        self._title_label = QLabel("")
        self._title_label.setStyleSheet("font-size: 11px; color: #616161; background: transparent;")
        title_bar_layout.addWidget(self._title_label)
        title_bar_layout.addStretch()
        
        btn_style = (
            "QPushButton { border: none; background: transparent;"
            " font-size: 11px; min-width: 30px; max-width: 30px;"
            " min-height: 18px; max-height: 18px;"
            " border-radius: 3px; color: #616161; padding: 0; }"
            "QPushButton:hover { background-color: rgba(0,0,0,0.06); color: #1a1a1a; }"
        )
        close_btn_style = (
            "QPushButton { border: none; background: transparent;"
            " font-size: 11px; min-width: 30px; max-width: 30px;"
            " min-height: 18px; max-height: 18px;"
            " border-radius: 3px; color: #616161; padding: 0; }"
            "QPushButton:hover { background-color: #c42b1c; color: white; }"
        )
        
        min_btn = QPushButton("\u2014")  # —
        min_btn.setStyleSheet(btn_style)
        min_btn.clicked.connect(self.showMinimized)
        title_bar_layout.addWidget(min_btn)
        
        self._max_btn = QPushButton("\u25a1")  # □
        self._max_btn.setStyleSheet(btn_style)
        self._max_btn.clicked.connect(self._toggle_maximize)
        title_bar_layout.addWidget(self._max_btn)
        
        close_btn_tb = QPushButton("\u2715")  # ✕
        close_btn_tb.setStyleSheet(close_btn_style)
        close_btn_tb.clicked.connect(self.close)
        title_bar_layout.addWidget(close_btn_tb)
        
        layout.addWidget(self._title_bar)
        
        # 主体区域: 侧边栏 + 内容
        body = QWidget()
        body.setStyleSheet("background: transparent;")
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        
        # === 左侧边栏 ===
        sidebar = QWidget()
        sidebar.setFixedWidth(170)
        sidebar.setObjectName("_sidebar")
        sidebar.setStyleSheet(
            "QWidget#_sidebar {"
            "  background-color: #f0f0f0;"
            "  border-right: 1px solid #e0e0e0;"
            "  border-bottom-left-radius: 9px;"
            "}"
        )
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(12, 14, 12, 12)
        sidebar_layout.setSpacing(2)
        
        # App icon
        from ..utils import get_resource_path
        icon_path = get_resource_path("icon.ico")
        icon_label = QLabel()
        icon_label.setFixedSize(48, 48)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("background: transparent; border: none;")
        pix = QPixmap(str(icon_path))
        if not pix.isNull():
            icon_label.setPixmap(pix.scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            icon_label.setText("A")
            icon_label.setStyleSheet(
                "background: #005fb8; color: white; border-radius: 12px;"
                " font-size: 22px; font-weight: bold; border: none;"
            )
        sidebar_layout.addWidget(icon_label, alignment=Qt.AlignmentFlag.AlignHCenter)
        
        app_name = QLabel("AShareTools")
        app_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        app_name.setStyleSheet("font-size: 15px; font-weight: bold; color: #1a1a1a; background: transparent; border: none;")
        sidebar_layout.addWidget(app_name)
        
        author_label = QLabel("by yxg")
        author_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        author_label.setStyleSheet("font-size: 12px; color: #888; background: transparent; border: none;")
        sidebar_layout.addWidget(author_label)
        
        repo_label = QLabel('<a href="https://github.com/yxingg/AshareTools" style="color:#005fb8; text-decoration:none;">GitHub Repo</a>')
        repo_label.setOpenExternalLinks(True)
        repo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        repo_label.setStyleSheet("font-size: 12px; background: transparent; border: none;")
        sidebar_layout.addWidget(repo_label)
        
        sidebar_layout.addSpacing(8)
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Plain)
        sep.setStyleSheet("color: #ddd; background: #ddd; border: none; max-height: 1px;")
        sidebar_layout.addWidget(sep)
        sidebar_layout.addSpacing(4)
        
        # 导航按钮
        nav_btn_style_normal = (
            "QPushButton { background: transparent; border: none; text-align: left;"
            " padding: 8px 12px; border-radius: 6px; font-size: 15px; color: #1a1a1a; }"
            "QPushButton:hover { background-color: rgba(0,0,0,0.04); }"
        )
        nav_btn_style_active = (
            "QPushButton { background-color: rgba(0,95,184,0.08); border: none; text-align: left;"
            " padding: 8px 12px; border-radius: 6px; font-size: 15px; color: #005fb8; font-weight: bold; }"
            "QPushButton:hover { background-color: rgba(0,95,184,0.12); }"
        )
        self._nav_btn_style_normal = nav_btn_style_normal
        self._nav_btn_style_active = nav_btn_style_active
        
        self._nav_btns = []
        for i, name in enumerate(["\u884c\u60c5\u7a97\u53e3", "\u9ec4\u91d1\u884c\u60c5", "\u884c\u60c5\u9884\u8b66"]):
            btn = QPushButton(name)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(nav_btn_style_active if i == 0 else nav_btn_style_normal)
            btn.clicked.connect(lambda checked, idx=i: self._on_nav_changed(idx))
            sidebar_layout.addWidget(btn)
            self._nav_btns.append(btn)
        
        sidebar_layout.addStretch()
        
        body_layout.addWidget(sidebar)
        
        # === 右侧内容区 ===
        right_area = QWidget()
        right_area.setStyleSheet("background: transparent;")
        right_layout = QVBoxLayout(right_area)
        right_layout.setContentsMargins(8, 6, 8, 8)
        right_layout.setSpacing(6)
        
        # 页面标题
        self._page_title = QLabel("行情窗口")
        self._page_title.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #1a1a1a;"
            " background: transparent; border: none; padding: 2px 0;"
        )
        right_layout.addWidget(self._page_title)
        
        self._stacked = QStackedWidget()
        right_layout.addWidget(self._stacked)
        
        # 创建页面
        self._create_quote_tab()
        self._create_gold_tab()
        self._create_alert_tab()
        
        # 底部按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        apply_btn = QPushButton("应用")
        apply_btn.setFixedWidth(70)
        apply_btn.clicked.connect(self._apply_settings)
        btn_layout.addWidget(apply_btn)
        
        close_btn = QPushButton("关闭")
        close_btn.setFixedWidth(70)
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)
        
        right_layout.addLayout(btn_layout)
        body_layout.addWidget(right_area)
        layout.addWidget(body)
        
        # 加载当前设置
        self._load_current_settings()

    def _create_quote_tab(self):
        """创建行情窗口选项卡"""
        # 外层 scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        
        tab = QWidget()
        tab.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)
        
        # 总开关 (ToggleSwitch)
        self.enable_quote_check = ToggleSwitch("启用行情窗口")
        self.enable_quote_check.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(self.enable_quote_check)
        
        # 股票列表
        stock_group = QGroupBox("监控股票")
        stock_layout = QVBoxLayout(stock_group)
        stock_layout.setContentsMargins(6, 10, 6, 6)
        stock_layout.setSpacing(4)
        
        self.stock_list = QListWidget()
        self.stock_list.setMinimumHeight(150)
        self.stock_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.stock_list.setStyleSheet(
            "QListWidget { background-color: #ffffff; color: #1a1a1a; }"
            "QListWidget::item { color: #1a1a1a; }"
            "QListWidget::item:selected { background-color: rgba(0,95,184,0.08); color: #1a1a1a; }"
        )
        stock_layout.addWidget(self.stock_list)
        
        stock_btn_layout = QHBoxLayout()
        stock_btn_layout.setSpacing(6)
        add_stock_btn = QPushButton("添加")
        add_stock_btn.setFixedWidth(60)
        add_stock_btn.clicked.connect(self._add_stock)
        stock_btn_layout.addWidget(add_stock_btn)
        
        remove_stock_btn = QPushButton("删除")
        remove_stock_btn.setFixedWidth(60)
        remove_stock_btn.clicked.connect(self._remove_stock)
        stock_btn_layout.addWidget(remove_stock_btn)
        
        stock_btn_layout.addStretch()
        stock_layout.addLayout(stock_btn_layout)
        
        layout.addWidget(stock_group)
        
        # 显示设置
        display_group = QGroupBox("显示设置")
        display_group.setMinimumHeight(220)
        display_layout = QFormLayout(display_group)
        display_layout.setContentsMargins(6, 10, 6, 6)
        display_layout.setSpacing(4)
        
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 48)
        self.font_size_spin.setFixedWidth(80)
        display_layout.addRow("字体大小:", self.font_size_spin)
        
        self.bg_alpha_slider = QSlider(Qt.Orientation.Horizontal)
        self.bg_alpha_slider.setRange(0, 255)
        display_layout.addRow("背景透明度:", self.bg_alpha_slider)
        
        self.text_alpha_slider = QSlider(Qt.Orientation.Horizontal)
        self.text_alpha_slider.setRange(0, 255)
        display_layout.addRow("文字透明度:", self.text_alpha_slider)
        
        self.refresh_interval_spin = QSpinBox()
        self.refresh_interval_spin.setRange(1, 3600)
        self.refresh_interval_spin.setSuffix(" 秒")
        self.refresh_interval_spin.setFixedWidth(80)
        display_layout.addRow("刷新间隔:", self.refresh_interval_spin)
        
        self.show_name_check = ToggleSwitch("显示名称")
        self.show_code_check = ToggleSwitch("显示代码")
        self.show_header_check = ToggleSwitch("显示标题栏")
        self.always_top_check = ToggleSwitch("始终置顶")
        
        toggle_row1 = QHBoxLayout()
        toggle_row1.setSpacing(16)
        toggle_row1.addWidget(self.show_name_check)
        toggle_row1.addWidget(self.show_code_check)
        display_layout.addRow(toggle_row1)
        
        toggle_row2 = QHBoxLayout()
        toggle_row2.setSpacing(16)
        toggle_row2.addWidget(self.show_header_check)
        toggle_row2.addWidget(self.always_top_check)
        display_layout.addRow(toggle_row2)
        
        layout.addWidget(display_group)
        
        # 定时显示设置
        schedule_group = QGroupBox("定时显示")
        schedule_layout = QVBoxLayout(schedule_group)
        schedule_layout.setContentsMargins(6, 10, 6, 6)
        schedule_layout.setSpacing(4)
        
        self.enable_schedule_check = ToggleSwitch("启用定时显示")
        schedule_layout.addWidget(self.enable_schedule_check)
        
        self.schedule_table = QTableWidget(0, 3)
        self.schedule_table.setMinimumHeight(120)
        self.schedule_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.schedule_table.setHorizontalHeaderLabels(["开始时间", "结束时间", "操作"])
        self.schedule_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.schedule_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.schedule_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.schedule_table.setColumnWidth(2, 50)
        self.schedule_table.verticalHeader().setVisible(False)
        schedule_layout.addWidget(self.schedule_table, 1)  # stretch factor 1
        
        add_period_btn = QPushButton("添加时间段")
        add_period_btn.clicked.connect(self._add_schedule_period)
        schedule_layout.addWidget(add_period_btn)
        
        layout.addWidget(schedule_group)
        layout.addStretch()
        
        scroll.setWidget(tab)
        self._stacked.addWidget(scroll)

    def _create_gold_tab(self):
        """创建黄金行情选项卡"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        tab = QWidget()
        tab.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # 固定黄金标的
        gold_targets_group = QGroupBox("监控黄金标的")
        gold_targets_layout = QVBoxLayout(gold_targets_group)
        gold_targets_layout.setContentsMargins(6, 10, 6, 6)
        gold_targets_layout.setSpacing(4)

        self.gold_targets_rows_layout = QVBoxLayout()
        self.gold_targets_rows_layout.setSpacing(4)
        gold_targets_layout.addLayout(self.gold_targets_rows_layout)

        layout.addWidget(gold_targets_group)

        # 显示设置（与行情窗口一致）
        gold_display_group = QGroupBox("显示设置")
        gold_display_group.setMinimumHeight(190)
        gold_display_layout = QFormLayout(gold_display_group)
        gold_display_layout.setContentsMargins(6, 10, 6, 6)
        gold_display_layout.setSpacing(4)

        self.gold_font_size_spin = QSpinBox()
        self.gold_font_size_spin.setRange(8, 48)
        self.gold_font_size_spin.setFixedWidth(80)
        gold_display_layout.addRow("字体大小:", self.gold_font_size_spin)

        self.gold_bg_alpha_slider = QSlider(Qt.Orientation.Horizontal)
        self.gold_bg_alpha_slider.setRange(0, 255)
        gold_display_layout.addRow("背景透明度:", self.gold_bg_alpha_slider)

        self.gold_text_alpha_slider = QSlider(Qt.Orientation.Horizontal)
        self.gold_text_alpha_slider.setRange(0, 255)
        gold_display_layout.addRow("文字透明度:", self.gold_text_alpha_slider)

        self.gold_refresh_interval_spin = QSpinBox()
        self.gold_refresh_interval_spin.setRange(1, 3600)
        self.gold_refresh_interval_spin.setSuffix(" 秒")
        self.gold_refresh_interval_spin.setFixedWidth(80)
        gold_display_layout.addRow("刷新间隔:", self.gold_refresh_interval_spin)

        self.gold_show_code_check = ToggleSwitch("显示代码")
        self.gold_always_top_check = ToggleSwitch("始终置顶")

        gold_toggle_row1 = QHBoxLayout()
        gold_toggle_row1.setSpacing(16)
        gold_toggle_row1.addWidget(self.gold_show_code_check)
        gold_toggle_row1.addWidget(self.gold_always_top_check)
        gold_display_layout.addRow(gold_toggle_row1)

        layout.addWidget(gold_display_group)

        # 定时显示（按标的单独配置）
        gold_schedule_group = QGroupBox("定时显示")
        gold_schedule_layout = QVBoxLayout(gold_schedule_group)
        gold_schedule_layout.setContentsMargins(6, 10, 6, 6)
        gold_schedule_layout.setSpacing(4)

        self.enable_gold_schedule_check = ToggleSwitch("启用定时显示")
        gold_schedule_layout.addWidget(self.enable_gold_schedule_check)

        target_layout = QHBoxLayout()
        target_layout.addWidget(QLabel("配置标的:"))
        self.gold_schedule_target_combo = QComboBox()
        self.gold_schedule_target_combo.setStyleSheet(
            "QComboBox {"
            " background-color: #ffffff;"
            " color: #1a1a1a;"
            " border: 1px solid #c8c8c8;"
            " border-radius: 4px;"
            " padding: 2px 8px;"
            "}"
            "QComboBox QAbstractItemView {"
            " background-color: #ffffff;"
            " color: #1a1a1a;"
            " selection-background-color: rgba(0,95,184,0.12);"
            " selection-color: #1a1a1a;"
            "}"
        )
        self.gold_schedule_target_combo.currentIndexChanged.connect(self._on_gold_target_changed)
        target_layout.addWidget(self.gold_schedule_target_combo)
        target_layout.addStretch()
        gold_schedule_layout.addLayout(target_layout)

        self.gold_schedule_table = QTableWidget(0, 3)
        self.gold_schedule_table.setMinimumHeight(120)
        self.gold_schedule_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.gold_schedule_table.setHorizontalHeaderLabels(["开始时间", "结束时间", "操作"])
        self.gold_schedule_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.gold_schedule_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.gold_schedule_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.gold_schedule_table.setColumnWidth(2, 50)
        self.gold_schedule_table.verticalHeader().setVisible(False)
        gold_schedule_layout.addWidget(self.gold_schedule_table, 1)

        add_gold_period_btn = QPushButton("添加时间段")
        add_gold_period_btn.clicked.connect(self._add_gold_schedule_period)
        gold_schedule_layout.addWidget(add_gold_period_btn)

        layout.addWidget(gold_schedule_group)
        layout.addStretch()

        scroll.setWidget(tab)
        self._stacked.addWidget(scroll)

    def _create_alert_tab(self):
        """创建行情预警选项卡"""
        # 外层 scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        
        tab = QWidget()
        tab.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)
        
        # 钉钉配置
        dingtalk_group = QGroupBox("钉钉通知")
        dingtalk_layout = QFormLayout(dingtalk_group)
        dingtalk_layout.setContentsMargins(6, 10, 6, 6)
        dingtalk_layout.setSpacing(4)
        
        self.webhook_edit = QLineEdit()
        self.webhook_edit.setPlaceholderText("https://oapi.dingtalk.com/robot/send?access_token=xxx")
        dingtalk_layout.addRow("Webhook:", self.webhook_edit)
        
        self.secret_edit = QLineEdit()
        self.secret_edit.setPlaceholderText("SECxxx")
        dingtalk_layout.addRow("Secret:", self.secret_edit)
        
        layout.addWidget(dingtalk_group)
        
        # 总开关
        enable_layout = QHBoxLayout()
        enable_layout.setSpacing(8)
        self.enable_alert_check = ToggleSwitch("启用行情预警")
        self.enable_alert_check.setStyleSheet("font-weight: bold; font-size: 13px;")
        enable_layout.addWidget(self.enable_alert_check)
        enable_layout.addStretch()
        layout.addLayout(enable_layout)
        
        # 预警设置
        alert_group = QGroupBox("股票行情预警")
        alert_layout = QVBoxLayout(alert_group)
        alert_layout.setContentsMargins(6, 10, 6, 6)
        alert_layout.setSpacing(4)
        
        top_layout = QHBoxLayout()
        top_layout.setSpacing(8)
        
        top_layout.addWidget(QLabel("扫描间隔:"))
        self.scan_interval_spin = QSpinBox()
        self.scan_interval_spin.setRange(1, 300)
        self.scan_interval_spin.setSuffix(" 秒")
        self.scan_interval_spin.setFixedWidth(80)
        top_layout.addWidget(self.scan_interval_spin)
        
        top_layout.addStretch()
        alert_layout.addLayout(top_layout)
        
        # 预警任务表格
        self.alert_table = QTableWidget(0, 5)
        self.alert_table.setMinimumHeight(120)
        self.alert_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.alert_table.setHorizontalHeaderLabels(["股票代码", "策略", "K线周期（分钟）", "预警开关", "操作"])
        self.alert_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.alert_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.alert_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.alert_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.alert_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.alert_table.setColumnWidth(2, 110)
        self.alert_table.setColumnWidth(3, 100)
        self.alert_table.setColumnWidth(4, 60)
        self.alert_table.verticalHeader().setVisible(False)
        alert_layout.addWidget(self.alert_table, 1)  # stretch factor 1
        
        # 底部按钮栏
        bottom_btn_layout = QHBoxLayout()
        bottom_btn_layout.setSpacing(8)
        
        add_alert_btn = QPushButton("添加预警任务")
        add_alert_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        add_alert_btn.setFixedHeight(30)
        add_alert_btn.clicked.connect(self._add_alert_task)
        bottom_btn_layout.addWidget(add_alert_btn)
        
        reload_btn = QPushButton("重载策略")
        reload_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        reload_btn.setFixedHeight(30)
        reload_btn.clicked.connect(self._reload_strategies)
        bottom_btn_layout.addWidget(reload_btn)

        refresh_btn = QPushButton("刷新状态")
        refresh_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        refresh_btn.setFixedHeight(30)
        refresh_btn.clicked.connect(self._refresh_alert_status)
        bottom_btn_layout.addWidget(refresh_btn)
        
        alert_layout.addLayout(bottom_btn_layout)
        
        layout.addWidget(alert_group, 1)

        # 黄金预警设置
        gold_alert_group = QGroupBox("黄金行情预警")
        gold_alert_layout = QVBoxLayout(gold_alert_group)
        gold_alert_layout.setContentsMargins(6, 10, 6, 6)
        gold_alert_layout.setSpacing(4)

        gold_top_layout = QHBoxLayout()
        gold_top_layout.setSpacing(8)
        gold_top_layout.addWidget(QLabel("扫描间隔:"))
        self.gold_alert_scan_interval_spin = QSpinBox()
        self.gold_alert_scan_interval_spin.setRange(1, 3600)
        self.gold_alert_scan_interval_spin.setSuffix(" 秒")
        self.gold_alert_scan_interval_spin.setFixedWidth(80)
        gold_top_layout.addWidget(self.gold_alert_scan_interval_spin)
        gold_top_layout.addStretch()
        gold_alert_layout.addLayout(gold_top_layout)

        self.gold_alert_table = QTableWidget(0, 5)
        self.gold_alert_table.setMinimumHeight(120)
        self.gold_alert_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.gold_alert_table.setHorizontalHeaderLabels(["黄金标的", "预警价格", "预警频率（分钟）", "预警开关", "操作"])
        self.gold_alert_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.gold_alert_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.gold_alert_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.gold_alert_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.gold_alert_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.gold_alert_table.setColumnWidth(2, 120)
        self.gold_alert_table.setColumnWidth(3, 100)
        self.gold_alert_table.setColumnWidth(4, 60)
        self.gold_alert_table.verticalHeader().setVisible(False)
        gold_alert_layout.addWidget(self.gold_alert_table, 1)

        add_gold_alert_btn = QPushButton("添加预警任务")
        add_gold_alert_btn.setFixedHeight(30)
        add_gold_alert_btn.clicked.connect(self._add_gold_alert_task)
        gold_alert_layout.addWidget(add_gold_alert_btn)

        layout.addWidget(gold_alert_group, 1)
        layout.addStretch()
        
        scroll.setWidget(tab)
        self._stacked.addWidget(scroll)

    def _on_nav_changed(self, index: int):
        """侧边栏导航切换"""
        self._stacked.setCurrentIndex(index)
        names = ["行情窗口", "黄金行情", "行情预警"]
        if 0 <= index < len(names):
            self._page_title.setText(names[index])
        for i, btn in enumerate(self._nav_btns):
            btn.setStyleSheet(self._nav_btn_style_active if i == index else self._nav_btn_style_normal)

    def _load_current_settings(self):
        """加载当前设置"""
        # 行情窗口设置
        self.enable_quote_check.setChecked(self.quote_manager.is_visible())
        
        self.stock_list.clear()
        
        # 批量检查缓存（只对缺失的进行网络请求）
        all_codes = list(self.quote_manager.codes)
        stock_mgr = StockNameManager.get_instance()
        if stock_mgr and all_codes:
            # 只获取缓存中没有的（使用新方法检查，兼容带前缀和不带前缀的格式）
            stock_mgr.ensure_symbols(all_codes)  # ensure_symbols内部会正确检查缺失
        
        for code in all_codes:
            self._add_stock_item_fast(code)  # 使用快速版本，不再单独联网
        
        self.font_size_spin.setValue(self.quote_manager.font_size)
        self.bg_alpha_slider.setValue(self.quote_manager.background_alpha)
        self.text_alpha_slider.setValue(self.quote_manager.text_alpha)
        self.refresh_interval_spin.setValue(self.quote_manager.update_interval)
        
        self.show_name_check.setChecked(self.quote_manager.show_name)
        self.show_code_check.setChecked(self.quote_manager.show_code)
        self.show_header_check.setChecked(self.quote_manager.show_column_header)
        self.always_top_check.setChecked(self.quote_manager.always_on_top)
        
        # 定时显示
        self.enable_schedule_check.setChecked(self.settings_manager.get_time_schedule_enabled())
        self._load_schedule_periods()

        # 黄金行情设置
        self._load_gold_settings()
        
        # 预警设置
        dingtalk = self.settings_manager.get_dingtalk_config()
        self.webhook_edit.setText(dingtalk.get('webhook', ''))
        self.secret_edit.setText(dingtalk.get('secret', ''))
        
        self.enable_alert_check.setChecked(self.settings_manager.get_alert_enabled())
        self.scan_interval_spin.setValue(self.settings_manager.get_alert_scan_interval())
        self.gold_alert_scan_interval_spin.setValue(self.settings_manager.get_gold_alert_scan_interval())
        
        self._load_alert_tasks()
        self._load_gold_alert_tasks()

    def _load_schedule_periods(self):
        """加载时间段"""
        self.schedule_table.setRowCount(0)
        periods = self.settings_manager.get_time_schedule_periods()
        for period in periods:
            self._add_schedule_period_row(period.get('start', '09:25'), period.get('end', '15:05'))

    def _add_schedule_period(self):
        """添加时间段"""
        self._add_schedule_period_row('09:25', '15:05')

    def _add_schedule_period_row(self, start: str, end: str):
        """添加时间段行"""
        row = self.schedule_table.rowCount()
        self.schedule_table.insertRow(row)
        
        start_edit = QTimeEdit()
        start_parts = start.split(':')
        start_edit.setTime(QTime(int(start_parts[0]), int(start_parts[1])))
        start_edit.setDisplayFormat("HH:mm")
        self.schedule_table.setCellWidget(row, 0, start_edit)
        
        end_edit = QTimeEdit()
        end_parts = end.split(':')
        end_edit.setTime(QTime(int(end_parts[0]), int(end_parts[1])))
        end_edit.setDisplayFormat("HH:mm")
        self.schedule_table.setCellWidget(row, 1, end_edit)
        
        del_btn = QPushButton("删除")
        del_btn.setFixedWidth(60)
        del_btn.clicked.connect(lambda: self._remove_schedule_row())
        self.schedule_table.setCellWidget(row, 2, del_btn)

    def _remove_schedule_row(self):
        """删除时间段行"""
        for i in range(self.schedule_table.rowCount()):
            btn = self.schedule_table.cellWidget(i, 2)
            if btn == self.sender():
                self.schedule_table.removeRow(i)
                break

    def _load_alert_tasks(self):
        """加载预警任务"""
        self.alert_table.setRowCount(0)
        tasks = self.settings_manager.get_alert_tasks()
        for task in tasks:
            self._add_alert_task_row(
                task.get('symbol', ''),
                task.get('strategy', ''),
                task.get('period', '5'),
                bool(task.get('enabled', True)),
            )

    def _add_alert_task(self):
        """添加预警任务"""
        self._add_alert_task_row('', '', '5', True)

    def _add_alert_task_row(self, symbol: str, strategy: str, period: str, enabled: bool):
        """添加预警任务行"""
        row = self.alert_table.rowCount()
        self.alert_table.insertRow(row)
        
        code_edit = QLineEdit()
        code_edit.setText(symbol)
        code_edit.setPlaceholderText("如: 600519")
        self.alert_table.setCellWidget(row, 0, code_edit)
        
        strategy_combo = QComboBox()
        strategy_combo.setStyleSheet(self.gold_schedule_target_combo.styleSheet())
        strategies = self.alert_engine.get_available_strategies()
        for sid, info in strategies.items():
            strategy_combo.addItem(f"{info.get('name', sid)} ({sid})", sid)
        
        for i in range(strategy_combo.count()):
            if strategy_combo.itemData(i) == strategy:
                strategy_combo.setCurrentIndex(i)
                break
        
        self.alert_table.setCellWidget(row, 1, strategy_combo)
        
        period_combo = QComboBox()
        period_combo.addItems(['1', '5', '15', '30', '60'])
        period_combo.setCurrentText(period)
        self.alert_table.setCellWidget(row, 2, period_combo)

        switch = ToggleSwitch("")
        switch.setChecked(enabled)
        switch_container = QWidget()
        switch_layout = QHBoxLayout(switch_container)
        switch_layout.setContentsMargins(0, 0, 0, 0)
        switch_layout.setSpacing(0)
        switch_layout.addStretch()
        switch_layout.addWidget(switch)
        switch_layout.addStretch()
        self.alert_table.setCellWidget(row, 3, switch_container)
        
        del_btn = QPushButton("删除")
        del_btn.clicked.connect(lambda: self._remove_alert_row())
        del_btn.setFixedWidth(60)
        self.alert_table.setCellWidget(row, 4, del_btn)

    def _remove_alert_row(self):
        """删除预警任务行"""
        for i in range(self.alert_table.rowCount()):
            btn = self.alert_table.cellWidget(i, 4)
            if btn == self.sender():
                self.alert_table.removeRow(i)
                break

    def _load_gold_alert_tasks(self):
        """加载黄金预警任务"""
        self.gold_alert_table.setRowCount(0)
        tasks = self.settings_manager.get_gold_alert_tasks()
        for task in tasks:
            self._add_gold_alert_task_row(
                task.get('target', 'london_spot'),
                str(task.get('price', '')),
                str(task.get('frequency', 0)),
                bool(task.get('enabled', True)),
            )

    def _add_gold_alert_task(self):
        """添加黄金预警任务"""
        self._add_gold_alert_task_row('london_spot', '', '0', True)

    def _add_gold_alert_task_row(self, target: str, price: str, frequency: str, enabled: bool):
        """添加黄金预警任务行"""
        row = self.gold_alert_table.rowCount()
        self.gold_alert_table.insertRow(row)

        target_combo = QComboBox()
        target_combo.setStyleSheet(self.gold_schedule_target_combo.styleSheet())
        for item in DEFAULT_GOLD_TARGETS:
            key = item.get('key', '')
            name = item.get('name', key)
            target_combo.addItem(name, key)
        for i in range(target_combo.count()):
            if target_combo.itemData(i) == target:
                target_combo.setCurrentIndex(i)
                break
        self.gold_alert_table.setCellWidget(row, 0, target_combo)

        price_edit = QLineEdit()
        price_edit.setPlaceholderText('例如: 1130.5')
        price_edit.setText(price)
        self.gold_alert_table.setCellWidget(row, 1, price_edit)

        freq_edit = QLineEdit()
        freq_edit.setPlaceholderText('0=仅一次')
        freq_edit.setText(frequency)
        self.gold_alert_table.setCellWidget(row, 2, freq_edit)

        switch = ToggleSwitch("")
        switch.setChecked(enabled)
        switch_container = QWidget()
        switch_layout = QHBoxLayout(switch_container)
        switch_layout.setContentsMargins(0, 0, 0, 0)
        switch_layout.setSpacing(0)
        switch_layout.addStretch()
        switch_layout.addWidget(switch)
        switch_layout.addStretch()
        self.gold_alert_table.setCellWidget(row, 3, switch_container)

        del_btn = QPushButton("删除")
        del_btn.clicked.connect(lambda: self._remove_gold_alert_row())
        del_btn.setFixedWidth(60)
        self.gold_alert_table.setCellWidget(row, 4, del_btn)

    def _remove_gold_alert_row(self):
        """删除黄金预警任务行"""
        for i in range(self.gold_alert_table.rowCount()):
            btn = self.gold_alert_table.cellWidget(i, 4)
            if btn == self.sender():
                self.gold_alert_table.removeRow(i)
                break

    def _add_stock(self):
        """添加股票"""
        from ..utils import normalize_stock_code
        code, ok = QInputDialog.getText(self, "添加股票", "请输入股票代码:")
        if ok and code:
            normalized = normalize_stock_code(code)
            if normalized:
                self._add_stock_item(normalized)
            else:
                QMessageBox.warning(self, "错误", "无效的股票代码")

    def _add_stock_item_fast(self, code: str):
        """添加股票列表项（快速版本，只从缓存读取，不联网）"""
        stock_mgr = StockNameManager.get_instance()
        name = ""
        market = ""
        sec_type = ""
        
        if stock_mgr:
            # 使用新的兼容方法获取信息
            info = stock_mgr.get_info(code)
            name = info.get('name', '')
            market = info.get('market', '')
            sec_type = info.get('type', '')
        
        # 如果缓存中没有名称，尝试从行情数据获取
        if not name or name == code:
            if code in self.quote_manager.quotes:
                quote = self.quote_manager.quotes[code]
                if quote:
                    name = quote.name
        
        # 如果仍没有市场和类型信息，使用工具函数计算
        if not market:
            market = get_market_short_name(code)
        if not sec_type:
            sec_type = get_security_type(code)
        
        # 显示格式: 代码 - 名称 [市场·类型]
        if name and name != code:
            display = f"{code} - {name} [{market}·{sec_type}]"
        else:
            display = f"{code} [{market}·{sec_type}]"
        
        item = QListWidgetItem(display)
        item.setData(Qt.ItemDataRole.UserRole, code)
        self.stock_list.addItem(item)

    def _add_stock_item(self, code: str):
        """添加股票列表项（用于新增股票，会联网查询）"""
        # 首先尝试从缓存获取股票信息
        stock_mgr = StockNameManager.get_instance()
        name = ""
        market = ""
        sec_type = ""
        
        if stock_mgr:
            # ensure_symbols内部会正确检查缓存（兼容带前缀和不带前缀的格式）
            stock_mgr.ensure_symbols([code])
            info = stock_mgr.get_info(code)
            name = info.get('name', '')
            market = info.get('market', '')
            sec_type = info.get('type', '')
        
        # 如果缓存中没有名称，尝试从行情数据获取
        if not name or name == code:
            if code in self.quote_manager.quotes:
                quote = self.quote_manager.quotes[code]
                if quote:
                    name = quote.name
        
        # 如果仍没有市场和类型信息，使用工具函数计算
        if not market:
            market = get_market_short_name(code)
        if not sec_type:
            sec_type = get_security_type(code)
        
        # 显示格式: 代码 - 名称 [市场·类型]
        if name and name != code:
            display = f"{code} - {name} [{market}·{sec_type}]"
        else:
            display = f"{code} [{market}·{sec_type}]"
        
        item = QListWidgetItem(display)
        item.setData(Qt.ItemDataRole.UserRole, code)  # 存储原始代码
        self.stock_list.addItem(item)

    def _remove_stock(self):
        """删除股票"""
        current = self.stock_list.currentItem()
        if current:
            self.stock_list.takeItem(self.stock_list.row(current))

    def _reload_strategies(self):
        """重载策略"""
        success = self.alert_engine.reload_strategies()
        if success:
            self._reload_strategies_ui_only()
            QMessageBox.information(self, "成功", "策略重载成功！")
        else:
            QMessageBox.warning(self, "失败", "策略重载失败，请检查文件格式。")

    def _reload_strategies_ui_only(self):
        """仅刷新界面上的策略列表（不触发引擎重载）"""
        strategies = self.alert_engine.get_available_strategies()
        for row in range(self.alert_table.rowCount()):
            combo = self.alert_table.cellWidget(row, 1)
            if combo:
                current = combo.currentData()
                combo.clear()
                for sid, info in strategies.items():
                    combo.addItem(f"{info.get('name', sid)} ({sid})", sid)
                for i in range(combo.count()):
                    if combo.itemData(i) == current:
                        combo.setCurrentIndex(i)
                        break

    def _refresh_alert_status(self):
        """刷新预警状态"""
        is_running = self.alert_engine.is_running()
        self.enable_alert_check.setChecked(is_running)
        
        # 同步设置管理器状态
        self.settings_manager.set_alert_enabled(is_running)
        
        # 重新加载任务列表
        self._load_alert_tasks()
        if is_running:
            runtime_gold_tasks = self.alert_engine.get_gold_tasks_snapshot()
            self.settings_manager.set_gold_alert_tasks(runtime_gold_tasks)
        self._load_gold_alert_tasks()
        if is_running:
            self.quote_manager.set_alert_polling_config(
                self.settings_manager.get_alert_tasks(),
                self.settings_manager.get_alert_scan_interval(),
            )
        else:
            self.quote_manager.set_alert_polling_config([], self.settings_manager.get_alert_scan_interval())
        self.gold_manager.set_alert_polling_config(
            self.settings_manager.get_gold_alert_tasks(),
            self.settings_manager.get_gold_alert_scan_interval(),
        )
        
        status_text = "运行中" if is_running else "已停止"
        
        # 同步托盘图标菜单状态
        if self.on_settings_applied:
            self.on_settings_applied()
            
        QMessageBox.information(self, "状态刷新", "预警状态和任务列表已更新！")

    def _apply_settings(self):
        """应用设置"""
        # 行情窗口开关
        quote_enabled = self.enable_quote_check.isChecked()
        self.settings_manager.set_quote_enabled(quote_enabled)
        
        # 行情窗口设置
        new_codes = []
        for i in range(self.stock_list.count()):
            item = self.stock_list.item(i)
            code = item.data(Qt.ItemDataRole.UserRole)  # 从UserRole获取原始代码
            if code:
                new_codes.append(code)
            else:
                # 兼容旧数据，直接取文本
                new_codes.append(item.text().split(' ')[0])
        
        self.quote_manager.codes = new_codes
        self.quote_manager.font_size = self.font_size_spin.value()
        self.quote_manager.background_alpha = self.bg_alpha_slider.value()
        self.quote_manager.text_alpha = self.text_alpha_slider.value()
        self.quote_manager.update_interval = self.refresh_interval_spin.value()
        self.quote_manager.show_name = self.show_name_check.isChecked()
        self.quote_manager.show_code = self.show_code_check.isChecked()
        self.quote_manager.show_column_header = self.show_header_check.isChecked()
        self.quote_manager.always_on_top = self.always_top_check.isChecked()
        self.quote_manager._reconcile_polling_state()
        
        # 根据开关控制行情窗口
        if quote_enabled:
            self.quote_manager.show_windows()
            self.quote_manager._apply_settings_to_all()
            self.quote_manager._notify_settings_changed()
        else:
            self.quote_manager.hide_windows()
        
        # 定时显示设置
        self.settings_manager.set_time_schedule_enabled(self.enable_schedule_check.isChecked())
        
        periods = []
        for row in range(self.schedule_table.rowCount()):
            start_edit = self.schedule_table.cellWidget(row, 0)
            end_edit = self.schedule_table.cellWidget(row, 1)
            if start_edit and end_edit:
                periods.append({
                    'start': start_edit.time().toString("HH:mm"),
                    'end': end_edit.time().toString("HH:mm"),
                })
        self.settings_manager.set_time_schedule_periods(periods)

        # 黄金行情设置（预留接口，数据暂不接入行情）
        self._save_current_gold_schedule_periods()
        updated_targets = []
        for target in self._gold_targets:
            key = target.get('key', '')
            name = target.get('name', key)
            switch = self.gold_target_switches.get(key)
            enabled = switch.isChecked() if switch else target.get('enabled', True)
            updated_targets.append({'key': key, 'name': name, 'enabled': enabled})

        self.settings_manager.set_gold_targets(updated_targets)
        self.settings_manager.set_gold_enabled(any(t.get('enabled', False) for t in updated_targets))
        self.settings_manager.set_gold_config({
            'settings': {
                'font_size': self.gold_font_size_spin.value(),
                'background_alpha': self.gold_bg_alpha_slider.value(),
                'text_alpha': self.gold_text_alpha_slider.value(),
                'show_code': self.gold_show_code_check.isChecked(),
                'always_on_top': self.gold_always_top_check.isChecked(),
                'update_interval': self.gold_refresh_interval_spin.value(),
            }
        })
        self.settings_manager.set_gold_time_schedule_enabled(self.enable_gold_schedule_check.isChecked())
        self.settings_manager.set_gold_symbol_periods(self._gold_symbol_periods)

        self.gold_manager.set_targets(updated_targets)
        self.gold_manager.font_size = self.gold_font_size_spin.value()
        self.gold_manager.background_alpha = self.gold_bg_alpha_slider.value()
        self.gold_manager.text_alpha = self.gold_text_alpha_slider.value()
        self.gold_manager.show_name = False
        self.gold_manager.show_code = self.gold_show_code_check.isChecked()
        self.gold_manager.show_column_header = False
        self.gold_manager.always_on_top = self.gold_always_top_check.isChecked()
        self.gold_manager.update_interval = max(1, self.gold_refresh_interval_spin.value())
        self.gold_manager.fetch_timer.setInterval(self.gold_manager.update_interval * 1000)
        self.gold_manager._apply_settings_to_all()
        if any(t.get('enabled', False) for t in updated_targets):
            self.gold_manager.show_windows()
            if not self.gold_manager.fetch_timer.isActive():
                self.gold_manager.fetch_timer.start()
            self.gold_manager.refresh_quotes(force=True)
        else:
            self.gold_manager.hide_windows()
        self.gold_manager._notify_settings_changed()

        if self.on_gold_settings_applied:
            self.on_gold_settings_applied()
        
        # 预警设置
        self.settings_manager.set_dingtalk_config({
            'webhook': self.webhook_edit.text().strip(),
            'secret': self.secret_edit.text().strip(),
        })
        
        tasks = []
        for row in range(self.alert_table.rowCount()):
            code_edit = self.alert_table.cellWidget(row, 0)
            strategy_combo = self.alert_table.cellWidget(row, 1)
            period_combo = self.alert_table.cellWidget(row, 2)
            switch_widget = self.alert_table.cellWidget(row, 3)
            switch = switch_widget if isinstance(switch_widget, ToggleSwitch) else (
                switch_widget.findChild(ToggleSwitch) if switch_widget else None
            )
            
            if code_edit and strategy_combo and period_combo and switch:
                symbol = code_edit.text().strip()
                if symbol:
                    tasks.append({
                        'symbol': symbol,
                        'strategy': strategy_combo.currentData(),
                        'period': period_combo.currentText(),
                        'enabled': switch.isChecked(),
                    })

        gold_tasks = []
        for row in range(self.gold_alert_table.rowCount()):
            target_combo = self.gold_alert_table.cellWidget(row, 0)
            price_edit = self.gold_alert_table.cellWidget(row, 1)
            freq_edit = self.gold_alert_table.cellWidget(row, 2)
            switch_widget = self.gold_alert_table.cellWidget(row, 3)
            switch = switch_widget if isinstance(switch_widget, ToggleSwitch) else (
                switch_widget.findChild(ToggleSwitch) if switch_widget else None
            )

            if not target_combo or not price_edit or not freq_edit or not switch:
                continue

            target = target_combo.currentData()
            try:
                price = float(price_edit.text().strip())
            except Exception:
                continue
            if price <= 0:
                continue
            try:
                frequency = int(freq_edit.text().strip() or '0')
            except Exception:
                frequency = 0

            gold_tasks.append({
                'target': target,
                'price': price,
                'frequency': max(0, frequency),
                'enabled': switch.isChecked(),
            })
        
        self.settings_manager.set_alert_tasks(tasks)
        self.settings_manager.set_alert_scan_interval(self.scan_interval_spin.value())
        self.settings_manager.set_gold_alert_tasks(gold_tasks)
        self.settings_manager.set_gold_alert_scan_interval(self.gold_alert_scan_interval_spin.value())
        self.gold_manager.set_alert_polling_config(
            gold_tasks,
            self.gold_alert_scan_interval_spin.value(),
        )
        
        # 更新预警引擎
        was_running = self.alert_engine.is_running()
        should_run = self.enable_alert_check.isChecked()
        
        if should_run:
            dingtalk = self.settings_manager.get_dingtalk_config()
            self.quote_manager.set_alert_polling_config(
                tasks,
                self.scan_interval_spin.value(),
            )
            self.alert_engine.update_tasks(
                tasks,
                self.scan_interval_spin.value(),
                gold_tasks=gold_tasks,
                gold_scan_interval=self.gold_alert_scan_interval_spin.value(),
            )
            if self.alert_engine.notifier:
                self.alert_engine.notifier.update_config(
                    dingtalk.get('webhook', ''),
                    dingtalk.get('secret', '')
                )
            
            if not was_running:
                self.alert_engine.start()
            else:
                # 如果已经在运行，发送配置更新通知
                if self.alert_engine.notifier:
                    self.alert_engine.notifier.send(f"【系统通知】\n预警配置已更新\n当前任务数: {len(tasks)}")
        else:
            self.quote_manager.set_alert_polling_config([], self.scan_interval_spin.value())
            if was_running:
                self.alert_engine.stop()
        
        self.settings_manager.set_alert_enabled(should_run)
        
        # 同步托盘图标菜单状态
        if self.on_settings_applied:
            self.on_settings_applied()

    def _load_gold_settings(self):
        """加载黄金行情设置（界面）"""
        gold_config = self.settings_manager.get_gold_config()
        targets = self.gold_manager.targets or gold_config.get('targets') or [target.copy() for target in DEFAULT_GOLD_TARGETS]
        normalized_targets = []
        for target in targets:
            key = target.get('key', '')
            name = target.get('name', key)
            normalized_targets.append({
                'key': key,
                'name': name,
                'enabled': target.get('enabled', True),
            })
        self._gold_targets = normalized_targets
        self._rebuild_gold_target_rows()

        self.gold_schedule_target_combo.blockSignals(True)
        self.gold_schedule_target_combo.clear()

        for target in normalized_targets:
            key = target.get('key', '')
            name = target.get('name', key)
            self.gold_schedule_target_combo.addItem(name, key)

        self.gold_schedule_target_combo.blockSignals(False)

        self.gold_font_size_spin.setValue(self.gold_manager.font_size)
        self.gold_bg_alpha_slider.setValue(self.gold_manager.background_alpha)
        self.gold_text_alpha_slider.setValue(self.gold_manager.text_alpha)
        self.gold_refresh_interval_spin.setValue(self.gold_manager.update_interval)
        self.gold_show_code_check.setChecked(self.gold_manager.show_code)
        self.gold_always_top_check.setChecked(self.gold_manager.always_on_top)

        self.enable_gold_schedule_check.setChecked(self.settings_manager.get_gold_time_schedule_enabled())
        self._gold_symbol_periods = self.settings_manager.get_gold_symbol_periods()

        if self.gold_schedule_target_combo.count() > 0:
            self._current_gold_target_key = self.gold_schedule_target_combo.currentData()
            self._load_gold_schedule_table(self._current_gold_target_key)
        else:
            self._current_gold_target_key = None

        self.sync_gold_target_switches_with_visibility()

    def sync_gold_target_switches_with_visibility(self):
        """同步黄金标的开关与真实窗口可见状态"""
        visible_by_key = self.gold_manager.get_target_visibility_map()
        self._syncing_gold_switches = True
        for key, switch in self.gold_target_switches.items():
            switch.setChecked(bool(visible_by_key.get(key, False)))
        self._syncing_gold_switches = False

        # 同步本地缓存，避免“应用”时读到旧状态
        for target in self._gold_targets:
            key = target.get('key', '')
            if key:
                target['enabled'] = bool(visible_by_key.get(key, False))

    def _rebuild_gold_target_rows(self):
        """重建黄金标的行（名称 + 独立开关）"""
        while self.gold_targets_rows_layout.count():
            item = self.gold_targets_rows_layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget:
                widget.deleteLater()
            if child_layout:
                while child_layout.count():
                    child_item = child_layout.takeAt(0)
                    child_widget = child_item.widget()
                    if child_widget:
                        child_widget.deleteLater()

        self.gold_target_switches = {}
        for target in self._gold_targets:
            key = target.get('key', '')
            name = target.get('name', key)
            enabled = target.get('enabled', True)

            row_layout = QHBoxLayout()
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)
            row_layout.addWidget(QLabel(name))
            row_layout.addStretch()

            switch = ToggleSwitch("")
            switch.setChecked(enabled)
            switch.toggled.connect(lambda checked, k=key: self._on_gold_target_switch_toggled(k, checked))
            self.gold_target_switches[key] = switch
            row_layout.addWidget(switch)

            self.gold_targets_rows_layout.addLayout(row_layout)

        self.gold_targets_rows_layout.addStretch()

    def _on_gold_target_switch_toggled(self, key: str, checked: bool):
        """黄金标的开关实时双向绑定到底层窗口状态"""
        if self._syncing_gold_switches:
            return

        self.gold_manager.set_target_visible_state(key, bool(checked), persist=True)
        for target in self._gold_targets:
            if target.get('key', '') == key:
                target['enabled'] = bool(checked)
                break

    def _on_gold_target_changed(self, index: int):
        """切换黄金标的定时配置"""
        if index < 0:
            return
        self._save_current_gold_schedule_periods()
        self._current_gold_target_key = self.gold_schedule_target_combo.itemData(index)
        self._load_gold_schedule_table(self._current_gold_target_key)

    def _load_gold_schedule_table(self, target_key: str):
        """加载指定黄金标的的时间段到表格"""
        self.gold_schedule_table.setRowCount(0)
        periods = self._gold_symbol_periods.get(target_key, [
            {'start': '09:25', 'end': '11:35'},
            {'start': '12:55', 'end': '15:05'},
        ])
        for period in periods:
            self._add_gold_schedule_period_row(period.get('start', '09:25'), period.get('end', '15:05'))

    def _save_current_gold_schedule_periods(self):
        """保存当前黄金标的时间段"""
        target_key = getattr(self, '_current_gold_target_key', None)
        if not target_key:
            return

        periods = []
        for row in range(self.gold_schedule_table.rowCount()):
            start_edit = self.gold_schedule_table.cellWidget(row, 0)
            end_edit = self.gold_schedule_table.cellWidget(row, 1)
            if start_edit and end_edit:
                periods.append({
                    'start': start_edit.time().toString("HH:mm"),
                    'end': end_edit.time().toString("HH:mm"),
                })
        self._gold_symbol_periods[target_key] = periods

    def _add_gold_schedule_period(self):
        """添加黄金时间段"""
        self._add_gold_schedule_period_row('09:25', '15:05')

    def _add_gold_schedule_period_row(self, start: str, end: str):
        """添加黄金时间段行"""
        row = self.gold_schedule_table.rowCount()
        self.gold_schedule_table.insertRow(row)

        start_edit = QTimeEdit()
        start_parts = start.split(':')
        start_edit.setTime(QTime(int(start_parts[0]), int(start_parts[1])))
        start_edit.setDisplayFormat("HH:mm")
        self.gold_schedule_table.setCellWidget(row, 0, start_edit)

        end_edit = QTimeEdit()
        end_parts = end.split(':')
        end_edit.setTime(QTime(int(end_parts[0]), int(end_parts[1])))
        end_edit.setDisplayFormat("HH:mm")
        self.gold_schedule_table.setCellWidget(row, 1, end_edit)

        del_btn = QPushButton("删除")
        del_btn.setFixedWidth(60)
        del_btn.clicked.connect(lambda: self._remove_gold_schedule_row())
        self.gold_schedule_table.setCellWidget(row, 2, del_btn)

    def _remove_gold_schedule_row(self):
        """删除黄金时间段行"""
        for i in range(self.gold_schedule_table.rowCount()):
            btn = self.gold_schedule_table.cellWidget(i, 2)
            if btn == self.sender():
                self.gold_schedule_table.removeRow(i)
                break

    def closeEvent(self, event: QCloseEvent):
        """关闭时隐藏而不是退出"""
        event.ignore()
        self.hide()

    def showEvent(self, event):
        """显示时刷新数据"""
        super().showEvent(event)
        self._load_current_settings()

    # === 自定义标题栏拖动 / 最大化 / 边缘拉伸 ===

    _EDGE_CURSORS = {
        'left': Qt.CursorShape.SizeHorCursor,
        'right': Qt.CursorShape.SizeHorCursor,
        'top': Qt.CursorShape.SizeVerCursor,
        'bottom': Qt.CursorShape.SizeVerCursor,
        'top-left': Qt.CursorShape.SizeFDiagCursor,
        'bottom-right': Qt.CursorShape.SizeFDiagCursor,
        'top-right': Qt.CursorShape.SizeBDiagCursor,
        'bottom-left': Qt.CursorShape.SizeBDiagCursor,
    }

    def _edge_at(self, pos: QPoint) -> str:
        m = self.RESIZE_MARGIN
        x, y = pos.x(), pos.y()
        w, h = self.width(), self.height()
        on_left = x < m
        on_right = x >= w - m
        on_top = y < m
        on_bottom = y >= h - m
        if on_top and on_left: return 'top-left'
        if on_top and on_right: return 'top-right'
        if on_bottom and on_left: return 'bottom-left'
        if on_bottom and on_right: return 'bottom-right'
        if on_left: return 'left'
        if on_right: return 'right'
        if on_top: return 'top'
        if on_bottom: return 'bottom'
        return ''

    def _do_edge_resize(self, global_pos: QPoint) -> None:
        if not self._resize_origin or not self._resize_geometry:
            return
        diff = global_pos - self._resize_origin
        geo = QRect(self._resize_geometry)
        if 'left' in self._resize_edge:
            geo.setLeft(geo.left() + diff.x())
        if 'right' in self._resize_edge:
            geo.setRight(geo.right() + diff.x())
        if 'top' in self._resize_edge:
            geo.setTop(geo.top() + diff.y())
        if 'bottom' in self._resize_edge:
            geo.setBottom(geo.bottom() + diff.y())
        min_w = max(self.minimumWidth(), 100)
        min_h = max(self.minimumHeight(), 80)
        if geo.width() >= min_w and geo.height() >= min_h:
            self.setGeometry(geo)

    def _toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
            self._max_btn.setText("\u25a1")
        else:
            self.showMaximized()
            self._max_btn.setText("\u2750")

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            edge = self._edge_at(pos)
            if edge:
                self._resize_edge = edge
                self._resize_origin = event.globalPosition().toPoint()
                self._resize_geometry = QRect(self.geometry())
                return
            if pos.y() <= self._title_bar.height():
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        global_pos = event.globalPosition().toPoint()
        if self._resize_edge and self._resize_origin:
            self._do_edge_resize(global_pos)
            return
        if self._drag_pos is not None:
            if self.isMaximized():
                self.showNormal()
                self._max_btn.setText("\u25a1")
                self._drag_pos = QPoint(self.width() // 2, self._title_bar.height() // 2)
            self.move(global_pos - self._drag_pos)
        else:
            # 悬停时更新光标
            pos = event.position().toPoint()
            edge = self._edge_at(pos)
            cursor = self._EDGE_CURSORS.get(edge)
            if cursor:
                self.setCursor(cursor)
            else:
                self.unsetCursor()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self._resize_edge:
            self._resize_edge = ""
            self._resize_origin = None
            self._resize_geometry = None
            return
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.position().y() <= self._title_bar.height():
            self._toggle_maximize()
        super().mouseDoubleClickEvent(event)
