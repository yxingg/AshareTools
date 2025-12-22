# gui/quote_manager.py - 行情窗口管理器
"""行情窗口管理器"""

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QApplication,
    QInputDialog,
    QMenu,
    QMessageBox,
    QWidget,
)

from ..constants import COLUMN_COUNT, DEFAULT_WINDOW_CONFIG
from ..data_fetcher import QuoteFetcher, StockQuote
from ..utils import normalize_stock_code, color_to_rgba
from .float_window import StockFloatWindow

logger = logging.getLogger(__name__)


class QuoteWindowManager:
    """行情窗口管理器"""
    
    def __init__(self, on_settings_changed=None, on_visibility_changed=None):
        self.fetcher = QuoteFetcher()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="quote-fetch")
        
        # 股票列表和设置
        self.codes: List[str] = []
        self.code_settings: Dict[str, Dict[str, Any]] = {}  # 包含每个股票窗口的位置、大小等
        self.quotes: Dict[str, StockQuote] = {}
        self.windows: Dict[str, StockFloatWindow] = {}
        
        # 窗口设置
        self.background_color = QColor(28, 28, 30)
        self.background_alpha = 220
        self.text_alpha = 255
        self.neutral_color = QColor(230, 230, 230)
        self.up_color = QColor(217, 48, 80)
        self.down_color = QColor(0, 158, 96)
        
        self.font_size = 14
        self.show_name = True
        self.show_code = True
        self.show_column_header = True
        self.always_on_top = True
        self.update_interval = 5
        
        self.column_widths: List[int] = [160, 140, 120, 120, 140, 140]
        self.row_height = 44
        self.window_size = (620, 140)
        
        # 状态
        self.fetch_in_progress = False
        self._force_refresh_requested = False
        self._visible = True  # 是否显示窗口
        
        # 回调
        self.on_settings_changed = on_settings_changed
        self.on_visibility_changed = on_visibility_changed  # 窗口可见性变化回调
        
        # 刷新定时器
        self.fetch_timer = QTimer()
        self.fetch_timer.setInterval(self.update_interval * 1000)
        self.fetch_timer.timeout.connect(self.refresh_quotes)

    def load_settings(self, settings: Dict):
        """从配置加载设置"""
        quote_config = settings.get('quote_window', {})
        
        self.codes = quote_config.get('stocks', [])
        self.code_settings = quote_config.get('code_settings', {})
        
        ws = quote_config.get('settings', {})
        self.font_size = ws.get('font_size', 14)
        self.background_alpha = ws.get('background_alpha', 220)
        self.text_alpha = ws.get('text_alpha', 255)
        self.show_name = ws.get('show_name', True)
        self.show_code = ws.get('show_code', True)
        self.show_column_header = ws.get('show_column_header', True)
        self.always_on_top = ws.get('always_on_top', True)
        self.column_widths = ws.get('column_widths', [160, 140, 120, 120, 140, 140])
        self.row_height = ws.get('row_height', 44)
        self.window_size = tuple(ws.get('window_size', [620, 140]))
        self.update_interval = ws.get('update_interval', 5)
        
        self.fetch_timer.setInterval(self.update_interval * 1000)

    def save_settings(self) -> Dict:
        """保存设置"""
        return {
            'stocks': self.codes,
            'code_settings': self.code_settings,
            'settings': {
                'font_size': self.font_size,
                'background_alpha': self.background_alpha,
                'text_alpha': self.text_alpha,
                'show_name': self.show_name,
                'show_code': self.show_code,
                'show_column_header': self.show_column_header,
                'always_on_top': self.always_on_top,
                'column_widths': self.column_widths,
                'row_height': self.row_height,
                'window_size': list(self.window_size),
                'update_interval': self.update_interval,
            }
        }

    def start(self):
        """启动行情刷新"""
        self._ensure_windows(initial=True)
        if self.codes:
            self.refresh_quotes(force=True)
        self.fetch_timer.start()

    def stop(self):
        """停止行情刷新"""
        self.fetch_timer.stop()

    def show_windows(self):
        """显示所有窗口"""
        self._visible = True
        self._ensure_windows(initial=True)
        for window in self.windows.values():
            window.show()
            window.raise_()  # 确保窗口在最前面

    def hide_windows(self):
        """隐藏所有窗口"""
        self._visible = False
        for window in self.windows.values():
            window.hide()

    def close_all_windows(self):
        """关闭所有窗口"""
        self._visible = False
        for window in self.windows.values():
            window.close()
        self.windows.clear()

    def _close_windows_and_notify(self):
        """关闭窗口并通知托盘更新状态"""
        self.hide_windows()
        if self.on_visibility_changed:
            self.on_visibility_changed(False)

    def is_visible(self) -> bool:
        """是否可见"""
        return self._visible

    def toggle_visibility(self):
        """切换显示状态"""
        if self._visible:
            self.hide_windows()
        else:
            self.show_windows()

    def _window_config(self) -> Dict[str, Any]:
        """生成窗口配置"""
        bg = QColor(self.background_color)
        bg.setAlpha(self.background_alpha)
        
        neutral = QColor(self.neutral_color)
        neutral.setAlpha(self.text_alpha)
        
        up = QColor(self.up_color)
        up.setAlpha(self.text_alpha)
        
        down = QColor(self.down_color)
        down.setAlpha(self.text_alpha)
        
        return {
            "background_color": bg,
            "neutral_color": neutral,
            "up_color": up,
            "down_color": down,
            "font_size": self.font_size,
            "show_name": self.show_name,
            "show_code": self.show_code,
            "show_column_header": self.show_column_header,
            "column_widths": self.column_widths,
            "row_height": self.row_height,
            "window_size": self.window_size,
        }

    def _ensure_windows(self, initial: bool = False):
        """确保窗口存在"""
        config = self._window_config()
        
        # 创建新窗口
        for code in self.codes:
            if code not in self.windows:
                window = StockFloatWindow(self, code)
                window.apply_settings(config, initial=initial)
                window.update_quote(self.quotes.get(code))
                
                # 恢复窗口位置和大小
                code_cfg = self.code_settings.get(code, {})
                if 'window_pos' in code_cfg:
                    pos = code_cfg['window_pos']
                    window.move(pos[0], pos[1])
                if 'window_size' in code_cfg:
                    size = code_cfg['window_size']
                    window.resize(size[0], size[1])
                
                if self._visible:
                    window.show()
                else:
                    window.hide()
                self.windows[code] = window
        
        # 移除多余窗口
        for code in list(self.windows.keys()):
            if code not in self.codes:
                self.windows[code].close()
                del self.windows[code]

    def _apply_settings_to_all(self):
        """应用设置到所有窗口"""
        config = self._window_config()
        for window in self.windows.values():
            window.apply_settings(config, initial=False)

    def _notify_settings_changed(self):
        """通知设置改变"""
        if self.on_settings_changed:
            self.on_settings_changed()

    def populate_context_menu(self, menu: QMenu, anchor: QWidget, code: Optional[str]) -> None:
        """填充右键菜单（供 float_window 调用）"""
        add_action = menu.addAction("添加股票")
        add_action.triggered.connect(lambda: self.prompt_add_code(anchor))

        remove_action = menu.addAction("删除当前股票")
        if code:
            remove_action.triggered.connect(lambda: self.remove_code(code))
        else:
            remove_action.setEnabled(False)

        menu.addSeparator()

        if code:
            unit_action = menu.addAction("设置挂单单位...")
            unit_action.triggered.connect(lambda: self.prompt_volume_unit(anchor, code))
            menu.addSeparator()

        show_name_action = menu.addAction("显示名称")
        show_name_action.setCheckable(True)
        show_name_action.setChecked(self.show_name)
        show_name_action.triggered.connect(lambda checked: self.set_show_name(checked))

        show_code_action = menu.addAction("显示代码")
        show_code_action.setCheckable(True)
        show_code_action.setChecked(self.show_code)
        show_code_action.triggered.connect(lambda checked: self.set_show_code(checked))

        header_action = menu.addAction("显示标题栏")
        header_action.setCheckable(True)
        header_action.setChecked(self.show_column_header)
        header_action.triggered.connect(lambda checked: self.set_show_column_header(checked))

        top_action = menu.addAction("始终置顶")
        top_action.setCheckable(True)
        top_action.setChecked(self.always_on_top)
        top_action.triggered.connect(lambda checked: self.set_always_on_top(checked))

        menu.addSeparator()

        font_action = menu.addAction("设置字体大小...")
        font_action.triggered.connect(lambda: self.prompt_font_size(anchor))

        bg_alpha_action = menu.addAction("背景透明度...")
        bg_alpha_action.triggered.connect(lambda: self.prompt_background_alpha(anchor))

        text_alpha_action = menu.addAction("文字透明度...")
        text_alpha_action.triggered.connect(lambda: self.prompt_text_alpha(anchor))

        interval_action = menu.addAction("设置刷新频率...")
        interval_action.triggered.connect(lambda: self.prompt_update_interval(anchor))

        menu.addSeparator()

        fit_current = menu.addAction("自适应当前窗口")
        if code:
            fit_current.triggered.connect(lambda: self.auto_fit_code(code))
        else:
            fit_current.setEnabled(False)

        fit_all = menu.addAction("自适应全部窗口")
        fit_all.triggered.connect(self.auto_fit_all)
        
        menu.addSeparator()
        
        # 关闭行情窗口放最后
        close_action = menu.addAction("关闭行情窗口")
        close_action.triggered.connect(self._close_windows_and_notify)

    def prompt_add_code(self, parent: QWidget) -> None:
        code, ok = QInputDialog.getText(parent, "添加股票", "请输入股票代码:")
        if ok and code:
            self.add_code(code)

    def prompt_volume_unit(self, parent: QWidget, code: str) -> None:
        current_unit = self.code_settings.get(code, {}).get("volume_unit", 100)
        value, ok = QInputDialog.getInt(parent, "挂单单位", "单位(手, 0为隐藏):", current_unit, 0, 1000000, 100)
        if ok:
            if code not in self.code_settings:
                self.code_settings[code] = {}
            self.code_settings[code]["volume_unit"] = value
            self._notify_settings_changed()
            if code in self.windows:
                window = self.windows[code]
                window.apply_settings(self._window_config(), initial=False)
                window.update_quote(self.quotes.get(code))

    def prompt_font_size(self, parent: QWidget) -> None:
        value, ok = QInputDialog.getInt(parent, "字体大小", "字号:", self.font_size, 8, 48, 1)
        if ok:
            self.font_size = value
            self._apply_settings_to_all()
            self._notify_settings_changed()

    def prompt_background_alpha(self, parent: QWidget) -> None:
        value, ok = QInputDialog.getInt(parent, "背景透明度", "0-255:", self.background_alpha, 0, 255, 1)
        if ok:
            self.background_alpha = value
            self._apply_settings_to_all()
            self._notify_settings_changed()

    def prompt_text_alpha(self, parent: QWidget) -> None:
        value, ok = QInputDialog.getInt(parent, "文字透明度", "0-255:", self.text_alpha, 0, 255, 1)
        if ok:
            self.text_alpha = value
            self._apply_settings_to_all()
            self._notify_settings_changed()

    def prompt_update_interval(self, parent: QWidget) -> None:
        value, ok = QInputDialog.getInt(parent, "刷新频率", "秒:", self.update_interval, 1, 3600, 1)
        if ok:
            self.update_interval = value
            self.fetch_timer.setInterval(self.update_interval * 1000)
            self._notify_settings_changed()

    def add_code(self, code: str) -> None:
        normalized = normalize_stock_code(code)
        if not normalized:
            return
        if normalized in self.codes:
            return
        self.codes.append(normalized)
        self._ensure_windows(initial=True)
        self.refresh_quotes(force=True)
        self._notify_settings_changed()

    def remove_code(self, code: str) -> None:
        if code not in self.codes:
            return
        self.codes.remove(code)
        window = self.windows.pop(code, None)
        if window:
            window.close()
        self.quotes.pop(code, None)
        self._notify_settings_changed()

    def set_show_name(self, value: bool) -> None:
        if self.show_name == value:
            return
        self.show_name = value
        self._apply_settings_to_all()
        self._notify_settings_changed()

    def set_show_code(self, value: bool) -> None:
        if self.show_code == value:
            return
        self.show_code = value
        self._apply_settings_to_all()
        self._notify_settings_changed()

    def set_show_column_header(self, value: bool) -> None:
        if self.show_column_header == value:
            return
        self.show_column_header = value
        self._apply_settings_to_all()
        self._notify_settings_changed()

    def set_always_on_top(self, value: bool) -> None:
        if self.always_on_top == value:
            return
        self.always_on_top = value
        self._apply_settings_to_all()
        self._notify_settings_changed()

    def auto_fit_code(self, code: str) -> None:
        window = self.windows.get(code)
        if window:
            window.auto_fit()
            self.sync_from_window(window)

    def auto_fit_all(self) -> None:
        for window in self.windows.values():
            window.auto_fit()
            self.sync_from_window(window)

    def sync_from_window(self, window: StockFloatWindow) -> None:
        """从窗口同步设置（包括位置和大小）"""
        self.column_widths = window.get_column_widths()
        self.row_height = window.get_row_height()
        self.window_size = window.get_window_size()
        
        # 保存窗口位置和大小到code_settings
        code = window.code
        if code not in self.code_settings:
            self.code_settings[code] = {}
        self.code_settings[code]['window_pos'] = [window.x(), window.y()]
        self.code_settings[code]['window_size'] = list(window.get_window_size())
        
        self._notify_settings_changed()

    def refresh_quotes(self, force: bool = False) -> None:
        """刷新行情"""
        if not self.codes:
            return
        if self.fetch_in_progress:
            if force:
                self._force_refresh_requested = True
            return
        self.fetch_in_progress = True
        self._force_refresh_requested = False
        self.executor.submit(self._fetch_worker, list(self.codes))

    def _fetch_worker(self, codes: List[str]) -> None:
        """获取行情的工作线程"""
        try:
            quotes = self.fetcher.fetch(codes)
            # 在主线程更新
            QApplication.instance().postEvent(
                QApplication.instance(),
                _QuoteUpdateEvent(quotes)
            )
        except Exception as e:
            logger.warning(f"获取行情失败: {e}")
        finally:
            self.fetch_in_progress = False
            if self._force_refresh_requested:
                self.refresh_quotes(force=True)

    def on_quotes_received(self, quotes: List[StockQuote]) -> None:
        """收到行情数据"""
        for quote in quotes:
            self.quotes[quote.code] = quote
            if quote.code in self.windows:
                self.windows[quote.code].update_quote(quote)


# 自定义事件用于跨线程通信
from PyQt6.QtCore import QEvent

class _QuoteUpdateEvent(QEvent):
    EVENT_TYPE = QEvent.Type(QEvent.registerEventType())
    
    def __init__(self, quotes):
        super().__init__(self.EVENT_TYPE)
        self.quotes = quotes
