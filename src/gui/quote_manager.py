# gui/quote_manager.py - 行情窗口管理器
"""行情窗口管理器"""

import logging
import queue
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QApplication,
    QInputDialog,
    QMenu,
    QWidget,
)

from ..data_fetcher import QuoteFetcher, StockQuote
from ..utils import normalize_stock_code
from .float_window import StockFloatWindow

logger = logging.getLogger(__name__)


class QuoteWindowManager:
    """行情窗口管理器"""
    
    def __init__(self, on_settings_changed=None, on_visibility_changed=None):
        self.fetcher = QuoteFetcher()
        self.executor: Optional[ThreadPoolExecutor] = ThreadPoolExecutor(max_workers=1, thread_name_prefix="quote-fetch")
        
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
        self._visible = False  # 是否显示窗口
        self._last_requested_codes: set[str] = set()

        # 预警特权拉取（窗口隐藏时，允许有预警的标的按预警频率拉取）
        self._alert_poll_intervals: Dict[str, int] = {}
        self._alert_last_poll_time: Dict[str, float] = {}
        self._default_alert_poll_interval = 20
        
        # 回调
        self.on_settings_changed = on_settings_changed
        self.on_visibility_changed = on_visibility_changed  # 窗口可见性变化回调
        
        # 跨线程数据队列
        self._quote_queue: queue.Queue[List[StockQuote]] = queue.Queue()

        # 刷新定时器
        self.fetch_timer = QTimer()
        self.fetch_timer.setInterval(self.update_interval * 1000)
        self.fetch_timer.timeout.connect(self.refresh_quotes)

        # 窗口手动调整后的防抖保存（5秒）
        self._sync_delay_ms = 5000
        self._pending_sync_codes: set[str] = set()
        self._sync_timer = QTimer()
        self._sync_timer.setSingleShot(True)
        self._sync_timer.timeout.connect(self._flush_synced_settings)

    def load_settings(self, settings: Dict):
        """从配置加载设置"""
        quote_config = settings.get('quote_window', {})
        self._visible = bool(quote_config.get('enabled', True))
        
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
        if self.executor is None:
            self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="quote-fetch")
        self._ensure_windows(initial=True)
        if self._visible and self.codes:
            self.refresh_quotes(force=True)
        self._reconcile_polling_state()

    def stop(self):
        """停止行情刷新"""
        self.fetch_timer.stop()
        self._force_refresh_requested = False
        self._last_requested_codes = set()
        if self.executor:
            self.executor.shutdown(wait=False, cancel_futures=True)
            self.executor = None

    def set_alert_polling_config(self, alert_tasks: List[Dict[str, Any]], default_interval: int = 20) -> None:
        """配置隐藏窗口下的预警特权拉取频率（秒）"""
        self._default_alert_poll_interval = max(1, int(default_interval or 20))
        intervals: Dict[str, int] = {}

        for task in alert_tasks or []:
            if not task.get('enabled', True):
                continue

            symbol = str(task.get('symbol', '')).strip()
            if not symbol:
                continue

            normalized = normalize_stock_code(symbol)
            if not normalized:
                continue

            try:
                task_interval = int(task.get('interval', 0) or 0)
            except Exception:
                task_interval = 0

            poll_sec = self._default_alert_poll_interval if task_interval <= 0 else max(1, task_interval)
            prev = intervals.get(normalized)
            if prev is None or poll_sec < prev:
                intervals[normalized] = poll_sec

        self._alert_poll_intervals = intervals
        self._alert_last_poll_time = {
            code: ts for code, ts in self._alert_last_poll_time.items() if code in intervals
        }
        self._reconcile_polling_state()

    def _reconcile_polling_state(self) -> None:
        """根据当前显示状态和预警特权配置启停轮询定时器。"""
        need_polling = bool((self._visible and self.codes) or self._alert_poll_intervals)
        if need_polling:
            intervals: List[int] = []
            if self._visible and self.codes:
                intervals.append(max(1, int(self.update_interval)))
            if self._alert_poll_intervals:
                intervals.append(max(1, min(int(v) for v in self._alert_poll_intervals.values())))
            target_interval = max(1, min(intervals) if intervals else int(self.update_interval))
            if self.fetch_timer.interval() != target_interval * 1000:
                self.fetch_timer.setInterval(target_interval * 1000)
            if not self.fetch_timer.isActive():
                self.fetch_timer.start()
            return
        if self.fetch_timer.isActive():
            self.fetch_timer.stop()

    def show_windows(self):
        """显示所有窗口"""
        state_changed = not self._visible
        self._visible = True
        if self.executor is None:
            self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="quote-fetch")
        self._ensure_windows(initial=True)
        for window in self.windows.values():
            window.show()
            window.raise_()  # 确保窗口在最前面
        self._reconcile_polling_state()
        if self.codes:
            self.refresh_quotes(force=True)
        if state_changed and self.on_visibility_changed:
            self.on_visibility_changed(True)

    def hide_windows(self):
        """隐藏所有窗口"""
        state_changed = self._visible
        self._visible = False
        for window in self.windows.values():
            window.hide()
        self._reconcile_polling_state()
        if state_changed and self.on_visibility_changed:
            self.on_visibility_changed(False)

    def close_all_windows(self):
        """关闭所有窗口"""
        state_changed = self._visible
        self._visible = False
        self.capture_window_states(notify=False)
        for window in self.windows.values():
            window.close()
        self.windows.clear()
        self._reconcile_polling_state()
        if state_changed and self.on_visibility_changed:
            self.on_visibility_changed(False)

    def _close_windows_and_notify(self):
        """关闭窗口并通知托盘更新状态"""
        self.hide_windows()

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
                # 恢复单窗口置顶设置
                code_cfg = self.code_settings.get(code, {})
                window._always_on_top = code_cfg.get('always_on_top', self.always_on_top)
                window.apply_settings(config, initial=initial)
                window.update_quote(self.quotes.get(code))

                # 恢复窗口位置、大小、列宽（抑制同步）
                window._initializing = True
                self._restore_window_state(window, code_cfg)
                window._initializing = False
                
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
        window = self.windows.get(code)
        top_action.setChecked(window._always_on_top if window else self.always_on_top)
        top_action.triggered.connect(lambda checked, c=code: self.set_window_always_on_top(c, checked))

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
            self._reconcile_polling_state()
            self._notify_settings_changed()

    def add_code(self, code: str) -> None:
        normalized = normalize_stock_code(code)
        if not normalized:
            return
        if normalized in self.codes:
            return
        self.codes.append(normalized)
        self._ensure_windows(initial=True)
        self._reconcile_polling_state()
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
        self._reconcile_polling_state()
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
        self.always_on_top = value
        # 全局设置更新所有窗口
        for code, window in self.windows.items():
            window._always_on_top = value
            if code not in self.code_settings:
                self.code_settings[code] = {}
            self.code_settings[code]['always_on_top'] = value
        self._apply_settings_to_all()
        self._notify_settings_changed()

    def set_window_always_on_top(self, code: str, value: bool) -> None:
        """设置单个窗口的置顶状态"""
        if code not in self.code_settings:
            self.code_settings[code] = {}
        self.code_settings[code]['always_on_top'] = value
        window = self.windows.get(code)
        if window:
            window._always_on_top = value
            window._apply_flags(show=window.isVisible())
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
        self._sync_window_state(window)
        self._pending_sync_codes.add(window.code)
        self._sync_timer.start(self._sync_delay_ms)

    def capture_window_states(self, notify: bool = True) -> None:
        """立即采集所有窗口状态（用于退出前落盘）。"""
        for window in self.windows.values():
            self._sync_window_state(window)
        if notify:
            self._notify_settings_changed()

    def flush_pending_settings(self) -> None:
        """立即刷写防抖中的窗口状态。"""
        if self._sync_timer.isActive():
            self._sync_timer.stop()
        self.capture_window_states(notify=True)
        self._pending_sync_codes.clear()

    def _flush_synced_settings(self) -> None:
        if not self._pending_sync_codes:
            return
        self._pending_sync_codes.clear()
        self._notify_settings_changed()

    def _sync_window_state(self, window: StockFloatWindow) -> None:
        self.column_widths = window.get_column_widths()
        self.row_height = window.get_row_height()
        self.window_size = window.get_window_size()

        code = window.code
        if code not in self.code_settings:
            self.code_settings[code] = {}
        self.code_settings[code]['window_pos'] = [window.x(), window.y()]
        self.code_settings[code]['window_size'] = list(window.get_window_size())
        self.code_settings[code]['column_widths'] = window.get_column_widths()
        self.code_settings[code]['visible'] = bool(window.isVisible())

    def _restore_window_state(self, window: StockFloatWindow, code_cfg: Dict[str, Any]) -> None:
        size = code_cfg.get('window_size')
        if isinstance(size, (list, tuple)) and len(size) == 2:
            try:
                window.resize(max(int(size[0]), 1), max(int(size[1]), 1))
            except Exception:
                pass

        if 'column_widths' in code_cfg:
            for i, w in enumerate(code_cfg.get('column_widths', [])[: window.table.columnCount()]):
                try:
                    window.table.setColumnWidth(i, int(w))
                except Exception:
                    continue

        pos = code_cfg.get('window_pos')
        if isinstance(pos, (list, tuple)) and len(pos) == 2:
            try:
                window.move(int(pos[0]), int(pos[1]))
            except Exception:
                pass

        self._ensure_window_on_screen(window)

    def _ensure_window_on_screen(self, window: StockFloatWindow) -> None:
        screens = QApplication.screens()
        if not screens:
            return

        frame = window.frameGeometry()
        if any(screen.availableGeometry().intersects(frame) for screen in screens):
            return

        target_screen = QApplication.screenAt(frame.center()) or QApplication.primaryScreen() or screens[0]
        area = target_screen.availableGeometry()

        width = min(max(window.width(), window.minimumWidth()), max(1, area.width()))
        height = min(max(window.height(), window.minimumHeight()), max(1, area.height()))
        window.resize(width, height)

        x = min(max(window.x(), area.left()), area.left() + max(0, area.width() - width))
        y = min(max(window.y(), area.top()), area.top() + max(0, area.height() - height))
        window.move(x, y)

    def refresh_quotes(self, force: bool = False) -> None:
        """刷新行情"""
        visible_codes = set(self.codes) if self._visible else set()
        now = time.time()

        alert_codes: set[str] = set()
        for code, interval in self._alert_poll_intervals.items():
            if code in visible_codes:
                continue
            last = self._alert_last_poll_time.get(code, 0.0)
            if force or (now - last) >= max(1, int(interval)):
                alert_codes.add(code)

        request_codes = visible_codes | alert_codes
        if not request_codes:
            return
        if self.fetch_in_progress:
            if force:
                self._force_refresh_requested = True
            return
        self.fetch_in_progress = True
        self._force_refresh_requested = False
        self._last_requested_codes = set(request_codes)
        for code in alert_codes:
            self._alert_last_poll_time[code] = now
        if self.executor is None:
            self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="quote-fetch")
        self.executor.submit(self._fetch_worker, list(request_codes))

    def _fetch_worker(self, codes: List[str]) -> None:
        """获取行情的工作线程"""
        try:
            quotes = self.fetcher.fetch(codes)
            # 数据放入线程安全队列，事件仅做通知
            self._quote_queue.put(quotes)
            app = QApplication.instance()
            if app is not None:
                app.postEvent(app, _QuoteUpdateEvent())
        except Exception as e:
            logger.warning(f"获取行情失败: {e}")
        finally:
            self.fetch_in_progress = False
            if self._force_refresh_requested:
                self.refresh_quotes(force=True)

    def on_quotes_received(self) -> None:
        """收到行情数据，从队列中读取"""
        while not self._quote_queue.empty():
            try:
                quotes = self._quote_queue.get_nowait()
            except queue.Empty:
                break
            for quote in quotes:
                self.quotes[quote.code] = quote
                if quote.code in self._last_requested_codes and quote.code in self.windows:
                    self.windows[quote.code].update_quote(quote)


# 自定义事件用于跨线程通信
from PyQt6.QtCore import QEvent

class _QuoteUpdateEvent(QEvent):
    EVENT_TYPE = QEvent.Type(QEvent.registerEventType())

    def __init__(self):
        super().__init__(self.EVENT_TYPE)
