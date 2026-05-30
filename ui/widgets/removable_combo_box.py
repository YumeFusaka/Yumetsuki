from __future__ import annotations

from PySide6.QtCore import QEvent, QRect, Signal, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QComboBox, QStyledItemDelegate, QStyleOptionViewItem


class _RemoveItemDelegate(QStyledItemDelegate):
    def __init__(self, combo: "RemovableComboBox"):
        super().__init__(combo)
        self._combo = combo

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        text_option = QStyleOptionViewItem(option)
        text_option.rect = option.rect.adjusted(0, 0, -self._combo.remove_area_width(), 0)
        super().paint(painter, text_option, index)

        rect = self._combo.remove_rect(option.rect)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(QColor("#a85a72"))
        pen.setWidth(2)
        painter.setPen(pen)
        center = rect.center()
        half = 4
        painter.drawLine(center.x() - half, center.y() - half, center.x() + half, center.y() + half)
        painter.drawLine(center.x() + half, center.y() - half, center.x() - half, center.y() + half)
        painter.restore()


class RemovableComboBox(QComboBox):
    """可在下拉列表右侧点击 x 移除条目的组合框；不会删除磁盘文件。"""

    itemRemoveRequested = Signal(str)
    itemRemoved = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setItemDelegate(_RemoveItemDelegate(self))
        self.view().viewport().installEventFilter(self)

    def remove_area_width(self) -> int:
        return 28

    def remove_rect(self, item_rect: QRect) -> QRect:
        return QRect(
            item_rect.right() - self.remove_area_width() + 1,
            item_rect.top(),
            self.remove_area_width(),
            item_rect.height(),
        )

    def remove_item_at(self, index: int) -> None:
        if index < 0 or index >= self.count():
            return
        text = self.itemText(index)
        self.itemRemoveRequested.emit(text)
        self.removeItem(index)
        if self.count() == 0 and self.isEditable():
            self.setEditText("")
        self.itemRemoved.emit(text)

    def eventFilter(self, watched, event) -> bool:
        viewport = self.view().viewport()
        if watched is viewport and event.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease):
            if event.button() == Qt.MouseButton.LeftButton:
                pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
                index = self.view().indexAt(pos)
                if index.isValid() and self.remove_rect(self.view().visualRect(index)).contains(pos):
                    if event.type() == QEvent.Type.MouseButtonRelease:
                        self.remove_item_at(index.row())
                    return True
        return super().eventFilter(watched, event)
