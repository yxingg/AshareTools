# gui/float_window.py - 行情浮动窗口
"""行情浮动窗口组件"""

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from PyQt6.QtCore import QEvent, QPoint, QRect, Qt
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHeaderView,
    QMenu,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..constants import COLUMN_COUNT, COLUMN_HEADERS
from ..utils import color_to_rgba

if TYPE_CHECKING:
    from .quote_manager import QuoteWindowManager


class StockFloatWindow(QWidget):
    """股票行情浮动窗口"""
    
    RESIZE_MARGIN = 8

    def __init__(self, manager: "QuoteWindowManager", code: str) -> None:
        super().__init__()
        self.manager = manager
        self.code = code
        self.quote = None

        self._moving = False
        self._move_offset: Optional[QPoint] = None
        self._resize_mode = "center"
        self._resize_origin: Optional[QPoint] = None
        self._resize_geometry: Optional[QRect] = None

        self._bg_color = QColor(0, 0, 0, 180)
        self._neutral_color = QColor(230, 230, 230)
        self._up_color = QColor(217, 48, 80)
        self._down_color = QColor(0, 158, 96)
        self._initializing = True  # 标志：初始化中不同步设置

        self.table = QTableWidget(1, COLUMN_COUNT, self)
        self.table.setHorizontalHeaderLabels(COLUMN_HEADERS)
        self.table.setVerticalHeaderLabels([""])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.setShowGrid(False)
        self.table.setFrameShape(QFrame.Shape.NoFrame)
        self.table.verticalHeader().setVisible(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.table)

        self.table.horizontalHeader().sectionResized.connect(self._handle_column_resized)
        self.table.verticalHeader().sectionResized.connect(self._handle_row_resized)

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        self.table.viewport().installEventFilter(self)
        self.table.viewport().setMouseTracking(True)
        self.table.horizontalHeader().installEventFilter(self)

        self.setMouseTracking(True)
        self.setMinimumSize(1, 1)
        self._apply_flags(show=False)  # 初始化时不显示，由外部控制

    def _apply_flags(self, show: bool = False) -> None:
        """应用窗口标志
        
        Args:
            show: 是否在设置标志后显示窗口（setWindowFlags会隐藏窗口）
        """
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
        )
        if self.manager.always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowFlags(flags)
        if show:
            self.show()

    def apply_settings(self, config: Dict[str, Any], *, initial: bool) -> None:
        """应用设置"""
        self._initializing = initial  # 初始化时不同步设置
        self._bg_color = config["background_color"]
        self._neutral_color = config["neutral_color"]
        self._up_color = config["up_color"]
        self._down_color = config["down_color"]

        font = self.table.font()
        font.setPointSize(config["font_size"])
        self.table.setFont(font)

        header_font = self.table.horizontalHeader().font()
        header_font.setPointSize(max(config["font_size"] - 2, 8))
        self.table.horizontalHeader().setFont(header_font)
        self.table.horizontalHeader().setVisible(config["show_column_header"])

        self.table.setColumnHidden(0, not config["show_name"])
        self.table.setColumnHidden(1, not config["show_code"])

        unit = self.manager.code_settings.get(self.code, {}).get("volume_unit", 100)
        self.table.setColumnHidden(5, unit == 0)

        for index, width in enumerate(config["column_widths"]):
            self.table.setColumnWidth(index, width)

        self.table.setRowHeight(0, config["row_height"])

        if initial:
            width, height = config["window_size"]
            self.resize(width, height)

        # 应用窗口标志但不显示，由外部控制显示
        visible = self.isVisible()
        self._apply_flags(show=visible)
        self._refresh_style()
        self._initializing = False  # 结束初始化

    def update_quote(self, quote) -> None:
        """更新行情数据"""
        self.quote = quote
        if quote:
            values = quote.as_row()
            unit = self.manager.code_settings.get(self.code, {}).get("volume_unit", 100)
            if unit > 0 and (quote.bid1_volume > 0 or quote.ask1_volume > 0):
                divisor = unit * 100
                ask_display = quote.ask1_volume / divisor
                bid_display = quote.bid1_volume / divisor
                
                def fmt(v: float) -> str:
                    s = f"{v:.2f}"
                    if s.endswith("0"):
                        s = s.rstrip("0").rstrip(".")
                    return s

                values.append(f"{fmt(ask_display)}/{fmt(bid_display)}")
            else:
                values.append("--")
        else:
            values = ["--", self.code, "--", "--", "--", "--"]

        for col, value in enumerate(values):
            item = self.table.item(0, col)
            if item is None:
                item = QTableWidgetItem(value)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                self.table.setItem(0, col, item)
            else:
                item.setText(value)
            item.setData(Qt.ItemDataRole.UserRole, self.code)
            item.setForeground(QBrush(self._color_for_quote(quote)))
        self.setWindowTitle(values[0] if values[0] and values[0] != "--" else self.code)

    def _color_for_quote(self, quote) -> QColor:
        """根据涨跌返回颜色"""
        if not quote:
            return self._neutral_color
        if quote.change > 0:
            return self._up_color
        elif quote.change < 0:
            return self._down_color
        return self._neutral_color

    def auto_fit(self) -> None:
        """自适应窗口大小"""
        self.table.resizeColumnsToContents()
        self.table.resizeRowsToContents()
        width = self.table.verticalHeader().width()
        width += self.table.horizontalHeader().length()
        width += self.table.frameWidth() * 2
        if self.table.verticalScrollBar().isVisible():
            width += self.table.verticalScrollBar().width()

        header_height = self.table.horizontalHeader().height() if self.table.horizontalHeader().isVisible() else 0
        height = header_height
        height += self.table.rowHeight(0)
        height += self.table.frameWidth() * 2
        if self.table.horizontalScrollBar().isVisible():
            height += self.table.horizontalScrollBar().height()

        self.resize(max(width, 1), max(height, 1))
        self.manager.sync_from_window(self)

    def get_column_widths(self) -> List[int]:
        return [self.table.columnWidth(i) for i in range(COLUMN_COUNT)]

    def get_row_height(self) -> int:
        return self.table.rowHeight(0)

    def get_window_size(self) -> tuple:
        return (self.width(), self.height())

    def _refresh_style(self) -> None:
        bg = color_to_rgba(self._bg_color)
        fg = color_to_rgba(self._neutral_color)
        self.table.setStyleSheet(
            f"QTableWidget {{"
            f" background-color: {bg};"
            f" color: {fg};"
            f" gridline-color: transparent;"
            f" selection-background-color: rgba(255, 255, 255, 32);"
            f" selection-color: {fg};"
            f" border: none;"
            f"}}"
            f"QTableWidget::item {{"
            f" border: none;"
            f"}}"
            f"QHeaderView::section {{"
            f" background-color: {bg};"
            f" color: {fg};"
            f" border: none;"
            f" padding: 4px;"
            f"}}"
        )

    def _show_context_menu(self, point) -> None:
        menu = QMenu(self)
        self.manager.populate_context_menu(menu, self, self.code)
        menu.exec(self.mapToGlobal(point))

    def _handle_column_resized(self, index: int, old_size: int, new_size: int) -> None:
        if not self._initializing:
            self.manager.sync_from_window(self)

    def _handle_row_resized(self, index: int, old_size: int, new_size: int) -> None:
        if not self._initializing:
            self.manager.sync_from_window(self)

    def eventFilter(self, obj, event) -> bool:
        if event.type() == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton:
                self._moving = True
                self._move_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                return True
        elif event.type() == QEvent.Type.MouseMove:
            if self._moving and self._move_offset:
                self.move(event.globalPosition().toPoint() - self._move_offset)
                return True
        elif event.type() == QEvent.Type.MouseButtonRelease:
            self._moving = False
            self._move_offset = None
            self.manager.sync_from_window(self)
        return super().eventFilter(obj, event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._moving = True
            self._move_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event) -> None:
        if self._moving and self._move_offset:
            self.move(event.globalPosition().toPoint() - self._move_offset)

    def mouseReleaseEvent(self, event) -> None:
        self._moving = False
        self._move_offset = None
        self.manager.sync_from_window(self)
