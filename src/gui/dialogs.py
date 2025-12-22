# gui/dialogs.py - 对话框组件
"""对话框组件"""

from typing import Dict, List, Optional, Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QComboBox,
    QListWidget,
    QListWidgetItem,
    QCheckBox,
    QSpinBox,
    QTimeEdit,
    QGroupBox,
    QMessageBox,
    QWidget,
    QDialogButtonBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
)
from PyQt6.QtCore import QTime


class AddStockDialog(QDialog):
    """添加股票对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("添加股票")
        self.setMinimumWidth(300)
        
        layout = QVBoxLayout(self)
        
        form = QFormLayout()
        self.code_edit = QLineEdit()
        self.code_edit.setPlaceholderText("如: 600519, sh600519, hk00700")
        form.addRow("股票代码:", self.code_edit)
        layout.addLayout(form)
        
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        self.code_edit.setFocus()

    def get_code(self) -> str:
        return self.code_edit.text().strip()


class TimeScheduleDialog(QDialog):
    """时间段设置对话框"""
    
    def __init__(self, parent=None, periods: List[Dict] = None):
        super().__init__(parent)
        self.setWindowTitle("设置显示时间段")
        self.setMinimumWidth(400)
        self.setMinimumHeight(300)
        
        self.periods = periods or []
        
        layout = QVBoxLayout(self)
        
        # 说明
        tip = QLabel("设置行情窗口自动显示的时间段。\n手动打开的窗口不受时间段影响。")
        tip.setStyleSheet("color: gray;")
        layout.addWidget(tip)
        
        # 时间段列表
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["开始时间", "结束时间", "操作"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(2, 60)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)
        
        # 添加按钮
        add_btn = QPushButton("添加时间段")
        add_btn.clicked.connect(self._add_period)
        layout.addWidget(add_btn)
        
        # 确定取消
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        # 加载现有时间段
        self._load_periods()

    def _load_periods(self):
        """加载现有时间段"""
        for period in self.periods:
            self._add_period_row(period.get('start', '09:25'), period.get('end', '15:05'))

    def _add_period(self):
        """添加新时间段"""
        self._add_period_row('09:25', '15:05')

    def _add_period_row(self, start: str, end: str):
        """添加一行"""
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        # 开始时间
        start_edit = QTimeEdit()
        start_parts = start.split(':')
        start_edit.setTime(QTime(int(start_parts[0]), int(start_parts[1])))
        start_edit.setDisplayFormat("HH:mm")
        self.table.setCellWidget(row, 0, start_edit)
        
        # 结束时间
        end_edit = QTimeEdit()
        end_parts = end.split(':')
        end_edit.setTime(QTime(int(end_parts[0]), int(end_parts[1])))
        end_edit.setDisplayFormat("HH:mm")
        self.table.setCellWidget(row, 1, end_edit)
        
        # 删除按钮
        del_btn = QPushButton("删除")
        del_btn.clicked.connect(lambda: self._remove_row(row))
        self.table.setCellWidget(row, 2, del_btn)

    def _remove_row(self, row: int):
        """删除一行"""
        # 重新获取行号（因为删除后会变）
        for i in range(self.table.rowCount()):
            btn = self.table.cellWidget(i, 2)
            if btn == self.sender():
                self.table.removeRow(i)
                break

    def get_periods(self) -> List[Dict]:
        """获取所有时间段"""
        periods = []
        for row in range(self.table.rowCount()):
            start_edit = self.table.cellWidget(row, 0)
            end_edit = self.table.cellWidget(row, 1)
            if start_edit and end_edit:
                periods.append({
                    'start': start_edit.time().toString("HH:mm"),
                    'end': end_edit.time().toString("HH:mm"),
                })
        return periods


class AlertConfigDialog(QDialog):
    """预警配置对话框"""
    
    def __init__(self, parent=None, tasks: List[Dict] = None, 
                 available_strategies: Dict = None, scan_interval: int = 20,
                 dingtalk_config: Dict = None):
        super().__init__(parent)
        self.setWindowTitle("预警配置")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        
        self.tasks = tasks or []
        self.available_strategies = available_strategies or {}
        
        layout = QVBoxLayout(self)
        
        # 钉钉配置
        dingtalk_group = QGroupBox("钉钉通知配置")
        dingtalk_layout = QFormLayout(dingtalk_group)
        
        self.webhook_edit = QLineEdit()
        self.webhook_edit.setPlaceholderText("https://oapi.dingtalk.com/robot/send?access_token=xxx")
        self.webhook_edit.setText(dingtalk_config.get('webhook', '') if dingtalk_config else '')
        dingtalk_layout.addRow("Webhook:", self.webhook_edit)
        
        self.secret_edit = QLineEdit()
        self.secret_edit.setPlaceholderText("SECxxx")
        self.secret_edit.setText(dingtalk_config.get('secret', '') if dingtalk_config else '')
        dingtalk_layout.addRow("Secret:", self.secret_edit)
        
        layout.addWidget(dingtalk_group)
        
        # 扫描间隔
        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("扫描间隔:"))
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 300)
        self.interval_spin.setValue(scan_interval)
        self.interval_spin.setSuffix(" 秒")
        interval_layout.addWidget(self.interval_spin)
        interval_layout.addStretch()
        layout.addLayout(interval_layout)
        
        # 预警任务列表
        task_group = QGroupBox("预警任务")
        task_layout = QVBoxLayout(task_group)
        
        self.task_table = QTableWidget(0, 4)
        self.task_table.setHorizontalHeaderLabels(["股票代码", "策略", "周期", "操作"])
        self.task_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.task_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.task_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.task_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.task_table.setColumnWidth(2, 80)
        self.task_table.setColumnWidth(3, 60)
        task_layout.addWidget(self.task_table)
        
        # 添加任务按钮
        add_task_btn = QPushButton("添加预警任务")
        add_task_btn.clicked.connect(self._add_task)
        task_layout.addWidget(add_task_btn)
        
        layout.addWidget(task_group)
        
        # 确定取消
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        # 加载现有任务
        self._load_tasks()

    def _load_tasks(self):
        """加载现有任务"""
        for task in self.tasks:
            self._add_task_row(
                task.get('symbol', ''),
                task.get('strategy', ''),
                task.get('period', '5')
            )

    def _add_task(self):
        """添加新任务"""
        self._add_task_row('', '', '5')

    def _add_task_row(self, symbol: str, strategy: str, period: str):
        """添加任务行"""
        row = self.task_table.rowCount()
        self.task_table.insertRow(row)
        
        # 股票代码
        code_edit = QLineEdit()
        code_edit.setText(symbol)
        code_edit.setPlaceholderText("如: 600519")
        self.task_table.setCellWidget(row, 0, code_edit)
        
        # 策略选择
        strategy_combo = QComboBox()
        for sid, info in self.available_strategies.items():
            strategy_combo.addItem(f"{info.get('name', sid)} ({sid})", sid)
        
        # 设置当前值
        for i in range(strategy_combo.count()):
            if strategy_combo.itemData(i) == strategy:
                strategy_combo.setCurrentIndex(i)
                break
        
        self.task_table.setCellWidget(row, 1, strategy_combo)
        
        # 周期选择
        period_combo = QComboBox()
        period_combo.addItems(['1', '5', '15', '30', '60'])
        period_combo.setCurrentText(period)
        self.task_table.setCellWidget(row, 2, period_combo)
        
        # 删除按钮
        del_btn = QPushButton("删除")
        del_btn.clicked.connect(lambda: self._remove_task_row())
        self.task_table.setCellWidget(row, 3, del_btn)

    def _remove_task_row(self):
        """删除任务行"""
        for i in range(self.task_table.rowCount()):
            btn = self.task_table.cellWidget(i, 3)
            if btn == self.sender():
                self.task_table.removeRow(i)
                break

    def get_tasks(self) -> List[Dict]:
        """获取所有任务"""
        tasks = []
        for row in range(self.task_table.rowCount()):
            code_edit = self.task_table.cellWidget(row, 0)
            strategy_combo = self.task_table.cellWidget(row, 1)
            period_combo = self.task_table.cellWidget(row, 2)
            
            if code_edit and strategy_combo and period_combo:
                symbol = code_edit.text().strip()
                if symbol:
                    tasks.append({
                        'symbol': symbol,
                        'strategy': strategy_combo.currentData(),
                        'period': period_combo.currentText(),
                    })
        return tasks

    def get_scan_interval(self) -> int:
        return self.interval_spin.value()

    def get_dingtalk_config(self) -> Dict:
        return {
            'webhook': self.webhook_edit.text().strip(),
            'secret': self.secret_edit.text().strip(),
        }

    def update_strategies(self, strategies: Dict):
        """更新可用策略列表"""
        self.available_strategies = strategies
        # 更新所有策略下拉框
        for row in range(self.task_table.rowCount()):
            strategy_combo = self.task_table.cellWidget(row, 1)
            if strategy_combo:
                current = strategy_combo.currentData()
                strategy_combo.clear()
                for sid, info in strategies.items():
                    strategy_combo.addItem(f"{info.get('name', sid)} ({sid})", sid)
                # 恢复选择
                for i in range(strategy_combo.count()):
                    if strategy_combo.itemData(i) == current:
                        strategy_combo.setCurrentIndex(i)
                        break
