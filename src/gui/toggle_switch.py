# gui/toggle_switch.py - Win11 风格拨动开关
"""Win11 风格 ToggleSwitch 控件"""

from PyQt6.QtCore import Qt, QRectF, QPropertyAnimation, QEasingCurve, pyqtProperty, QSize
from PyQt6.QtGui import QPainter, QColor, QPainterPath, QMouseEvent
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel


class _ToggleTrack(QWidget):
    """开关滑轨"""

    def __init__(self, parent: "ToggleSwitch"):
        super().__init__(parent)
        self._switch = parent
        self._offset = 0.0  # 0.0=off, 1.0=on
        self.setFixedSize(44, 22)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._anim = QPropertyAnimation(self, b"offset")
        self._anim.setDuration(150)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

    @pyqtProperty(float)
    def offset(self) -> float:
        return self._offset

    @offset.setter  # type: ignore[attr-defined]
    def offset(self, value: float) -> None:
        self._offset = value
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._switch.toggle()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        radius = h / 2

        # 轨道颜色
        off_track = QColor(190, 190, 190)
        on_track = QColor(0, 95, 184)  # Win11 accent blue
        track_color = _lerp_color(off_track, on_track, self._offset)

        # 绘制轨道
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, w, h), radius, radius)
        p.fillPath(path, track_color)

        # 圆形把手
        margin = 3.0
        knob_d = h - margin * 2
        x_off = margin
        x_on = w - knob_d - margin
        knob_x = x_off + (x_on - x_off) * self._offset

        p.setBrush(QColor(255, 255, 255))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(knob_x, margin, knob_d, knob_d))
        p.end()


def _lerp_color(c1: QColor, c2: QColor, t: float) -> QColor:
    return QColor(
        int(c1.red() + (c2.red() - c1.red()) * t),
        int(c1.green() + (c2.green() - c1.green()) * t),
        int(c1.blue() + (c2.blue() - c1.blue()) * t),
    )


class ToggleSwitch(QWidget):
    """带文字标签的 Win11 风格拨动开关，API 兼容 QCheckBox。

    使用方法:
        sw = ToggleSwitch("启用行情窗口")
        sw.setChecked(True)
        sw.isChecked()
    """

    def __init__(self, text: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(10)

        self._label = QLabel(text)
        self._label.setStyleSheet("background: transparent;")
        layout.addWidget(self._label)

        layout.addStretch()

        self._track = _ToggleTrack(self)
        layout.addWidget(self._track)

        self._checked = False
        # 回调列表 (兼容 .connect / .disconnect)
        self._callbacks: list = []

    # --- QCheckBox 兼容接口 ---

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, value: bool) -> None:
        if self._checked == value:
            self._track.offset = 1.0 if value else 0.0
            self._track.update()
            return
        self._checked = value
        self._track._anim.stop()
        self._track._anim.setStartValue(self._track.offset)
        self._track._anim.setEndValue(1.0 if value else 0.0)
        self._track._anim.start()

    def toggle(self) -> None:
        self.setChecked(not self._checked)
        for cb in self._callbacks:
            cb(self._checked)

    def text(self) -> str:
        return self._label.text()

    def setText(self, text: str) -> None:
        self._label.setText(text)

    def setStyleSheet(self, css: str) -> None:
        # 将字体样式传递给 label
        self._label.setStyleSheet(css + " background: transparent;")

    def sizeHint(self) -> QSize:
        return QSize(200, 30)

    # --- 信号模拟 (toggled) ---

    class _Signal:
        """简易信号代理，支持 .connect / .disconnect"""

        def __init__(self, owner: "ToggleSwitch"):
            self._owner = owner

        def connect(self, cb):
            self._owner._callbacks.append(cb)

        def disconnect(self, cb=None):
            if cb is None:
                self._owner._callbacks.clear()
            else:
                try:
                    self._owner._callbacks.remove(cb)
                except ValueError:
                    pass

    @property
    def toggled(self):
        return self._Signal(self)

    @property
    def stateChanged(self):
        return self._Signal(self)
