# settings_manager.py - 配置管理器
"""配置管理器 - 负责加载和保存所有配置"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

from .config import SETTINGS_PATH
from .constants import DEFAULT_SETTINGS

logger = logging.getLogger(__name__)


class SettingsManager:
    """配置管理器"""
    
    def __init__(self):
        self._settings: Dict[str, Any] = {}
        self._dirty = False
        self.load()

    def load(self):
        """加载配置"""
        try:
            if SETTINGS_PATH.exists():
                with open(SETTINGS_PATH, 'r', encoding='utf-8') as f:
                    self._settings = json.load(f)
                logger.info(f"配置已加载: {SETTINGS_PATH}")
            else:
                self._settings = DEFAULT_SETTINGS.copy()
                logger.info("使用默认配置")
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            self._settings = DEFAULT_SETTINGS.copy()

    def save(self):
        """保存配置"""
        try:
            SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(SETTINGS_PATH, 'w', encoding='utf-8') as f:
                json.dump(self._settings, f, ensure_ascii=False, indent=2)
            self._dirty = False
            logger.info(f"配置已保存: {SETTINGS_PATH}")
        except Exception as e:
            logger.error(f"保存配置失败: {e}")

    def _ensure_quote_window(self):
        """确保 quote_window 配置存在"""
        if 'quote_window' not in self._settings:
            self._settings['quote_window'] = DEFAULT_SETTINGS['quote_window'].copy()

    def _ensure_alert(self):
        """确保 alert 配置存在"""
        if 'alert' not in self._settings:
            self._settings['alert'] = DEFAULT_SETTINGS['alert'].copy()

    # ===== 行情窗口配置 =====
    
    def get_quote_config(self) -> Dict:
        """获取行情窗口配置"""
        self._ensure_quote_window()
        return self._settings['quote_window']

    def set_quote_config(self, config: Dict):
        """设置行情窗口配置"""
        self._ensure_quote_window()
        self._settings['quote_window'].update(config)
        self._dirty = True

    def get_quote_enabled(self) -> bool:
        """获取行情窗口是否启用"""
        self._ensure_quote_window()
        return self._settings['quote_window'].get('enabled', True)

    def set_quote_enabled(self, enabled: bool):
        """设置行情窗口是否启用"""
        self._ensure_quote_window()
        self._settings['quote_window']['enabled'] = enabled
        self._dirty = True
        self.save()

    def get_quote_stocks(self) -> List[str]:
        """获取行情窗口股票列表"""
        self._ensure_quote_window()
        return self._settings['quote_window'].get('stocks', [])

    def set_quote_stocks(self, stocks: List[str]):
        """设置行情窗口股票列表"""
        self._ensure_quote_window()
        self._settings['quote_window']['stocks'] = stocks
        self._dirty = True

    # ===== 时间段配置 =====
    
    def get_time_schedule_enabled(self) -> bool:
        """获取定时显示是否启用"""
        self._ensure_quote_window()
        schedule = self._settings['quote_window'].get('time_schedule', {})
        return schedule.get('enabled', False)

    def set_time_schedule_enabled(self, enabled: bool):
        """设置定时显示是否启用"""
        self._ensure_quote_window()
        if 'time_schedule' not in self._settings['quote_window']:
            self._settings['quote_window']['time_schedule'] = {}
        self._settings['quote_window']['time_schedule']['enabled'] = enabled
        self._dirty = True
        self.save()

    def get_time_schedule_periods(self) -> List[Dict]:
        """获取时间段列表"""
        self._ensure_quote_window()
        schedule = self._settings['quote_window'].get('time_schedule', {})
        return schedule.get('periods', [
            {"start": "09:25", "end": "11:35"},
            {"start": "12:55", "end": "15:05"}
        ])

    def set_time_schedule_periods(self, periods: List[Dict]):
        """设置时间段列表"""
        self._ensure_quote_window()
        if 'time_schedule' not in self._settings['quote_window']:
            self._settings['quote_window']['time_schedule'] = {}
        self._settings['quote_window']['time_schedule']['periods'] = periods
        self._dirty = True
        self.save()

    # ===== 预警配置 =====
    
    def get_alert_config(self) -> Dict:
        """获取预警配置"""
        self._ensure_alert()
        return self._settings['alert']

    def get_alert_enabled(self) -> bool:
        """获取预警是否启用"""
        self._ensure_alert()
        return self._settings['alert'].get('enabled', False)

    def set_alert_enabled(self, enabled: bool):
        """设置预警是否启用"""
        self._ensure_alert()
        self._settings['alert']['enabled'] = enabled
        self._dirty = True
        self.save()

    def get_alert_tasks(self) -> List[Dict]:
        """获取预警任务列表"""
        self._ensure_alert()
        return self._settings['alert'].get('tasks', [])

    def set_alert_tasks(self, tasks: List[Dict]):
        """设置预警任务列表"""
        self._ensure_alert()
        self._settings['alert']['tasks'] = tasks
        self._dirty = True
        self.save()

    def get_alert_scan_interval(self) -> int:
        """获取预警扫描间隔"""
        self._ensure_alert()
        return self._settings['alert'].get('scan_interval', 20)

    def set_alert_scan_interval(self, interval: int):
        """设置预警扫描间隔"""
        self._ensure_alert()
        self._settings['alert']['scan_interval'] = interval
        self._dirty = True
        self.save()

    def get_dingtalk_config(self) -> Dict:
        """获取钉钉配置"""
        self._ensure_alert()
        return self._settings['alert'].get('dingtalk', {'webhook': '', 'secret': ''})

    def set_dingtalk_config(self, config: Dict):
        """设置钉钉配置"""
        self._ensure_alert()
        self._settings['alert']['dingtalk'] = config
        self._dirty = True
        self.save()

    # ===== 通用方法 =====

    def get_all(self) -> Dict:
        """获取所有配置"""
        return self._settings.copy()

    def update_quote_window_settings(self, settings: Dict):
        """更新行情窗口设置"""
        self._ensure_quote_window()
        self._settings['quote_window'].update(settings)
        self._dirty = True
        self.save()
