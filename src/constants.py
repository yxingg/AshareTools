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
    # 预警配置
    "alert": {
        "enabled": False,
        "tasks": [],  # 预警任务列表 [{"symbol": "600519", "strategy": "MA_TREND", "period": "5"}, ...]
        "scan_interval": 20,
        "dingtalk": {
            "webhook": "",
            "secret": ""
        }
    }
}
