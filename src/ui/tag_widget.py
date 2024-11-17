from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QLabel, QPushButton, QVBoxLayout
from PyQt6.QtGui import QColor, QPainter, QBrush, QPen
from PyQt6.QtCore import Qt, QRect, pyqtSignal


class TagWidget(QWidget):
    tag_added = pyqtSignal(str)
    tag_removed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tags = []
        self.init_ui()

    def init_ui(self):
        self.layout = QVBoxLayout(self)
        self.tag_input = QLineEdit(self)
        self.tag_input.setPlaceholderText("Enter tags (comma-separated)")
        self.tag_input.returnPressed.connect(self.add_tags_from_input)
        self.layout.addWidget(self.tag_input)
        self.tag_container = QWidget(self)
        self.tag_layout = QHBoxLayout(self.tag_container)
        self.layout.addWidget(self.tag_container)

    def add_tags_from_input(self):
        tags = self.tag_input.text().split(',')
        for tag in tags:
            tag = tag.strip()
            if tag and tag not in self.tags:
                self.add_tag(tag)
        self.tag_input.clear()

    def add_tag(self, tag):
        self.tags.append(tag)
        tag_label = TagLabel(tag, self)
        tag_label.tag_removed.connect(self.remove_tag)
        self.tag_layout.addWidget(tag_label)
        self.tag_added.emit(tag)

    def remove_tag(self, tag):
        if tag in self.tags:
            self.tags.remove(tag)
            for i in range(self.tag_layout.count()):
                item = self.tag_layout.itemAt(i).widget()
                if isinstance(item, TagLabel) and item.text() == tag:
                    self.tag_layout.removeWidget(item)
                    item.deleteLater()
                    self.tag_removed.emit(tag)
                    break

    def get_tags(self):
        return self.tags

    def set_tags(self, tags):
        self.clear_tags()
        for tag in tags:
            self.add_tag(tag)

    def clear_tags(self):
        while self.tag_layout.count():
            item = self.tag_layout.takeAt(0).widget()
            if item:
                item.deleteLater()
        self.tags = []


class TagLabel(QWidget):
    tag_removed = pyqtSignal(str)

    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.text = text
        self.init_ui()

    def init_ui(self):
        self.layout = QHBoxLayout(self)
        self.label = QLabel(self.text, self)
        self.label.setStyleSheet("background-color: lightblue; border-radius: 5px; padding: 2px 5px;")
        self.remove_button = QPushButton("x", self)
        self.remove_button.setFixedSize(16, 16)
        self.remove_button.setStyleSheet("background-color: red; color: white; border: none; border-radius: 8px;")
        self.remove_button.clicked.connect(self.on_remove)
        self.layout.addWidget(self.label)
        self.layout.addWidget(self.remove_button)

    def on_remove(self):
        self.tag_removed.emit(self.text)
