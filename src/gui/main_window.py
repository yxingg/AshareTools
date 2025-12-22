# gui/main_window.py - 主界面窗口
"""主界面窗口 - 提供所有配置功能"""

from typing import Dict, List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QGroupBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QCheckBox,
    QSpinBox,
    QSlider,
    QComboBox,
    QListWidget,
    QListWidgetItem,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QTimeEdit,
    QMessageBox,
    QInputDialog,
    QSizePolicy,
)
from PyQt6.QtCore import QTime
from PyQt6.QtGui import QCloseEvent

from ..utils import get_market_short_name, get_security_type
from ..data_fetcher import StockNameManager


class MainWindow(QMainWindow):
    """主配置窗口"""
    
    def __init__(self, quote_manager, alert_engine, settings_manager, parent=None):
        super().__init__(parent)
        self.quote_manager = quote_manager
        self.alert_engine = alert_engine
        self.settings_manager = settings_manager
        self.on_settings_applied = None  # 设置应用后的回调
        
        self.setWindowTitle("AShareTools - 设置")
        self.setMinimumSize(350, 280)  # 最小尺寸缩小到一半
        self.resize(600, 480)  # 默认尺寸稍小
        
        # 创建中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        
        # 创建选项卡
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # 行情窗口选项卡
        self._create_quote_tab()
        
        # 行情预警选项卡
        self._create_alert_tab()
        
        # 底部按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        apply_btn = QPushButton("应用")
        apply_btn.setFixedWidth(70)
        apply_btn.clicked.connect(self._apply_settings)
        btn_layout.addWidget(apply_btn)
        
        close_btn = QPushButton("关闭")
        close_btn.setFixedWidth(70)
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
        
        # 加载当前设置
        self._load_current_settings()

    def _create_quote_tab(self):
        """创建行情窗口选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)
        
        # 总开关
        enable_layout = QHBoxLayout()
        enable_layout.setSpacing(8)
        self.enable_quote_check = QCheckBox("启用行情窗口")
        self.enable_quote_check.setStyleSheet("font-weight: bold; font-size: 12px;")
        enable_layout.addWidget(self.enable_quote_check)
        enable_layout.addStretch()
        layout.addLayout(enable_layout)
        
        # 股票列表
        stock_group = QGroupBox("监控股票")
        stock_layout = QVBoxLayout(stock_group)
        stock_layout.setContentsMargins(6, 10, 6, 6)
        stock_layout.setSpacing(4)
        
        self.stock_list = QListWidget()
        self.stock_list.setMaximumHeight(100)
        stock_layout.addWidget(self.stock_list)
        
        stock_btn_layout = QHBoxLayout()
        stock_btn_layout.setSpacing(6)
        add_stock_btn = QPushButton("添加")
        add_stock_btn.setFixedWidth(60)
        add_stock_btn.clicked.connect(self._add_stock)
        stock_btn_layout.addWidget(add_stock_btn)
        
        remove_stock_btn = QPushButton("删除")
        remove_stock_btn.setFixedWidth(60)
        remove_stock_btn.clicked.connect(self._remove_stock)
        stock_btn_layout.addWidget(remove_stock_btn)
        
        stock_btn_layout.addStretch()
        stock_layout.addLayout(stock_btn_layout)
        
        layout.addWidget(stock_group)
        
        # 显示设置
        display_group = QGroupBox("显示设置")
        display_layout = QFormLayout(display_group)
        display_layout.setContentsMargins(6, 10, 6, 6)
        display_layout.setSpacing(4)
        
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 48)
        self.font_size_spin.setFixedWidth(80)
        display_layout.addRow("字体大小:", self.font_size_spin)
        
        self.bg_alpha_slider = QSlider(Qt.Orientation.Horizontal)
        self.bg_alpha_slider.setRange(0, 255)
        display_layout.addRow("背景透明度:", self.bg_alpha_slider)
        
        self.text_alpha_slider = QSlider(Qt.Orientation.Horizontal)
        self.text_alpha_slider.setRange(0, 255)
        display_layout.addRow("文字透明度:", self.text_alpha_slider)
        
        self.refresh_interval_spin = QSpinBox()
        self.refresh_interval_spin.setRange(1, 3600)
        self.refresh_interval_spin.setSuffix(" 秒")
        self.refresh_interval_spin.setFixedWidth(80)
        display_layout.addRow("刷新间隔:", self.refresh_interval_spin)
        
        self.show_name_check = QCheckBox("显示名称")
        self.show_code_check = QCheckBox("显示代码")
        self.show_header_check = QCheckBox("显示标题栏")
        self.always_top_check = QCheckBox("始终置顶")
        
        check_layout = QHBoxLayout()
        check_layout.setSpacing(8)
        check_layout.addWidget(self.show_name_check)
        check_layout.addWidget(self.show_code_check)
        check_layout.addWidget(self.show_header_check)
        check_layout.addWidget(self.always_top_check)
        check_layout.addStretch()
        display_layout.addRow("显示选项:", check_layout)
        
        layout.addWidget(display_group)
        
        # 定时显示设置
        schedule_group = QGroupBox("定时显示")
        schedule_layout = QVBoxLayout(schedule_group)
        schedule_layout.setContentsMargins(6, 10, 6, 6)
        schedule_layout.setSpacing(4)
        
        self.enable_schedule_check = QCheckBox("启用定时显示")
        schedule_layout.addWidget(self.enable_schedule_check)
        
        self.schedule_table = QTableWidget(0, 3)
        self.schedule_table.setHorizontalHeaderLabels(["开始时间", "结束时间", "操作"])
        self.schedule_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.schedule_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.schedule_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.schedule_table.setColumnWidth(2, 50)
        self.schedule_table.setMaximumHeight(90)
        schedule_layout.addWidget(self.schedule_table)
        
        add_period_btn = QPushButton("添加时间段")
        add_period_btn.clicked.connect(self._add_schedule_period)
        schedule_layout.addWidget(add_period_btn)
        
        layout.addWidget(schedule_group)
        layout.addStretch()  # 添加弹性空间
        
        self.tab_widget.addTab(tab, "行情窗口")

    def _create_alert_tab(self):
        """创建行情预警选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)
        
        # 钉钉配置
        dingtalk_group = QGroupBox("钉钉通知")
        dingtalk_layout = QFormLayout(dingtalk_group)
        dingtalk_layout.setContentsMargins(6, 10, 6, 6)
        dingtalk_layout.setSpacing(4)
        
        self.webhook_edit = QLineEdit()
        self.webhook_edit.setPlaceholderText("https://oapi.dingtalk.com/robot/send?access_token=xxx")
        dingtalk_layout.addRow("Webhook:", self.webhook_edit)
        
        self.secret_edit = QLineEdit()
        self.secret_edit.setPlaceholderText("SECxxx")
        dingtalk_layout.addRow("Secret:", self.secret_edit)
        
        layout.addWidget(dingtalk_group)
        
        # 总开关
        enable_layout = QHBoxLayout()
        enable_layout.setSpacing(8)
        self.enable_alert_check = QCheckBox("启用行情预警")
        self.enable_alert_check.setStyleSheet("font-weight: bold; font-size: 12px;")
        enable_layout.addWidget(self.enable_alert_check)
        enable_layout.addStretch()
        layout.addLayout(enable_layout)
        
        # 预警设置
        alert_group = QGroupBox("预警设置")
        alert_layout = QVBoxLayout(alert_group)
        alert_layout.setContentsMargins(6, 10, 6, 6)
        alert_layout.setSpacing(4)
        
        top_layout = QHBoxLayout()
        top_layout.setSpacing(8)
        
        top_layout.addWidget(QLabel("扫描间隔:"))
        self.scan_interval_spin = QSpinBox()
        self.scan_interval_spin.setRange(1, 300)
        self.scan_interval_spin.setSuffix(" 秒")
        self.scan_interval_spin.setFixedWidth(70)
        top_layout.addWidget(self.scan_interval_spin)
        
        top_layout.addStretch()
        alert_layout.addLayout(top_layout)
        
        # 预警任务表格
        self.alert_table = QTableWidget(0, 4)
        self.alert_table.setHorizontalHeaderLabels(["股票代码", "策略", "K线周期（分钟）", "操作"])
        self.alert_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.alert_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.alert_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.alert_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.alert_table.setColumnWidth(2, 110)
        self.alert_table.setColumnWidth(3, 50)
        alert_layout.addWidget(self.alert_table)
        
        # 底部按钮栏
        bottom_btn_layout = QHBoxLayout()
        bottom_btn_layout.setSpacing(8)
        
        add_alert_btn = QPushButton("添加预警任务")
        add_alert_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        add_alert_btn.clicked.connect(self._add_alert_task)
        bottom_btn_layout.addWidget(add_alert_btn)
        
        reload_btn = QPushButton("重载策略")
        reload_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        reload_btn.clicked.connect(self._reload_strategies)
        bottom_btn_layout.addWidget(reload_btn)

        refresh_btn = QPushButton("刷新状态")
        refresh_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        refresh_btn.clicked.connect(self._refresh_alert_status)
        bottom_btn_layout.addWidget(refresh_btn)
        
        alert_layout.addLayout(bottom_btn_layout)
        
        layout.addWidget(alert_group)
        
        self.tab_widget.addTab(tab, "行情预警")

    def _load_current_settings(self):
        """加载当前设置"""
        # 行情窗口设置
        self.enable_quote_check.setChecked(self.settings_manager.get_quote_enabled())
        
        self.stock_list.clear()
        
        # 批量检查缓存（只对缺失的进行网络请求）
        all_codes = list(self.quote_manager.codes)
        stock_mgr = StockNameManager.get_instance()
        if stock_mgr and all_codes:
            # 只获取缓存中没有的（使用新方法检查，兼容带前缀和不带前缀的格式）
            stock_mgr.ensure_symbols(all_codes)  # ensure_symbols内部会正确检查缺失
        
        for code in all_codes:
            self._add_stock_item_fast(code)  # 使用快速版本，不再单独联网
        
        self.font_size_spin.setValue(self.quote_manager.font_size)
        self.bg_alpha_slider.setValue(self.quote_manager.background_alpha)
        self.text_alpha_slider.setValue(self.quote_manager.text_alpha)
        self.refresh_interval_spin.setValue(self.quote_manager.update_interval)
        
        self.show_name_check.setChecked(self.quote_manager.show_name)
        self.show_code_check.setChecked(self.quote_manager.show_code)
        self.show_header_check.setChecked(self.quote_manager.show_column_header)
        self.always_top_check.setChecked(self.quote_manager.always_on_top)
        
        # 定时显示
        self.enable_schedule_check.setChecked(self.settings_manager.get_time_schedule_enabled())
        self._load_schedule_periods()
        
        # 预警设置
        dingtalk = self.settings_manager.get_dingtalk_config()
        self.webhook_edit.setText(dingtalk.get('webhook', ''))
        self.secret_edit.setText(dingtalk.get('secret', ''))
        
        self.enable_alert_check.setChecked(self.settings_manager.get_alert_enabled())
        self.scan_interval_spin.setValue(self.settings_manager.get_alert_scan_interval())
        
        self._load_alert_tasks()

    def _load_schedule_periods(self):
        """加载时间段"""
        self.schedule_table.setRowCount(0)
        periods = self.settings_manager.get_time_schedule_periods()
        for period in periods:
            self._add_schedule_period_row(period.get('start', '09:25'), period.get('end', '15:05'))

    def _add_schedule_period(self):
        """添加时间段"""
        self._add_schedule_period_row('09:25', '15:05')

    def _add_schedule_period_row(self, start: str, end: str):
        """添加时间段行"""
        row = self.schedule_table.rowCount()
        self.schedule_table.insertRow(row)
        
        start_edit = QTimeEdit()
        start_parts = start.split(':')
        start_edit.setTime(QTime(int(start_parts[0]), int(start_parts[1])))
        start_edit.setDisplayFormat("HH:mm")
        self.schedule_table.setCellWidget(row, 0, start_edit)
        
        end_edit = QTimeEdit()
        end_parts = end.split(':')
        end_edit.setTime(QTime(int(end_parts[0]), int(end_parts[1])))
        end_edit.setDisplayFormat("HH:mm")
        self.schedule_table.setCellWidget(row, 1, end_edit)
        
        del_btn = QPushButton("删除")
        del_btn.clicked.connect(lambda: self._remove_schedule_row())
        self.schedule_table.setCellWidget(row, 2, del_btn)

    def _remove_schedule_row(self):
        """删除时间段行"""
        for i in range(self.schedule_table.rowCount()):
            btn = self.schedule_table.cellWidget(i, 2)
            if btn == self.sender():
                self.schedule_table.removeRow(i)
                break

    def _load_alert_tasks(self):
        """加载预警任务"""
        self.alert_table.setRowCount(0)
        tasks = self.settings_manager.get_alert_tasks()
        for task in tasks:
            self._add_alert_task_row(
                task.get('symbol', ''),
                task.get('strategy', ''),
                task.get('period', '5')
            )

    def _add_alert_task(self):
        """添加预警任务"""
        self._add_alert_task_row('', '', '5')

    def _add_alert_task_row(self, symbol: str, strategy: str, period: str):
        """添加预警任务行"""
        row = self.alert_table.rowCount()
        self.alert_table.insertRow(row)
        
        code_edit = QLineEdit()
        code_edit.setText(symbol)
        code_edit.setPlaceholderText("如: 600519")
        self.alert_table.setCellWidget(row, 0, code_edit)
        
        strategy_combo = QComboBox()
        strategies = self.alert_engine.get_available_strategies()
        for sid, info in strategies.items():
            strategy_combo.addItem(f"{info.get('name', sid)} ({sid})", sid)
        
        for i in range(strategy_combo.count()):
            if strategy_combo.itemData(i) == strategy:
                strategy_combo.setCurrentIndex(i)
                break
        
        self.alert_table.setCellWidget(row, 1, strategy_combo)
        
        period_combo = QComboBox()
        period_combo.addItems(['1', '5', '15', '30', '60'])
        period_combo.setCurrentText(period)
        self.alert_table.setCellWidget(row, 2, period_combo)
        
        del_btn = QPushButton("删除")
        del_btn.clicked.connect(lambda: self._remove_alert_row())
        self.alert_table.setCellWidget(row, 3, del_btn)

    def _remove_alert_row(self):
        """删除预警任务行"""
        for i in range(self.alert_table.rowCount()):
            btn = self.alert_table.cellWidget(i, 3)
            if btn == self.sender():
                self.alert_table.removeRow(i)
                break

    def _add_stock(self):
        """添加股票"""
        from ..utils import normalize_stock_code
        code, ok = QInputDialog.getText(self, "添加股票", "请输入股票代码:")
        if ok and code:
            normalized = normalize_stock_code(code)
            if normalized:
                self._add_stock_item(normalized)
            else:
                QMessageBox.warning(self, "错误", "无效的股票代码")

    def _add_stock_item_fast(self, code: str):
        """添加股票列表项（快速版本，只从缓存读取，不联网）"""
        stock_mgr = StockNameManager.get_instance()
        name = ""
        market = ""
        sec_type = ""
        
        if stock_mgr:
            # 使用新的兼容方法获取信息
            info = stock_mgr.get_info(code)
            name = info.get('name', '')
            market = info.get('market', '')
            sec_type = info.get('type', '')
        
        # 如果缓存中没有名称，尝试从行情数据获取
        if not name or name == code:
            if code in self.quote_manager.quotes:
                quote = self.quote_manager.quotes[code]
                if quote:
                    name = quote.name
        
        # 如果仍没有市场和类型信息，使用工具函数计算
        if not market:
            market = get_market_short_name(code)
        if not sec_type:
            sec_type = get_security_type(code)
        
        # 显示格式: 代码 - 名称 [市场·类型]
        if name and name != code:
            display = f"{code} - {name} [{market}·{sec_type}]"
        else:
            display = f"{code} [{market}·{sec_type}]"
        
        item = QListWidgetItem(display)
        item.setData(Qt.ItemDataRole.UserRole, code)
        self.stock_list.addItem(item)

    def _add_stock_item(self, code: str):
        """添加股票列表项（用于新增股票，会联网查询）"""
        # 首先尝试从缓存获取股票信息
        stock_mgr = StockNameManager.get_instance()
        name = ""
        market = ""
        sec_type = ""
        
        if stock_mgr:
            # ensure_symbols内部会正确检查缓存（兼容带前缀和不带前缀的格式）
            stock_mgr.ensure_symbols([code])
            info = stock_mgr.get_info(code)
            name = info.get('name', '')
            market = info.get('market', '')
            sec_type = info.get('type', '')
        
        # 如果缓存中没有名称，尝试从行情数据获取
        if not name or name == code:
            if code in self.quote_manager.quotes:
                quote = self.quote_manager.quotes[code]
                if quote:
                    name = quote.name
        
        # 如果仍没有市场和类型信息，使用工具函数计算
        if not market:
            market = get_market_short_name(code)
        if not sec_type:
            sec_type = get_security_type(code)
        
        # 显示格式: 代码 - 名称 [市场·类型]
        if name and name != code:
            display = f"{code} - {name} [{market}·{sec_type}]"
        else:
            display = f"{code} [{market}·{sec_type}]"
        
        item = QListWidgetItem(display)
        item.setData(Qt.ItemDataRole.UserRole, code)  # 存储原始代码
        self.stock_list.addItem(item)

    def _remove_stock(self):
        """删除股票"""
        current = self.stock_list.currentItem()
        if current:
            self.stock_list.takeItem(self.stock_list.row(current))

    def _reload_strategies(self):
        """重载策略"""
        success = self.alert_engine.reload_strategies()
        if success:
            self._reload_strategies_ui_only()
            QMessageBox.information(self, "成功", "策略重载成功！")
        else:
            QMessageBox.warning(self, "失败", "策略重载失败，请检查文件格式。")

    def _reload_strategies_ui_only(self):
        """仅刷新界面上的策略列表（不触发引擎重载）"""
        strategies = self.alert_engine.get_available_strategies()
        for row in range(self.alert_table.rowCount()):
            combo = self.alert_table.cellWidget(row, 1)
            if combo:
                current = combo.currentData()
                combo.clear()
                for sid, info in strategies.items():
                    combo.addItem(f"{info.get('name', sid)} ({sid})", sid)
                for i in range(combo.count()):
                    if combo.itemData(i) == current:
                        combo.setCurrentIndex(i)
                        break

    def _refresh_alert_status(self):
        """刷新预警状态"""
        is_running = self.alert_engine.is_running()
        self.enable_alert_check.setChecked(is_running)
        
        # 同步设置管理器状态
        self.settings_manager.set_alert_enabled(is_running)
        
        # 重新加载任务列表
        self._load_alert_tasks()
        
        status_text = "运行中" if is_running else "已停止"
        
        # 同步托盘图标菜单状态
        if self.on_settings_applied:
            self.on_settings_applied()
            
        QMessageBox.information(self, "状态刷新", "预警状态和任务列表已更新！")

    def _apply_settings(self):
        """应用设置"""
        # 行情窗口开关
        quote_enabled = self.enable_quote_check.isChecked()
        self.settings_manager.set_quote_enabled(quote_enabled)
        
        # 行情窗口设置
        new_codes = []
        for i in range(self.stock_list.count()):
            item = self.stock_list.item(i)
            code = item.data(Qt.ItemDataRole.UserRole)  # 从UserRole获取原始代码
            if code:
                new_codes.append(code)
            else:
                # 兼容旧数据，直接取文本
                new_codes.append(item.text().split(' ')[0])
        
        self.quote_manager.codes = new_codes
        self.quote_manager.font_size = self.font_size_spin.value()
        self.quote_manager.background_alpha = self.bg_alpha_slider.value()
        self.quote_manager.text_alpha = self.text_alpha_slider.value()
        self.quote_manager.update_interval = self.refresh_interval_spin.value()
        self.quote_manager.show_name = self.show_name_check.isChecked()
        self.quote_manager.show_code = self.show_code_check.isChecked()
        self.quote_manager.show_column_header = self.show_header_check.isChecked()
        self.quote_manager.always_on_top = self.always_top_check.isChecked()
        
        self.quote_manager.fetch_timer.setInterval(self.quote_manager.update_interval * 1000)
        
        # 根据开关控制行情窗口
        if quote_enabled:
            # 必须调用 show_windows 以确保 _visible 标志被重置为 True
            self.quote_manager.show_windows()
            self.quote_manager._apply_settings_to_all()
            self.quote_manager._notify_settings_changed()
            if not self.quote_manager.fetch_timer.isActive():
                self.quote_manager.fetch_timer.start()
        else:
            # 关闭行情窗口
            self.quote_manager.fetch_timer.stop()
            self.quote_manager.close_all_windows()
        
        # 定时显示设置
        self.settings_manager.set_time_schedule_enabled(self.enable_schedule_check.isChecked())
        
        periods = []
        for row in range(self.schedule_table.rowCount()):
            start_edit = self.schedule_table.cellWidget(row, 0)
            end_edit = self.schedule_table.cellWidget(row, 1)
            if start_edit and end_edit:
                periods.append({
                    'start': start_edit.time().toString("HH:mm"),
                    'end': end_edit.time().toString("HH:mm"),
                })
        self.settings_manager.set_time_schedule_periods(periods)
        
        # 预警设置
        self.settings_manager.set_dingtalk_config({
            'webhook': self.webhook_edit.text().strip(),
            'secret': self.secret_edit.text().strip(),
        })
        
        tasks = []
        for row in range(self.alert_table.rowCount()):
            code_edit = self.alert_table.cellWidget(row, 0)
            strategy_combo = self.alert_table.cellWidget(row, 1)
            period_combo = self.alert_table.cellWidget(row, 2)
            
            if code_edit and strategy_combo and period_combo:
                symbol = code_edit.text().strip()
                if symbol:
                    tasks.append({
                        'symbol': symbol,
                        'strategy': strategy_combo.currentData(),
                        'period': period_combo.currentText(),
                    })
        
        self.settings_manager.set_alert_tasks(tasks)
        self.settings_manager.set_alert_scan_interval(self.scan_interval_spin.value())
        
        # 更新预警引擎
        was_running = self.alert_engine.is_running()
        should_run = self.enable_alert_check.isChecked()
        
        if should_run:
            dingtalk = self.settings_manager.get_dingtalk_config()
            self.alert_engine.update_tasks(tasks, self.scan_interval_spin.value())
            if self.alert_engine.notifier:
                self.alert_engine.notifier.update_config(
                    dingtalk.get('webhook', ''),
                    dingtalk.get('secret', '')
                )
            
            if not was_running:
                self.alert_engine.start()
            else:
                # 如果已经在运行，发送配置更新通知
                if self.alert_engine.notifier:
                    self.alert_engine.notifier.send(f"【系统通知】\n预警配置已更新\n当前任务数: {len(tasks)}")
        else:
            if was_running:
                self.alert_engine.stop()
        
        self.settings_manager.set_alert_enabled(should_run)
        
        # 同步托盘图标菜单状态
        if self.on_settings_applied:
            self.on_settings_applied()
        
        QMessageBox.information(self, "成功", "设置已应用！")

    def closeEvent(self, event: QCloseEvent):
        """关闭时隐藏而不是退出"""
        event.ignore()
        self.hide()

    def showEvent(self, event):
        """显示时刷新数据"""
        super().showEvent(event)
        self._load_current_settings()
