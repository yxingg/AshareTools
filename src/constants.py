# constants.py - GUI 常量定义

# 表格列定义
COLUMN_COUNT = 6
COLUMN_HEADERS = ["名称", "代码", "现价", "涨跌", "涨跌幅", "挂单"]

# 默认颜色配置
DEFAULT_COLORS = {
    "background": (28, 28, 30),
    "neutral": (230, 230, 230),
    "up": (217, 48, 80),      # 上涨 - 红色
    "down": (0, 158, 96),     # 下跌 - 绿色
}

# 默认窗口配置
DEFAULT_WINDOW_CONFIG = {
    "font_size": 14,
    "background_alpha": 220,
    "text_alpha": 255,
    "show_name": True,
    "show_code": True,
    "show_column_header": True,
    "always_on_top": True,
    "column_widths": [160, 140, 120, 120, 140, 140],
    "row_height": 44,
    "window_size": (620, 140),
}

# 黄金标的定义
DEFAULT_GOLD_TARGETS = [
    {"key": "london_spot", "name": "伦敦金现", "enabled": True},
    {"key": "usd_cny", "name": "美元汇率", "enabled": True},
    {"key": "london_spot_rmb", "name": "伦敦金现（RMB/g）", "enabled": True},
    {"key": "ny_gold", "name": "纽约金", "enabled": True},
    {"key": "au9999", "name": "AU9999", "enabled": True},
]


def _default_gold_symbol_periods():
    """默认黄金定时显示时段（按标的）"""
    base_periods = [
        {"start": "09:25", "end": "11:35"},
        {"start": "12:55", "end": "15:05"},
    ]
    return {target["key"]: [p.copy() for p in base_periods] for target in DEFAULT_GOLD_TARGETS}


def _default_gold_window_settings():
    """默认黄金窗口样式"""
    settings = DEFAULT_WINDOW_CONFIG.copy()
    settings["show_name"] = False
    settings["show_code"] = False
    settings["show_column_header"] = False
    settings["update_interval"] = 1
    settings["column_widths"] = [140, 140, 140]
    settings["window_size"] = (420, 120)
    return settings

# 默认设置
DEFAULT_SETTINGS = {
    # 行情窗口配置
    "quote_window": {
        "enabled": True,
        "stocks": [],  # 行情窗口显示的股票代码列表
        "settings": DEFAULT_WINDOW_CONFIG.copy(),
        "code_settings": {},  # 每个股票的独立设置
        "time_schedule": {
            "enabled": False,
            "periods": [
                {"start": "09:25", "end": "11:35"},
                {"start": "12:55", "end": "15:05"}
            ]
        }
    },
    # 黄金行情窗口配置（界面预留，行情实现后接入）
    "gold_window": {
        "enabled": False,
        "targets": [target.copy() for target in DEFAULT_GOLD_TARGETS],
        "settings": _default_gold_window_settings(),
        "code_settings": {},
        "time_schedule": {
            "enabled": False,
            "symbol_periods": _default_gold_symbol_periods()
        }
    },
    # 预警配置
    "alert": {
        "enabled": False,
        "tasks": [],  # 预警任务列表 [{"symbol": "600519", "strategy": "MA_TREND", "period": "5", "enabled": True}, ...]
        "scan_interval": 20,
        "gold_tasks": [],  # 黄金预警任务列表 [{"target": "au9999", "price": 700, "frequency": 0, "enabled": True}, ...]
        "gold_scan_interval": 20,
        "dingtalk": {
            "webhook": "",
            "secret": ""
        }
    }
}
