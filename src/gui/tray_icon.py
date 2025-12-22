# gui/tray_icon.py - 系统托盘图标
"""系统托盘图标模块"""

import logging
from typing import Callable, Optional

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtWidgets import (
    QApplication,
    QMenu,
    QSystemTrayIcon,
    QMessageBox,
    QInputDialog,
)

from .dialogs import AlertConfigDialog, TimeScheduleDialog, AddStockDialog
from .main_window import MainWindow
from ..scheduler import TradingScheduler

logger = logging.getLogger(__name__)


class SystemTrayIcon(QSystemTrayIcon):
    """系统托盘图标"""
    
    def __init__(
        self,
        app: QApplication,
        quote_manager,
        alert_engine,
        settings_manager,
        parent=None
    ):
        super().__init__(parent)
        
        self.app = app
        self.quote_manager = quote_manager
        self.alert_engine = alert_engine
        self.settings_manager = settings_manager
        self.scheduler = TradingScheduler()
        
        # 主窗口（延迟创建）
        self.main_window: Optional[MainWindow] = None
        
        # 创建图标
        self._create_icon()
        
        # 创建菜单
        self._create_menu()
        
        # 时间段检查定时器
        self.schedule_timer = QTimer()
        self.schedule_timer.setInterval(60000)  # 每分钟检查一次
        self.schedule_timer.timeout.connect(self._check_time_schedule)
        self.schedule_timer.start()
        
        # 状态
        self._manually_shown = False  # 是否手动打开了窗口
        self._last_period_state = None  # 上一次的时间段状态 (True=在时间段内, False=不在)
        
        # 初始化窗口显示状态
        if self.settings_manager.get_time_schedule_enabled():
            self._check_time_schedule()
        elif self.settings_manager.get_quote_enabled():
            self.quote_manager.show_windows()
        
        # 显示
        self.show()

    def _create_icon(self):
        """创建托盘图标"""
        from ..config import ICON_PATH
        
        # 1. 尝试从本地文件加载
        if ICON_PATH.exists():
            icon = QIcon(str(ICON_PATH))
            if not icon.isNull():
                self.setIcon(icon)
                self.setToolTip("AShareTools - A股行情监控")
                self.activated.connect(self._on_activated)
                return

        # 2. 尝试使用内置图标
        icon = QIcon.fromTheme("stock")
        
        # 3. 如果都没有，则绘制并保存
        if icon.isNull():
            # 创建一个简单的彩色图标
            from PyQt6.QtGui import QPixmap, QPainter, QColor
            pixmap = QPixmap(32, 32)
            pixmap.fill(QColor(0, 0, 0, 0))
            painter = QPainter(pixmap)
            painter.setBrush(QColor(217, 48, 80))  # 红色
            painter.setPen(QColor(217, 48, 80))
            painter.drawRect(4, 4, 10, 24)
            painter.setBrush(QColor(0, 158, 96))  # 绿色
            painter.setPen(QColor(0, 158, 96))
            painter.drawRect(18, 12, 10, 16)
            painter.end()
            
            # 保存到本地，供下次使用
            try:
                pixmap.save(str(ICON_PATH), "PNG")
            except Exception as e:
                logger.warning(f"保存图标失败: {e}")
                
            icon = QIcon(pixmap)
        
        self.setIcon(icon)
        self.setToolTip("AShareTools - A股行情监控")
        
        # 双击显示/隐藏窗口
        self.activated.connect(self._on_activated)

    def _create_menu(self):
        """创建右键菜单（精简结构）"""
        menu = QMenu()
        
        # ===== 显示行情窗口 =====
        self.show_quote_action = QAction("显示行情窗口", menu)
        self.show_quote_action.setCheckable(True)
        self.show_quote_action.setChecked(self.settings_manager.get_quote_enabled())
        self.show_quote_action.triggered.connect(self._toggle_quote_window)
        menu.addAction(self.show_quote_action)
        
        # ===== 定时显示 =====
        self.time_schedule_action = QAction("定时显示", menu)
        self.time_schedule_action.setCheckable(True)
        self.time_schedule_action.setChecked(self.settings_manager.get_time_schedule_enabled())
        self.time_schedule_action.triggered.connect(self._toggle_time_schedule)
        menu.addAction(self.time_schedule_action)
        
        menu.addSeparator()
        
        # ===== 启用预警 =====
        self.enable_alert_action = QAction("启用预警", menu)
        self.enable_alert_action.setCheckable(True)
        self.enable_alert_action.setChecked(self.settings_manager.get_alert_enabled())
        self.enable_alert_action.triggered.connect(self._toggle_alert)
        menu.addAction(self.enable_alert_action)
        
        menu.addSeparator()
        
        # ===== 系统配置 =====
        config_action = QAction("系统配置", menu)
        config_action.triggered.connect(self._show_main_window)
        menu.addAction(config_action)
        
        menu.addSeparator()
        
        # ===== 退出 =====
        exit_action = QAction("退出", menu)
        exit_action.triggered.connect(self._quit)
        menu.addAction(exit_action)
        
        self.setContextMenu(menu)

    def _on_activated(self, reason):
        """托盘图标被激活"""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_main_window()

    def _show_main_window(self):
        """显示主窗口"""
        if self.main_window is None:
            self.main_window = MainWindow(
                self.quote_manager,
                self.alert_engine,
                self.settings_manager
            )
            # 确保主窗口使用托盘图标
            self.main_window.setWindowIcon(self.icon())
            # 设置回调，当设置应用后同步托盘菜单状态
            self.main_window.on_settings_applied = self._sync_menu_from_settings
        self.main_window.show()
        self.main_window.raise_()
        self.main_window.activateWindow()

    def _sync_menu_from_settings(self):
        """从设置同步菜单状态"""
        self.show_quote_action.setChecked(self.settings_manager.get_quote_enabled())
        self.enable_alert_action.setChecked(self.settings_manager.get_alert_enabled())
        
        schedule_enabled = self.settings_manager.get_time_schedule_enabled()
        self.time_schedule_action.setChecked(schedule_enabled)
        
        if schedule_enabled:
            # 如果通过设置启用了定时显示，立即检查
            self._check_time_schedule()

    def _toggle_quote_window(self, checked=None):
        """切换行情窗口显示"""
        if checked is None:
            checked = not self.quote_manager.is_visible()
        
        if checked:
            self.quote_manager.show_windows()
            self._manually_shown = True
        else:
            self.quote_manager.hide_windows()
            self._manually_shown = False
        
        self.show_quote_action.setChecked(checked)
        self.settings_manager.set_quote_enabled(checked)

    def _add_quote_stock(self):
        """添加行情股票"""
        dialog = AddStockDialog()
        if dialog.exec():
            code = dialog.get_code()
            if code:
                self.quote_manager.add_code(code)

    def _set_quote_option(self, option: str, value: bool):
        """设置行情窗口选项"""
        if option == 'show_name':
            self.quote_manager.set_show_name(value)
        elif option == 'show_code':
            self.quote_manager.set_show_code(value)
        elif option == 'show_column_header':
            self.quote_manager.set_show_column_header(value)
        elif option == 'always_on_top':
            self.quote_manager.set_always_on_top(value)

    def _prompt_font_size(self):
        """设置字体大小"""
        value, ok = QInputDialog.getInt(
            None, "字体大小", "字号:", 
            self.quote_manager.font_size, 8, 48, 1
        )
        if ok:
            self.quote_manager.font_size = value
            self.quote_manager._apply_settings_to_all()
            self.quote_manager._notify_settings_changed()

    def _prompt_bg_alpha(self):
        """设置背景透明度"""
        value, ok = QInputDialog.getInt(
            None, "背景透明度", "0-255:", 
            self.quote_manager.background_alpha, 0, 255, 1
        )
        if ok:
            self.quote_manager.background_alpha = value
            self.quote_manager._apply_settings_to_all()
            self.quote_manager._notify_settings_changed()

    def _prompt_text_alpha(self):
        """设置文字透明度"""
        value, ok = QInputDialog.getInt(
            None, "文字透明度", "0-255:", 
            self.quote_manager.text_alpha, 0, 255, 1
        )
        if ok:
            self.quote_manager.text_alpha = value
            self.quote_manager._apply_settings_to_all()
            self.quote_manager._notify_settings_changed()

    def _prompt_refresh_interval(self):
        """设置刷新频率"""
        value, ok = QInputDialog.getInt(
            None, "刷新频率", "秒:", 
            self.quote_manager.update_interval, 1, 3600, 1
        )
        if ok:
            self.quote_manager.update_interval = value
            self.quote_manager.fetch_timer.setInterval(value * 1000)
            self.quote_manager._notify_settings_changed()

    def _toggle_time_schedule(self, checked):
        """切换定时显示"""
        self.settings_manager.set_time_schedule_enabled(checked)
        if checked:
            # 启用定时显示时，重置状态，并立即检查
            self._last_period_state = None
            self._check_time_schedule()

    def _show_time_schedule_dialog(self):
        """显示时间段设置对话框"""
        periods = self.settings_manager.get_time_schedule_periods()
        dialog = TimeScheduleDialog(periods=periods)
        if dialog.exec():
            new_periods = dialog.get_periods()
            self.settings_manager.set_time_schedule_periods(new_periods)

    def _check_time_schedule(self):
        """检查时间段"""
        if not self.settings_manager.get_time_schedule_enabled():
            self._last_period_state = None
            return
        
        periods = self.settings_manager.get_time_schedule_periods()
        in_period = self.scheduler.is_in_time_period(periods)
        
        # 状态发生改变时触发 (边缘触发)
        if self._last_period_state != in_period:
            if in_period:
                # 进入时间段 -> 打开窗口
                self.quote_manager.show_windows()
                self.show_quote_action.setChecked(True)
                # 同步更新设置窗口状态
                if self.main_window and self.main_window.isVisible():
                    self.main_window.enable_quote_check.setChecked(True)
            else:
                # 离开时间段 -> 关闭窗口
                self.quote_manager.hide_windows()
                self.show_quote_action.setChecked(False)
                # 同步更新设置窗口状态
                if self.main_window and self.main_window.isVisible():
                    self.main_window.enable_quote_check.setChecked(False)
            
            # 更新状态
            self._last_period_state = in_period

    def _toggle_alert(self, checked):
        """切换预警功能"""
        if checked:
            tasks = self.settings_manager.get_alert_tasks()
            scan_interval = self.settings_manager.get_alert_scan_interval()
            self.alert_engine.update_tasks(tasks, scan_interval)
            
            # 更新钉钉配置
            dingtalk = self.settings_manager.get_dingtalk_config()
            if self.alert_engine.notifier:
                self.alert_engine.notifier.update_config(
                    dingtalk.get('webhook', ''),
                    dingtalk.get('secret', '')
                )
            
            self.alert_engine.start()
        else:
            self.alert_engine.stop()
        
        self.settings_manager.set_alert_enabled(checked)

    def _show_alert_config_dialog(self):
        """显示预警配置对话框"""
        tasks = self.settings_manager.get_alert_tasks()
        scan_interval = self.settings_manager.get_alert_scan_interval()
        strategies = self.alert_engine.get_available_strategies()
        dingtalk = self.settings_manager.get_dingtalk_config()
        
        dialog = AlertConfigDialog(
            tasks=tasks,
            available_strategies=strategies,
            scan_interval=scan_interval,
            dingtalk_config=dingtalk
        )
        
        if dialog.exec():
            new_tasks = dialog.get_tasks()
            new_interval = dialog.get_scan_interval()
            new_dingtalk = dialog.get_dingtalk_config()
            
            self.settings_manager.set_alert_tasks(new_tasks)
            self.settings_manager.set_alert_scan_interval(new_interval)
            self.settings_manager.set_dingtalk_config(new_dingtalk)
            
            # 如果预警已启用，更新配置
            if self.alert_engine.is_running():
                self.alert_engine.update_tasks(new_tasks, new_interval)
                if self.alert_engine.notifier:
                    self.alert_engine.notifier.update_config(
                        new_dingtalk.get('webhook', ''),
                        new_dingtalk.get('secret', '')
                    )

    def _reload_strategies(self):
        """重载策略"""
        success = self.alert_engine.reload_strategies()
        if success:
            self.showMessage(
                "策略重载",
                "策略文件重载成功！",
                QSystemTrayIcon.MessageIcon.Information,
                2000
            )
            # 如果设置窗口已打开，刷新其策略列表
            if self.main_window and self.main_window.isVisible():
                self.main_window._reload_strategies_ui_only()
        else:
            self.showMessage(
                "策略重载",
                "策略文件重载失败，请检查文件格式。",
                QSystemTrayIcon.MessageIcon.Warning,
                3000
            )

    def _quit(self):
        """退出程序"""
        self.quote_manager.stop()
        self.alert_engine.stop()
        self.settings_manager.save()
        if self.main_window:
            self.main_window.close()
        self.app.quit()

    def update_menu_state(self):
        """更新菜单状态（供外部调用）"""
        self.show_quote_action.setChecked(self.quote_manager.is_visible())
        self.time_schedule_action.setChecked(self.settings_manager.get_time_schedule_enabled())
        self.enable_alert_action.setChecked(self.settings_manager.get_alert_enabled())
