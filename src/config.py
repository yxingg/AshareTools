# config.py - 静态配置文件
"""
系统级静态配置，很少修改的配置项放在这里。
运行时配置（股票列表、预警任务等）保存在 settings.json 中。
"""
import sys
import os
from pathlib import Path

# ================= 路径配置 =================
def _runtime_base_dir() -> Path:
    """获取运行时基础目录（支持打包后的 EXE）"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent

BASE_DIR = _runtime_base_dir()
SETTINGS_PATH = BASE_DIR / "settings.json"
LOG_PATH = BASE_DIR / "asharetools.log"
STRATEGIES_FILE = BASE_DIR / "strategies.py"  # 策略定义文件
STOCK_CACHE_FILE = BASE_DIR / "stock_names.json"  # 股票名称缓存
ICON_PATH = BASE_DIR / "icon.png"  # 程序图标

# ================= 钉钉机器人配置 =================
# 请在钉钉机器人安全设置中勾选"自定义关键词"，并添加关键词 "交易提醒"
DINGTALK_WEBHOOK = "https://oapi.dingtalk.com/robot/send?access_token=YOUR_TOKEN_HERE"
DINGTALK_SECRET = "YOUR_SECRET_HERE"

# ================= 系统默认配置 =================
DEFAULT_SCAN_INTERVAL = 20  # 预警轮询间隔(秒)
DEFAULT_QUOTE_INTERVAL = 5  # 行情刷新间隔(秒)
DEFAULT_MAX_WORKERS = 10    # 最大并行线程数

# ================= 数据源配置 =================
AVAILABLE_DATA_SOURCES = ['em', 'tx', 'sina']  # 东方财富、腾讯、新浪

# ================= 日志配置 =================
LOG_LEVEL = "INFO"
LOG_BACKUP_COUNT = 30  # 日志保留天数
