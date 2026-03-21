# gui/gold_manager.py - 黄金行情窗口管理器
"""黄金行情窗口管理器"""

import logging
import queue
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Callable

from PyQt6.QtCore import QEvent, QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QApplication, QInputDialog, QMenu, QWidget

from ..constants import DEFAULT_GOLD_TARGETS
from ..data_fetcher import GoldQuote, GoldQuoteFetcher
from .float_window import StockFloatWindow

logger = logging.getLogger(__name__)


class GoldWindowManager:
    """黄金行情窗口管理器"""

    def __init__(
        self,
        on_settings_changed: Optional[Callable[[], None]] = None,
        on_visibility_changed: Optional[Callable[[bool], None]] = None,
        on_target_visibility_changed: Optional[Callable[[Dict[str, bool]], None]] = None,
    ):
        self.fetcher = GoldQuoteFetcher()
        self.executor: Optional[ThreadPoolExecutor] = ThreadPoolExecutor(max_workers=1, thread_name_prefix="gold-fetch")

        # 标的列表和设置
        self.targets: List[Dict[str, Any]] = [target.copy() for target in DEFAULT_GOLD_TARGETS]
        self.code_settings: Dict[str, Dict[str, Any]] = {}
        self.quotes: Dict[str, GoldQuote] = {}
        self.windows: Dict[str, StockFloatWindow] = {}

        # 窗口设置
        self.background_color = QColor(28, 28, 30)
        self.background_alpha = 220
        self.text_alpha = 255
        self.neutral_color = QColor(230, 230, 230)
        self.up_color = QColor(217, 48, 80)
        self.down_color = QColor(0, 158, 96)

        self.font_size = 14
        self.show_name = False
        self.show_code = False
        self.show_column_header = False
        self.always_on_top = True
        self.update_interval = 1
        self.disable_volume_column = True
        self.uses_name_code_columns = False
        self.code_column_index = 0

        self.column_widths: List[int] = [140, 140, 140]
        self.row_height = 44
        self.window_size = (620, 140)

        # 状态
        self.fetch_in_progress = False
        self._force_refresh_requested = False
        self._visible = False
        self._last_requested_keys: set[str] = set()

        # 预警特权拉取（隐藏但有预警时按预警频率轮询）
        self._alert_poll_intervals: Dict[str, int] = {}
        self._alert_last_poll_time: Dict[str, float] = {}
        self._default_alert_poll_interval = 20

        # 回调
        self.on_settings_changed = on_settings_changed
        self.on_visibility_changed = on_visibility_changed
        self.on_target_visibility_changed = on_target_visibility_changed

        # 跨线程数据队列
        self._quote_queue: queue.Queue[List[GoldQuote]] = queue.Queue()

        # 刷新定时器
        self.fetch_timer = QTimer()
        self.fetch_timer.setInterval(self.update_interval * 1000)
        self.fetch_timer.timeout.connect(self.refresh_quotes)

        # 窗口手动调整后的防抖保存（5秒）
        self._sync_delay_ms = 5000
        self._pending_sync_keys: set[str] = set()
        self._sync_timer = QTimer()
        self._sync_timer.setSingleShot(True)
        self._sync_timer.timeout.connect(self._flush_synced_settings)

    def load_settings(self, settings: Dict):
        """从配置加载设置"""
        gold_config = settings.get("gold_window", {})

        targets = gold_config.get("targets") or [target.copy() for target in DEFAULT_GOLD_TARGETS]
        normalized_targets: List[Dict[str, Any]] = []
        for target in targets:
            key = target.get("key", "")
            if not key:
                continue
            normalized_targets.append(
                {
                    "key": key,
                    "name": target.get("name", key),
                    "enabled": target.get("enabled", True),
                }
            )
        self.targets = normalized_targets or [target.copy() for target in DEFAULT_GOLD_TARGETS]

        self.code_settings = gold_config.get("code_settings", {})

        ws = gold_config.get("settings", {})
        self.font_size = ws.get("font_size", 14)
        self.background_alpha = ws.get("background_alpha", 220)
        self.text_alpha = ws.get("text_alpha", 255)
        self.show_name = False
        self.show_code = ws.get("show_code", ws.get("show_name", False))
        self.show_column_header = ws.get("show_column_header", False)
        self.always_on_top = ws.get("always_on_top", True)
        self.column_widths = ws.get("column_widths", [140, 140, 140])
        self.row_height = ws.get("row_height", 44)
        self.window_size = tuple(ws.get("window_size", [620, 140]))
        self.update_interval = max(1, int(ws.get("update_interval", 1)))

        self.fetch_timer.setInterval(self.update_interval * 1000)

    def save_settings(self) -> Dict:
        """保存设置"""
        return {
            "targets": self.targets,
            "code_settings": self.code_settings,
            "settings": {
                "font_size": self.font_size,
                "background_alpha": self.background_alpha,
                "text_alpha": self.text_alpha,
                "show_name": False,
                "show_code": self.show_code,
                "show_column_header": self.show_column_header,
                "always_on_top": self.always_on_top,
                "column_widths": self.column_widths,
                "row_height": self.row_height,
                "window_size": list(self.window_size),
                "update_interval": self.update_interval,
            },
        }

    def start(self):
        """启动行情刷新"""
        if self.executor is None:
            self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="gold-fetch")
        self._ensure_windows(initial=True)
        if self.enabled_keys:
            self.refresh_quotes(force=True)
        self.fetch_timer.start()

    def stop(self):
        """停止行情刷新"""
        self.fetch_timer.stop()
        self._force_refresh_requested = False
        if self.executor:
            self.executor.shutdown(wait=False, cancel_futures=True)
            self.executor = None

    @property
    def enabled_keys(self) -> List[str]:
        return [t.get("key") for t in self.targets if t.get("enabled", False) and t.get("key")]

    @property
    def target_names(self) -> Dict[str, str]:
        return {t.get("key", ""): t.get("name", t.get("key", "")) for t in self.targets if t.get("key")}

    def set_targets(self, targets: List[Dict[str, Any]]) -> None:
        self.targets = [
            {
                "key": t.get("key", ""),
                "name": t.get("name", t.get("key", "")),
                "enabled": t.get("enabled", True),
            }
            for t in targets
            if t.get("key")
        ]
        self._ensure_windows(initial=True)

    def show_windows(self):
        """显示所有窗口"""
        self._visible = True
        self._ensure_windows(initial=True)
        for key in self.enabled_keys:
            window = self.windows.get(key)
            if window and self._can_show_key(key):
                window.show()
                window.raise_()
        self._notify_target_visibility_changed()
        self.refresh_quotes(force=True)

    def show_window_for_key(self, key: str) -> None:
        """显示单个标的窗口（用于定时边界切换）"""
        self.set_target_visible_state(key, True, persist=True)

    def hide_window_for_key(self, key: str) -> None:
        """隐藏单个标的窗口（用于定时边界切换）"""
        self.set_target_visible_state(key, False, persist=True)

    def get_target_visibility_map(self) -> Dict[str, bool]:
        """返回各标的当前窗口真实可见状态"""
        result: Dict[str, bool] = {}
        for target in self.targets:
            key = target.get("key", "")
            if not key:
                continue
            window = self.windows.get(key)
            result[key] = bool(window and window.isVisible())
        return result

    def get_visible_keys(self) -> List[str]:
        return [k for k, v in self.get_target_visibility_map().items() if v]

    def set_alert_polling_config(self, gold_tasks: List[Dict[str, Any]], default_interval: int = 20) -> None:
        """配置隐藏窗口下的预警特权拉取频率（秒）"""
        self._default_alert_poll_interval = max(1, int(default_interval or 20))
        intervals: Dict[str, int] = {}
        for task in gold_tasks or []:
            if not task.get("enabled", False):
                continue
            key = str(task.get("target", "")).strip()
            if not key:
                continue
            # 兼容现有字段：frequency（分钟）优先；否则走默认扫描间隔（秒）
            try:
                freq_min = int(task.get("frequency", 0) or 0)
            except Exception:
                freq_min = 0
            poll_sec = self._default_alert_poll_interval if freq_min <= 0 else max(1, freq_min * 60)
            prev = intervals.get(key)
            if prev is None or poll_sec < prev:
                intervals[key] = poll_sec
        self._alert_poll_intervals = intervals
        self._alert_last_poll_time = {
            key: ts for key, ts in self._alert_last_poll_time.items() if key in intervals
        }

    def set_target_visible_state(self, key: str, visible: bool, persist: bool = True) -> None:
        """设置单个标的可见状态，并与配置开关保持一致"""
        if not key:
            return

        changed = False
        found = False
        for target in self.targets:
            if target.get("key") != key:
                continue
            found = True
            old_enabled = bool(target.get("enabled", False))
            if old_enabled != visible:
                target["enabled"] = visible
                changed = True
            break
        if not found:
            return

        if visible:
            self._visible = True
            self._ensure_windows(initial=True)
            window = self.windows.get(key)
            if window and not window.isVisible():
                window.show()
                window.raise_()
            self.refresh_quotes(force=True)
        else:
            window = self.windows.get(key)
            if window and window.isVisible():
                window.hide()
            if not self.enabled_keys:
                self._visible = False

        if changed and persist:
            self._notify_settings_changed()
        self._notify_target_visibility_changed()
        if not self.enabled_keys and self.on_visibility_changed:
            self.on_visibility_changed(False)

    def disable_target_and_hide(self, key: Optional[str]) -> None:
        """禁用并关闭单个黄金标的（用于右键“关闭当前黄金标的”）"""
        if key:
            self.set_target_visible_state(key, False, persist=True)

    def hide_windows(self):
        """隐藏所有窗口"""
        self._visible = False
        for window in self.windows.values():
            window.hide()
        self._notify_target_visibility_changed()

    def close_all_windows(self):
        """关闭所有窗口"""
        self._visible = False
        self.capture_window_states(notify=False)
        for window in self.windows.values():
            window.close()
        self.windows.clear()

    def disable_all_targets_and_notify(self):
        """禁用全部黄金标的并关闭窗口（用于“关闭所有黄金标的”）"""
        changed = False
        for target in self.targets:
            if target.get("enabled", False):
                target["enabled"] = False
                changed = True

        self.hide_windows()

        if changed:
            self._notify_settings_changed()
        self._notify_target_visibility_changed()
        if self.on_visibility_changed:
            self.on_visibility_changed(False)

    def is_visible(self) -> bool:
        return self._visible

    def get_column_headers(self) -> List[str]:
        """黄金窗口列头定义"""
        return ["代码", "最新价", "涨跌幅"]

    def apply_schedule_visibility(self, visible_keys: Optional[set[str]]) -> None:
        """兼容保留：不再设置持续可见性限制。"""
        return

    def _window_config(self) -> Dict[str, Any]:
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
            "show_name": False,
            "show_code": self.show_code,
            "show_column_header": self.show_column_header,
            "column_widths": self.column_widths,
            "row_height": self.row_height,
            "window_size": self.window_size,
        }

    def _ensure_windows(self, initial: bool = False):
        config = self._window_config()
        names = self.target_names

        for key in names.keys():
            if key not in self.windows:
                window = StockFloatWindow(self, key)
                code_cfg = self.code_settings.get(key, {})
                window._always_on_top = code_cfg.get("always_on_top", self.always_on_top)
                window.apply_settings(config, initial=initial)
                window.update_quote(self.quotes.get(key))

                window._initializing = True
                self._restore_window_state(window, code_cfg)
                window._initializing = False

                if self._can_show_key(key):
                    window.show()
                else:
                    window.hide()
                self.windows[key] = window

        valid_keys = set(names.keys())
        for key in list(self.windows.keys()):
            if key not in valid_keys:
                self.windows[key].close()
                del self.windows[key]

    def _apply_settings_to_all(self):
        config = self._window_config()
        for window in self.windows.values():
            window.apply_settings(config, initial=False)

    def _notify_settings_changed(self):
        if self.on_settings_changed:
            self.on_settings_changed()

    def _notify_target_visibility_changed(self):
        if self.on_target_visibility_changed:
            self.on_target_visibility_changed(self.get_target_visibility_map())

    def _can_show_key(self, key: str) -> bool:
        if not self._visible:
            return False
        if key not in self.enabled_keys:
            return False
        return True

    def populate_context_menu(self, menu: QMenu, anchor: QWidget, code: Optional[str]) -> None:
        """填充右键菜单（黄金窗口精简版）"""
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

        close_current_action = menu.addAction("关闭当前黄金标的")
        if code:
            close_current_action.triggered.connect(lambda: self.disable_target_and_hide(code))
        else:
            close_current_action.setEnabled(False)

        close_action = menu.addAction("关闭所有黄金标的")
        close_action.triggered.connect(self.disable_all_targets_and_notify)

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
            self.update_interval = max(1, value)
            self.fetch_timer.setInterval(self.update_interval * 1000)
            self._notify_settings_changed()

    def set_always_on_top(self, value: bool) -> None:
        self.always_on_top = value
        for key, window in self.windows.items():
            window._always_on_top = value
            if key not in self.code_settings:
                self.code_settings[key] = {}
            self.code_settings[key]["always_on_top"] = value
        self._apply_settings_to_all()
        self._notify_settings_changed()

    def set_window_always_on_top(self, code: Optional[str], value: bool) -> None:
        if not code:
            return
        if code not in self.code_settings:
            self.code_settings[code] = {}
        self.code_settings[code]["always_on_top"] = value
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
        self._sync_window_state(window)
        self._pending_sync_keys.add(window.code)
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
        self._pending_sync_keys.clear()

    def _flush_synced_settings(self) -> None:
        if not self._pending_sync_keys:
            return
        self._pending_sync_keys.clear()
        self._notify_settings_changed()

    def _sync_window_state(self, window: StockFloatWindow) -> None:
        self.column_widths = window.get_column_widths()
        self.row_height = window.get_row_height()
        self.window_size = window.get_window_size()

        key = window.code
        if key not in self.code_settings:
            self.code_settings[key] = {}
        self.code_settings[key]["window_pos"] = [window.x(), window.y()]
        self.code_settings[key]["window_size"] = list(window.get_window_size())
        self.code_settings[key]["column_widths"] = window.get_column_widths()
        self.code_settings[key]["visible"] = bool(window.isVisible())

    def _restore_window_state(self, window: StockFloatWindow, code_cfg: Dict[str, Any]) -> None:
        size = code_cfg.get("window_size")
        if isinstance(size, (list, tuple)) and len(size) == 2:
            try:
                window.resize(max(int(size[0]), 1), max(int(size[1]), 1))
            except Exception:
                pass

        if "column_widths" in code_cfg:
            for i, w in enumerate(code_cfg.get("column_widths", [])[: window.table.columnCount()]):
                try:
                    window.table.setColumnWidth(i, int(w))
                except Exception:
                    continue

        pos = code_cfg.get("window_pos")
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
        visible_keys = set(self.get_visible_keys())
        now = time.time()

        alert_keys: set[str] = set()
        for key, interval in self._alert_poll_intervals.items():
            if key in visible_keys:
                continue
            last = self._alert_last_poll_time.get(key, 0.0)
            if force or (now - last) >= max(1, int(interval)):
                alert_keys.add(key)

        request_keys = visible_keys | alert_keys
        if not request_keys:
            return
        if self.fetch_in_progress:
            if force:
                self._force_refresh_requested = True
            return

        self.fetch_in_progress = True
        self._force_refresh_requested = False
        self._last_requested_keys = set(request_keys)
        for key in alert_keys:
            self._alert_last_poll_time[key] = now
        if self.executor is None:
            self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="gold-fetch")
        self.executor.submit(self._fetch_worker, list(request_keys))

    def _fetch_worker(self, enabled_keys: List[str]) -> None:
        try:
            quotes = self.fetcher.fetch(self.target_names, enabled_keys)
            self._quote_queue.put(quotes)
            app = QApplication.instance()
            if app is not None:
                app.postEvent(app, _GoldUpdateEvent())
        except Exception as e:
            logger.warning("获取黄金行情失败: %s", e)
        finally:
            self.fetch_in_progress = False
            if self._force_refresh_requested:
                self.refresh_quotes(force=True)

    def on_quotes_received(self) -> None:
        while not self._quote_queue.empty():
            try:
                quotes = self._quote_queue.get_nowait()
            except queue.Empty:
                break

            for quote in quotes:
                self.quotes[quote.key] = quote
                if quote.key in self._last_requested_keys:
                    window = self.windows.get(quote.key)
                    if window:
                        window.update_quote(quote)

            # 刷新阶段只做“强制隐藏”，不自动拉起窗口；
            # 这样右键“关闭当前黄金标的”后不会被下一次刷新立即重新显示。
            for key, window in self.windows.items():
                if not self._can_show_key(key):
                    if window.isVisible():
                        window.hide()


class _GoldUpdateEvent(QEvent):
    EVENT_TYPE = QEvent.Type(QEvent.registerEventType())

    def __init__(self):
        super().__init__(self.EVENT_TYPE)
