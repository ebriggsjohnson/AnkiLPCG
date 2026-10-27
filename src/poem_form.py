"""Native Qt form: no generated PyQt files required to package the add-on."""
from aqt.qt import (QVBoxLayout, QFormLayout, QHBoxLayout, QWidget, QLineEdit,
                    QSpinBox, QPlainTextEdit, QPushButton, QComboBox, QLabel)


class Ui_Dialog:
    def setupUi(self, dialog):
        dialog.setWindowTitle('LPCG – Poem editor')
        dialog.resize(620, 720)
        layout = QVBoxLayout(dialog)
        self.deckChooser = QWidget(dialog)
        layout.addWidget(self.deckChooser)
        fields = QFormLayout()
        layout.addLayout(fields)
        for name, label in [('titleBox', 'Title'), ('authorBox', 'Author'), ('tagsBox', 'Tags')]:
            widget = QLineEdit(dialog)
            setattr(self, name, widget)
            fields.addRow(label, widget)
        for name, label, minimum, maximum in [
            ('contextLinesSpin', 'Lines of context', 1, 20),
            ('reciteLinesSpin', 'Lines to recite', 1, 10),
            ('groupLinesSpin', 'Lines per group', 1, 10),
        ]:
            widget = QSpinBox(dialog)
            widget.setRange(minimum, maximum)
            setattr(self, name, widget)
            fields.addRow(label, widget)
        self.modeBox = QComboBox(dialog)
        self.modeBox.addItem('Breakdown', 'breakdown')
        self.modeBox.addItem('Full poem', 'full')
        fields.addRow('Review mode', self.modeBox)
        self.textBox = QPlainTextEdit(dialog)
        layout.addWidget(self.textBox)
        layout.addWidget(QLabel('Save updates all notes.', dialog))
        buttons = QHBoxLayout()
        layout.addLayout(buttons)
        for name, label in [('helpButton', 'Help'), ('openFileButton', 'Open file'),
                            ('addCardsButton', 'Save poem'), ('cancelButton', 'Cancel')]:
            button = QPushButton(label, dialog)
            setattr(self, name, button)
            buttons.addWidget(button)
        self.addCardsButton.setDefault(True)
