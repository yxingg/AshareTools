# gui/win11_style.py - Win11 风格样式
"""Win11 Fluent Design 全局样式"""

from PyQt6.QtWidgets import QApplication


WIN11_STYLE = """
/* ===== Win11 Fluent Design Style ===== */
* {
    font-family: "Segoe UI Variable", "Segoe UI", "Microsoft YaHei UI", "微软雅黑", sans-serif;
}

QMainWindow, QDialog {
    background-color: #f3f3f3;
}

/* === Tab Widget === */
QTabWidget::pane {
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    background-color: #ffffff;
    top: -1px;
}

QTabBar::tab {
    background-color: transparent;
    color: #616161;
    padding: 8px 20px;
    margin-right: 2px;
    border: none;
    border-bottom: 2px solid transparent;
}

QTabBar::tab:selected {
    color: #005fb8;
    border-bottom: 2px solid #005fb8;
}

QTabBar::tab:hover:!selected {
    color: #1a1a1a;
    background-color: rgba(0, 0, 0, 0.04);
    border-radius: 6px 6px 0 0;
}

/* === Group Box === */
QGroupBox {
    background-color: #fbfbfb;
    border: 1px solid #e8e8e8;
    border-radius: 8px;
    margin-top: 14px;
    padding: 16px 10px 10px 10px;
    font-weight: bold;
    color: #1a1a1a;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 2px 8px;
    color: #1a1a1a;
}

/* === Push Button === */
QPushButton {
    background-color: #fdfdfd;
    border: 1px solid #d1d1d1;
    border-bottom: 1px solid #b8b8b8;
    border-radius: 6px;
    padding: 5px 16px;
    color: #1a1a1a;
    min-height: 22px;
}

QPushButton:hover {
    background-color: #f0f0f0;
    border-color: #c0c0c0;
}

QPushButton:pressed {
    background-color: #e5e5e5;
    border-color: #b0b0b0;
    color: #444444;
}

QPushButton:disabled {
    background-color: #f5f5f5;
    border-color: #e0e0e0;
    color: #a0a0a0;
}

/* === Line Edit === */
QLineEdit {
    border: 1px solid #d1d1d1;
    border-bottom: 1px solid #ababab;
    border-radius: 6px;
    padding: 5px 10px;
    background-color: #ffffff;
    color: #1a1a1a;
    selection-background-color: #005fb8;
    selection-color: #ffffff;
    min-height: 20px;
}

QLineEdit:focus {
    border: 1px solid #d1d1d1;
    border-bottom: 2px solid #005fb8;
}

/* === Spin Box === */
QSpinBox, QDoubleSpinBox {
    border: 1px solid #d1d1d1;
    border-bottom: 1px solid #ababab;
    border-radius: 6px;
    padding: 4px 8px;
    background-color: #ffffff;
    color: #1a1a1a;
    min-height: 20px;
}

QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #d1d1d1;
    border-bottom: 2px solid #005fb8;
}

QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    border: none;
    width: 20px;
    background: transparent;
}

/* === Combo Box === */
QComboBox {
    border: 1px solid #d1d1d1;
    border-bottom: 1px solid #ababab;
    border-radius: 6px;
    padding: 4px 10px;
    background-color: #ffffff;
    color: #1a1a1a;
    min-height: 20px;
}

QComboBox:hover {
    background-color: #f9f9f9;
}

QComboBox:focus {
    border-bottom: 2px solid #005fb8;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox QAbstractItemView {
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    background-color: #ffffff;
    selection-background-color: rgba(0, 95, 184, 0.08);
    selection-color: #1a1a1a;
    padding: 4px;
    outline: none;
}

/* === Check Box === */
QCheckBox {
    spacing: 8px;
    color: #1a1a1a;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 2px solid #8c8c8c;
    background-color: #ffffff;
}

QCheckBox::indicator:hover {
    border-color: #666666;
    background-color: #f5f5f5;
}

QCheckBox::indicator:checked {
    background-color: #005fb8;
    border-color: #005fb8;
}

QCheckBox::indicator:checked:hover {
    background-color: #1a6fc4;
    border-color: #1a6fc4;
}

/* === Time Edit === */
QTimeEdit {
    border: 1px solid #d1d1d1;
    border-bottom: 1px solid #ababab;
    border-radius: 6px;
    padding: 4px 8px;
    background-color: #ffffff;
    color: #1a1a1a;
    min-height: 20px;
}

QTimeEdit:focus {
    border-bottom: 2px solid #005fb8;
}

/* === Slider === */
QSlider::groove:horizontal {
    border: none;
    height: 4px;
    background-color: #d1d1d1;
    border-radius: 2px;
}

QSlider::handle:horizontal {
    background-color: #005fb8;
    border: 2px solid #ffffff;
    width: 18px;
    height: 18px;
    margin: -8px 0;
    border-radius: 11px;
}

QSlider::handle:horizontal:hover {
    background-color: #1a6fc4;
}

QSlider::sub-page:horizontal {
    background-color: #005fb8;
    border-radius: 2px;
}

/* === List Widget === */
QListWidget {
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    background-color: #ffffff;
    padding: 4px;
    outline: none;
}

QListWidget::item {
    padding: 5px 8px;
    border-radius: 4px;
}

QListWidget::item:hover {
    background-color: rgba(0, 0, 0, 0.04);
}

QListWidget::item:selected {
    background-color: rgba(0, 95, 184, 0.08);
    color: #1a1a1a;
}

/* === Table Widget (设置窗口和对话框中的表格) === */
QMainWindow QTableWidget, QDialog QTableWidget {
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    background-color: #ffffff;
    gridline-color: #f0f0f0;
    selection-background-color: rgba(0, 95, 184, 0.08);
    selection-color: #1a1a1a;
    outline: none;
}

QMainWindow QTableWidget QHeaderView::section,
QDialog QTableWidget QHeaderView::section {
    background-color: #f8f8f8;
    color: #616161;
    border: none;
    border-bottom: 1px solid #e0e0e0;
    padding: 6px 8px;
    font-weight: bold;
}

/* === Scroll Bar === */
QScrollBar:vertical {
    border: none;
    background-color: transparent;
    width: 8px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background-color: rgba(0, 0, 0, 0.15);
    border-radius: 4px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background-color: rgba(0, 0, 0, 0.25);
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    border: none;
    background-color: transparent;
    height: 8px;
    margin: 0;
}

QScrollBar::handle:horizontal {
    background-color: rgba(0, 0, 0, 0.15);
    border-radius: 4px;
    min-width: 30px;
}

QScrollBar::handle:horizontal:hover {
    background-color: rgba(0, 0, 0, 0.25);
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

/* === Context Menu === */
QMenu {
    background-color: #f9f9f9;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    padding: 4px 0;
}

QMenu::item {
    padding: 5px 36px 5px 16px;
    color: #1a1a1a;
    border-radius: 4px;
    margin: 1px 4px;
}

QMenu::item:selected {
    background-color: rgba(0, 0, 0, 0.04);
}

QMenu::item:disabled {
    color: #a0a0a0;
}

QMenu::separator {
    height: 1px;
    background-color: #e5e5e5;
    margin: 4px 12px;
}

QMenu::indicator {
    width: 16px;
    height: 16px;
    margin-left: 6px;
}

/* === Message Box & Input Dialog === */
QMessageBox, QInputDialog {
    background-color: #f3f3f3;
}

QMessageBox QPushButton, QInputDialog QPushButton {
    min-width: 80px;
}

/* === Tool Tip === */
QToolTip {
    background-color: #ffffff;
    color: #1a1a1a;
    border: 1px solid #e0e0e0;
    border-radius: 6px;
    padding: 6px 10px;
}

/* === Dialog Button Box === */
QDialogButtonBox QPushButton {
    min-width: 80px;
}

/* === Label === */
QLabel {
    color: #1a1a1a;
    background: transparent;
}
"""


def apply_win11_style(app: QApplication) -> None:
    """应用 Win11 Fluent Design 风格到整个应用"""
    app.setStyleSheet(WIN11_STYLE)
