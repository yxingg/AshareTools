# main.py - 程序主入口
"""
AShareTools - A股行情监控与预警工具
主程序入口
"""

from __future__ import annotations

import sys
import ctypes
from pathlib import Path

# 确保项目根目录在 sys.path 中
def _setup_path():
    current_dir = Path(__file__).resolve().parent
    parent_dir = current_dir.parent
    if str(parent_dir) not in sys.path:
        sys.path.insert(0, str(parent_dir))
    if str(current_dir) not in sys.path:
        sys.path.insert(0, str(current_dir))

_setup_path()

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QEvent

from src.config import STOCK_CACHE_FILE
from src.logger import setup_logger
from src.settings_manager import SettingsManager
from src.alert_engine import AlertEngine
from src.gui.quote_manager import QuoteWindowManager, _QuoteUpdateEvent
from src.gui.gold_manager import GoldWindowManager, _GoldUpdateEvent
from src.gui.tray_icon import SystemTrayIcon
from src.data_fetcher import StockNameManager


def _configure_logging() -> tuple:
    """配置日志"""
    return setup_logger("AShareTools")


class AShareToolsApp(QApplication):
    """主应用程序类"""
    
    def __init__(self, argv):
        super().__init__(argv)
        
        # 应用 Win11 风格
        from src.gui.win11_style import apply_win11_style
        apply_win11_style(self)
        
        # 配置日志
        self.logger, self.notifier = _configure_logging()
        self.logger.info("AShareTools 启动中...")
        
        # 全局异常处理
        sys.excepthook = self._log_excepthook
        
        # 配置管理器
        self.settings_manager = SettingsManager()
        
        # 初始化全局股票信息缓存管理器
        quote_stocks = self.settings_manager.get_quote_stocks()
        alert_tasks = self.settings_manager.get_alert_tasks()
        alert_symbols = [
            t.get('symbol', '')
            for t in alert_tasks
            if t.get('symbol') and bool(t.get('enabled', True))
        ]
        all_symbols = list(set(quote_stocks + alert_symbols))
        
        self.stock_name_manager = StockNameManager(
            self.logger,
            str(STOCK_CACHE_FILE),
            target_symbols=all_symbols
        )
        
        # 行情窗口管理器
        self.quote_manager = QuoteWindowManager(
            on_settings_changed=self._on_quote_settings_changed,
            on_visibility_changed=self._on_quote_visibility_changed
        )
        self.quote_manager.load_settings(self.settings_manager.get_all())
        if self.settings_manager.get_alert_enabled():
            self.quote_manager.set_alert_polling_config(
                self.settings_manager.get_alert_tasks(),
                self.settings_manager.get_alert_scan_interval(),
            )
        else:
            self.quote_manager.set_alert_polling_config([], self.settings_manager.get_alert_scan_interval())

        # 黄金行情窗口管理器
        self.gold_manager = GoldWindowManager(
            on_settings_changed=self._on_gold_settings_changed,
            on_visibility_changed=self._on_gold_visibility_changed,
            on_target_visibility_changed=self._on_gold_target_visibility_changed,
        )
        self.gold_manager.load_settings(self.settings_manager.get_all())
        self.gold_manager.set_alert_polling_config(
            self.settings_manager.get_gold_alert_tasks(),
            self.settings_manager.get_gold_alert_scan_interval(),
        )
        
        # 预警引擎
        self.alert_engine = AlertEngine(
            notifier=self.notifier,
            on_signal=self._on_alert_signal
        )
        
        # 系统托盘
        self.tray_icon = SystemTrayIcon(
            app=self,
            quote_manager=self.quote_manager,
            gold_manager=self.gold_manager,
            alert_engine=self.alert_engine,
            settings_manager=self.settings_manager
        )
        
        # 设置应用程序图标（与托盘图标一致）
        self.setWindowIcon(self.tray_icon.icon())
        
        # 启动行情窗口
        if self.settings_manager.get_quote_enabled():
            self.quote_manager.start()
            self.quote_manager.show_windows()
        else:
            self.quote_manager.start()
            self.quote_manager.hide_windows()

        # 启动黄金行情窗口
        self.gold_manager.start()
        if self.settings_manager.get_gold_enabled():
            self.gold_manager.show_windows()
            self.gold_manager.refresh_quotes(force=True)
        else:
            self.gold_manager.hide_windows()

        # 启动后立即执行一次运行时调度（股票+黄金）
        self.tray_icon._check_time_schedule()
        
        # 启动预警（如果已启用）
        if self.settings_manager.get_alert_enabled():
            tasks = self.settings_manager.get_alert_tasks()
            scan_interval = self.settings_manager.get_alert_scan_interval()
            gold_tasks = self.settings_manager.get_gold_alert_tasks()
            gold_scan_interval = self.settings_manager.get_gold_alert_scan_interval()
            dingtalk = self.settings_manager.get_dingtalk_config()
            
            self.alert_engine.update_tasks(
                tasks,
                scan_interval,
                gold_tasks=gold_tasks,
                gold_scan_interval=gold_scan_interval,
            )
            self.notifier.update_config(
                dingtalk.get('webhook', ''),
                dingtalk.get('secret', '')
            )
            self.alert_engine.start()
        else:
            # 即使未启用，也加载任务配置，以便后续启用时直接使用
            tasks = self.settings_manager.get_alert_tasks()
            scan_interval = self.settings_manager.get_alert_scan_interval()
            gold_tasks = self.settings_manager.get_gold_alert_tasks()
            gold_scan_interval = self.settings_manager.get_gold_alert_scan_interval()
            self.alert_engine.update_tasks(
                tasks,
                scan_interval,
                gold_tasks=gold_tasks,
                gold_scan_interval=gold_scan_interval,
            )
            # 确保不启动
            if self.alert_engine.is_running():
                self.alert_engine.stop()
        
        # 退出时保存配置
        self.aboutToQuit.connect(self._on_quit)
        
        self.logger.info("AShareTools 启动完成")

    def _log_excepthook(self, exc_type, exc_value, exc_traceback):
        """记录未捕获的异常"""
        self.logger.error(
            "未捕获的异常",
            exc_info=(exc_type, exc_value, exc_traceback)
        )

    def _on_quote_settings_changed(self):
        """行情设置改变回调"""
        config = self.quote_manager.save_settings()
        self.settings_manager.update_quote_window_settings(config)

    def _on_quote_visibility_changed(self, visible: bool):
        """行情窗口可见性变化回调"""
        if hasattr(self, 'tray_icon') and self.tray_icon:
            self.tray_icon._sync_quote_state(bool(visible))
        else:
            self.settings_manager.set_quote_enabled(bool(visible))

    def _on_gold_settings_changed(self):
        """黄金设置改变回调"""
        config = self.gold_manager.save_settings()
        self.settings_manager.update_gold_window_settings(config)
        self.settings_manager.set_gold_enabled(bool(self.gold_manager.enabled_keys))
        self.gold_manager.set_alert_polling_config(
            self.settings_manager.get_gold_alert_tasks(),
            self.settings_manager.get_gold_alert_scan_interval(),
        )

    def _on_gold_target_visibility_changed(self, visible_map: dict):
        """黄金标的可见状态变化回调"""
        if hasattr(self, 'tray_icon') and self.tray_icon:
            self.tray_icon._sync_gold_switches_if_open()

    def _on_gold_visibility_changed(self, visible: bool):
        """黄金窗口可见性变化回调"""
        if not visible:
            self.settings_manager.set_gold_enabled(False)

    def _on_alert_signal(self, symbol: str, strategy: str, signal: str, message: str):
        """预警信号回调"""
        # 显示托盘通知
        self.tray_icon.showMessage(
            "交易提醒",
            message,
            self.tray_icon.MessageIcon.Information,
            5000
        )

    def _on_quit(self):
        """退出时的清理"""
        self.logger.info("AShareTools 正在退出...")
        try:
            # 退出前强制落盘窗口状态（位置/大小/列宽/可见性）
            self.quote_manager.flush_pending_settings()
            self.gold_manager.flush_pending_settings()
            self.settings_manager.set_quote_enabled(bool(self.quote_manager.is_visible()))
            self.settings_manager.set_gold_enabled(bool(self.gold_manager.is_visible()))
        except Exception as e:
            self.logger.error(f"保存窗口状态失败: {e}")

        try:
            # 先停止定时刷新与后台抓取线程
            self.quote_manager.stop()
        except Exception as e:
            self.logger.error(f"停止行情模块失败: {e}")

        try:
            # 停止黄金行情刷新与后台抓取线程
            self.gold_manager.stop()
        except Exception as e:
            self.logger.error(f"停止黄金行情模块失败: {e}")

        try:
            # 再停止预警循环线程
            self.alert_engine.stop()
        except Exception as e:
            self.logger.error(f"停止预警模块失败: {e}")

        try:
            # 隐藏托盘图标，避免残留
            self.tray_icon.hide()
        except Exception as e:
            self.logger.warning(f"隐藏托盘图标失败: {e}")

        try:
            self.settings_manager.save()
        except Exception as e:
            self.logger.error(f"退出清理失败: {e}")

    def event(self, event: QEvent) -> bool:
        """处理自定义事件"""
        if event.type() == _QuoteUpdateEvent.EVENT_TYPE:
            self.quote_manager.on_quotes_received()
            return True
        if event.type() == _GoldUpdateEvent.EVENT_TYPE:
            self.gold_manager.on_quotes_received()
            return True
        return super().event(event)


def main():
    """主函数"""
    # 单实例检测
    try:
        kernel32 = ctypes.windll.kernel32
        mutex = kernel32.CreateMutexW(None, False, "AShareTools_Instance_Mutex_v1")
        if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            # 如果已有实例运行，弹出提示（需要先创建 QApplication 才能弹窗）
            app = QApplication(sys.argv)
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(None, "提示", "程序已经在运行中！\n请检查系统托盘图标。")
            return
    except Exception as e:
        print(f"单实例检测失败: {e}")

    # 设置 AppUserModelID 以便在任务栏显示正确图标
    try:
        myappid = 'asharetools.monitor.app.v1'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass

    app = AShareToolsApp(sys.argv)
    
    # 防止没有窗口时程序退出
    app.setQuitOnLastWindowClosed(False)
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
