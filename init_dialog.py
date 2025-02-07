from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from datetime import datetime


class InitDialog(QWidget):

    def __init__(self, parent=None):

        super(InitDialog, self).__init__(parent)
        # self.setAttribute(Qt.WA_DeleteOnClose)

        self.useTime = True
        self.fullName = ""

        layout = QFormLayout()
        self.customLabel = QLabel("User Label")

        self.customEdit = QLineEdit()
        self.customEdit.textChanged.connect(self.genName)

        self.timeLabel = QLabel()
        self.getTime()
        self.getTimeButton = QPushButton("Get time")
        self.getTimeButton.clicked.connect(self.getTime)
        self.getTimeButton.clicked.connect(self.genName)

        self.fullNameLabel = QLabel("Logging folder name: ")

        self.timeCbox = QCheckBox("Use Time Label")
        self.timeCbox.setChecked(True)
        self.timeCbox.stateChanged.connect(self.useTimeState)

        layout.addRow(self.customLabel, self.customEdit)
        layout.addRow(self.getTimeButton, self.timeLabel)
        layout.addRow(self.timeCbox)
        layout.addRow(self.fullNameLabel)

        self.setLayout(layout)
        self.setWindowTitle("Run Logging Initialization")
        self.genName()

    def useTimeState(self, state):
        if state == Qt.Checked:
            self.useTime = True
            self.genName()
        else:
            self.useTime = False
            self.genName()

    def genName(self):
        text = self.customEdit.text()

        if text == "" and self.useTime == False:
            self.fullNameLabel.setText("(Use time or enter a label)")
            return

        fullName = self.customEdit.text()

        if text == "" and self.useTime == True:
            self.fullNameLabel.setText(self.timeLabel.text())

            self.fullName = self.timeLabel.text()+'/'
            return

        fullName += "_" + self.timeLabel.text()+'/'

        self.fullName = fullName
        self.fullNameLabel.setText(fullName)

    def getTime(self):
        t_init = datetime.now()
        t_str = t_init.strftime('%Y_%m_%d_%H_%M_%a')
        self.timeLabel.setText(t_str)

    def getName(self):
        return self.fullName
