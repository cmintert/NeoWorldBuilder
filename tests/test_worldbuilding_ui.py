import pytest
from unittest.mock import Mock
from PyQt6.QtWidgets import QApplication, QLineEdit, QTableWidgetItem, QComboBox
from src.main import WorldBuildingUI, WorldBuildingController

@pytest.fixture
def app():
    return QApplication([])

@pytest.fixture
def controller():
    return Mock(spec=WorldBuildingController)

@pytest.fixture
def ui(controller):
    return WorldBuildingUI(controller)

def test_worldbuilding_ui_initialization(ui):
    assert ui.controller is not None
    assert ui.name_input is not None
    assert ui.description_input is not None
    assert ui.labels_input is not None
    assert ui.tags_input is not None
    assert ui.properties_table is not None
    assert ui.relationships_table is not None
    assert ui.image_label is not None

def test_worldbuilding_ui_clear_all_fields(ui):
    ui.name_input.setText("Test Name")
    ui.description_input.setPlainText("Test Description")
    ui.labels_input.setText("Label1, Label2")
    ui.tags_input.setText("Tag1, Tag2")
    ui.properties_table.setRowCount(1)
    ui.relationships_table.setRowCount(1)
    ui.image_label.setText("Test Image")

    ui.clear_all_fields()

    assert ui.name_input.text() == "Test Name"  # Name should not be cleared
    assert ui.description_input.toPlainText() == ""
    assert ui.labels_input.text() == ""
    assert ui.tags_input.text() == ""
    assert ui.properties_table.rowCount() == 0
    assert ui.relationships_table.rowCount() == 0
    assert ui.image_label.text() == ""

def test_worldbuilding_ui_set_image(ui):
    ui.set_image("src/test_image.png")
    assert ui.image_label.pixmap() is not None

    ui.set_image(None)
    assert ui.image_label.pixmap() is None

def test_worldbuilding_ui_add_relationship_row(ui):
    initial_row_count = ui.relationships_table.rowCount()
    ui.add_relationship_row("TestType", "TestTarget", ">", "{}")

    assert ui.relationships_table.rowCount() == initial_row_count + 1
    assert ui.relationships_table.item(initial_row_count, 0).text() == "TestType"
    assert isinstance(ui.relationships_table.cellWidget(initial_row_count, 1), QLineEdit)
    assert ui.relationships_table.cellWidget(initial_row_count, 1).text() == "TestTarget"
    assert isinstance(ui.relationships_table.cellWidget(initial_row_count, 2), QComboBox)
    assert ui.relationships_table.cellWidget(initial_row_count, 2).currentText() == ">"
    assert ui.relationships_table.item(initial_row_count, 3).text() == "{}"

def test_worldbuilding_ui_add_property_row(ui):
    initial_row_count = ui.properties_table.rowCount()
    ui.add_property_row()

    assert ui.properties_table.rowCount() == initial_row_count + 1
    assert ui.properties_table.cellWidget(initial_row_count, 2) is not None
