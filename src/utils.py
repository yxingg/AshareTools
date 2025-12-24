# utils.py - 通用工具函数
"""通用工具函数模块"""

import re
import sys
from pathlib import Path
from typing import Optional, List, Iterator


def get_resource_path(relative_path: str) -> Path:
    """
    获取资源文件的绝对路径
    支持开发环境和 PyInstaller 打包环境
    """
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller 打包后的临时目录
        return Path(sys._MEIPASS) / relative_path
    # 开发环境: 假设 utils.py 在 src/ 目录下，资源文件在项目根目录
    return Path(__file__).resolve().parent.parent / relative_path


def normalize_stock_code(raw: str) -> Optional[str]:
    """
    标准化股票代码
    支持格式: 600519, sh600519, SH600519, 00700.HK, hk00700, AAPL 等
    可转债: 11xxxx(沪), 12xxxx(深)
    """
    if not raw:
        return None
    
    raw = raw.strip().lower()
    
    # 移除可能的后缀
    raw = raw.replace('.sh', '').replace('.sz', '').replace('.hk', '')
    
    # 沪深A股/可转债: 6位纯数字
    if re.match(r'^\d{6}$', raw):
        # 上海: 6开头股票, 9开头B股, 11开头可转债
        if raw.startswith(('6', '9', '11')):
            return f"sh{raw}"
        # 深圳: 0开头主板, 3开头创业板, 2开头B股, 12开头可转债
        elif raw.startswith(('0', '3', '2', '12')):
            return f"sz{raw}"
        # 北交所: 4开头或8开头
        elif raw.startswith(('4', '8')):
            return f"bj{raw}"
        else:
            return f"sz{raw}"
    
    # 已带前缀的 A 股
    if re.match(r'^(sh|sz|bj)\d{6}$', raw):
        return raw
    
    # 港股: hk + 5位数字
    if re.match(r'^hk\d{5}$', raw):
        return raw
    if re.match(r'^\d{5}$', raw):
        return f"hk{raw}"
    
    # 美股: 纯字母
    if re.match(r'^[a-z]+$', raw) and len(raw) <= 5:
        return raw
    
    # 基金代码
    if re.match(r'^(f_|of)\d{6}$', raw):
        return raw
    
    return None


def split_text(text: str, delimiter: str) -> Iterator[str]:
    """按分隔符拆分文本，跳过空块"""
    for block in text.split(delimiter):
        block = block.strip()
        if block:
            yield block


def get_market_prefix(symbol: str) -> tuple:
    """
    根据股票代码获取市场前缀
    返回: (market_prefix, pure_code)
    """
    symbol = symbol.lower()
    
    if symbol.startswith('sh'):
        return 'sh', symbol[2:]
    elif symbol.startswith('sz'):
        return 'sz', symbol[2:]
    elif symbol.startswith('bj'):
        return 'bj', symbol[2:]
    elif symbol.startswith('hk'):
        return 'hk', symbol[2:]
    elif symbol.isdigit() and len(symbol) == 6:
        if symbol.startswith('6') or symbol.startswith('9'):
            return 'sh', symbol
        elif symbol.startswith(('4', '8')):
            return 'bj', symbol
        else:
            return 'sz', symbol
    else:
        return '', symbol


def format_number(value: float, precision: int = 2) -> str:
    """格式化数字，去除末尾的0"""
    s = f"{value:.{precision}f}"
    if '.' in s:
        s = s.rstrip('0').rstrip('.')
    return s if s else '0'


def format_change(value: float, precision: int = 2, suffix: str = '') -> str:
    """格式化涨跌值，带正负号"""
    sign = '+' if value > 0 else ''
    s = f"{sign}{value:.{precision}f}"
    if '.' in s:
        s = s.rstrip('0').rstrip('.')
    return s + suffix


def color_to_rgba(color) -> str:
    """将 QColor 转换为 CSS rgba 字符串"""
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()})"


def get_market_short_name(code: str) -> str:
    """
    获取市场简称
    返回: 沪、深、京、科、创、美、港
    """
    code = code.lower()
    
    if code.startswith('hk'):
        return '港'
    
    if code.startswith('sh'):
        pure = code[2:]
        if pure.startswith('688'):
            return '科'  # 科创板
        return '沪'
    
    if code.startswith('sz'):
        pure = code[2:]
        if pure.startswith('3'):
            return '创'  # 创业板
        return '深'
    
    if code.startswith('bj'):
        return '京'  # 北交所
    
    # 美股（纯字母）
    if code.isalpha():
        return '美'
    
    # 无前缀的数字代码
    if code.isdigit() and len(code) == 6:
        if code.startswith('6'):
            if code.startswith('688'):
                return '科'
            return '沪'
        elif code.startswith('3'):
            return '创'
        elif code.startswith(('4', '8')):
            return '京'
        else:
            return '深'
    
    return ''


def get_security_type(code: str) -> str:
    """
    获取证券类型标识
    返回: 股、基、债
    """
    code = code.lower()
    
    # 可转债: 11xxxx(沪), 12xxxx(深)
    if code.startswith('sh11') or code.startswith('sz12'):
        return '债'
    
    # 场内基金 (ETF/LOF): 51xxxx, 15xxxx, 16xxxx, 58xxxx
    if code.startswith('f_') or code.startswith('of'):
        return '基'
    
    pure_code = code[2:] if code.startswith(('sh', 'sz', 'bj')) else code
    if len(pure_code) == 6:
        # 上海场内基金 51xxxx, 58xxxx
        if pure_code.startswith(('51', '58')):
            return '基'
        # 深圳场内基金 15xxxx, 16xxxx
        if pure_code.startswith(('15', '16')):
            return '基'
    
    return '股'
