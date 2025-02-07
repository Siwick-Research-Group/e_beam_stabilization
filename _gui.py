from PyQt5 import QtWidgets, uic, QtGui, QtCore
from PyQt5 import uic
import logging
import sys
import pyqtgraph as pg
import numpy as np
import logging
from collections import deque
from PyQt5.QtWidgets import QFileDialog
import os
from collections import deque

class GuiLogger(logging.Handler, QtCore.QObject):
    appendPlainText = QtCore.pyqtSignal(str)

    def __init__(self, edit):
        super().__init__()
        QtCore.QObject.__init__(self)
        self.edit = edit
        self.edit.setReadOnly(True)
        self.appendPlainText.connect(self.edit.appendPlainText)

    def emit(self, record):
        self.appendPlainText.emit(self.format(record))


class _GuiMainWindow(QtWidgets.QMainWindow):

    save_folder_signal = QtCore.pyqtSignal(str)
    acquire_target_signal = QtCore.pyqtSignal()
    
    def __init__(self, cmd_arg, log_level=logging.DEBUG, *args, **kwargs):
        super().__init__(*args, **kwargs)
        uic.loadUi("tab_template.ui", self)

        gui_logger_handler = GuiLogger(self.textedit)
        gui_logger_handler.setLevel(log_level)
        gui_logger_handler.setFormatter(logging.root.handlers[0].formatter)
        logging.getLogger().addHandler(gui_logger_handler)

        self.dectris_centroids = deque(maxlen=1000)
        self.dectris_intensities = deque(maxlen=1000)


        # Set up plotting page
        # # labels
        self.dist_history.getPlotItem().getAxis("left").setLabel("Offset (mag.)")
        self.int_history.getPlotItem().getAxis("left").setLabel("Image Sum 1")
        # # axis-linkes
        self.int_history.setXLink(self.dist_history)

        # set histogram for pixel values 0 to 255
        self.histogram = self.viewer.getHistogramWidget()
        self.histogram.setHistogramRange(0, 4000)

        self.viewer.cursor_changed.connect(self.update_cursor_info)

        self.centroid_pen = pg.mkPen(cosmetic=True, width=5,
                                     color=pg.mkColor(184, 134, 11, 100))

        # self.centroid_1_lines = [pg.InfiniteLine(
        #     pos=None, angle=135, pen=self.centroid_pen),
        #     pg.InfiniteLine(pos=None, angle=45, pen=self.centroid_pen)]

        self.centroid_lines = [pg.InfiniteLine(
            pos=None, angle=135, pen=self.centroid_pen),
            pg.InfiniteLine(pos=None, angle=45, pen=self.centroid_pen)]

        self.target_pen = pg.mkPen(cosmetic=True, width=5,
                                   color=pg.mkColor(100, 149, 237, 100), dash=[4, 2])

        # self.target_1_lines = [pg.InfiniteLine(
        #     pos=None, angle=0, pen=self.target_pen),
        #     pg.InfiniteLine(pos=None, angle=90, pen=self.target_pen)]

        self.target_lines = [pg.InfiniteLine(
            pos=None, angle=0, pen=self.target_pen),
            pg.InfiniteLine(pos=None, angle=90, pen=self.target_pen)]
        
        self.ellipse_points_scatter = pg.ScatterPlotItem()
        self.viewer.addItem(self.ellipse_points_scatter)

        # self.traj_color = (178, 34, 34, 150)
        # self.traj_2 = pg.ScatterPlotItem()
        # self.traj_2.setBrush(self.traj_color)
        # self.traj_2.setSymbol('x')
        # self.traj_2.setSize(15)

        # self.viewer.getView().addItem(self.traj_2)
        # self.traj_2.setVisible(False)

        [self.viewer.getView().addItem(l) for l in self.centroid_lines]
        [self.viewer.getView().addItem(l) for l in self.target_lines]

        # self.traj_2_data = deque(maxlen=50)

        # self.center_locked_label.setText("Center Locked: 🔴")
        # self.align_label.setText("Alignment: 🔴")
        # self.blocked_label.setText("Blocking: False 🟢")
        
        
        self.init_buttons()

    def plot_ellipse_points(self, points):
        points = points.astype(float)
        points += 0.5
        self.ellipse_points_scatter.clear()
        self.ellipse_points_scatter.addPoints(*points.T)
    
    def acquire_target_dialog(self):
        reply = QtWidgets.QMessageBox.question(
            self,
            "Target Acquiring",
            "NO experiment Running?",
            QtWidgets.QMessageBox.Yes,
            QtWidgets.QMessageBox.No,
        )

        if reply == QtWidgets.QMessageBox.No:
            return 
        if reply == QtWidgets.QMessageBox.Yes:
            self.acquire_target_signal.emit()
            return
        

    def watch_folder_dialog(self):
        dialog = QFileDialog(self, caption='Select Experiment Folder to WATCH')
        dialog.setOption(QtWidgets.QFileDialog.DontUseNativeDialog, False)
        dialog.setFileMode(QtWidgets.QFileDialog.Directory)
        dialog.setOption(QtWidgets.QFileDialog.ShowDirsOnly, True)
        dialog.setLabelText(QtWidgets.QFileDialog.Accept, "Select Folder")
        if dialog.exec_():
            folders = dialog.selectedFiles()
            self.watch_folder = folders[0]
            self.save_folder_signal.emit(self.watch_folder)
            self.update_watch_folder()


    def update_watch_folder(self):
        logging.info("update watch folder")
        _dis_ls = []
        
        # _dis_ls.append()
        try:
            _dis_ls.append(self.watch_folder)
            self.select_folder_button.setFont(QtGui.QFont('Times', weight=QtGui.QFont.Bold))
            self.select_folder_button.setText(os.path.basename(self.watch_folder))
            
        except AttributeError:
            _dis_ls.append('❌')
            
        str_display = 'Folder:  {0}'.format(*_dis_ls)
        self.folder_label.setText(str_display)
        
    # @ QtCore.pyqtSlot(np.ndarray)
    # def update_cam_image(self, image):
    #     '''Updates image viewer 1 and 2 separately. If any of them is none, put blank'''
    #     self.image_1 = image

    #     self.viewer_1.clear()
    #     self.viewer_1.setImage(self.image_1, autoRange=False, autoLevels=False,
    #                            autoHistogramRange=False)

    @ QtCore.pyqtSlot(np.ndarray)
    def update_dectris_image(self, image):
        '''Updates image viewer 1 and 2 separately. If any of them is none, put blank'''
        self.image = image

        self.viewer.clear()
        self.viewer.setImage(self.image, autoRange=False, autoLevels=False,
                               autoHistogramRange=False)


    @ QtCore.pyqtSlot(np.ndarray)
    def update_dectris_centroid(self, centroid):
        self.dectris_centroids.append(centroid)
        
        if True not in np.isnan(centroid):
            [l.setPos(centroid) for l in self.centroid_lines]
            
            
    @ QtCore.pyqtSlot(list)
    def update_dectris_target(self, target):
        t2 = target
        [l.setPos(t2) for l in self.target_lines]

    # @ QtCore.pyqtSlot(list)
    # def new_target(self, targets):
    #     self.target1, self.target2 = targets

    def _check_centroids(self, state):
        
        if state == QtCore.Qt.Checked:
            # [l.setVisible(True) for l in self.centroid_1_lines]
            [l.setVisible(True) for l in self.centroid_lines]

        else:
            # [l.setVisible(False) for l in self.centroid_1_lines]
            [l.setVisible(False) for l in self.centroid_lines]

    # def _check_trajectories(self, state):
        
    #     if state == QtCore.Qt.Checked:
    #         self.traj_1.setVisible(True)
    #         self.traj_2.setVisible(True)

    #     else:
    #         self.traj_1.setVisible(False)
    #         self.traj_2.setVisible(False)

    def update_cursor_info(self, pos):
        x, y = pos
        """Determine cursor information from mouse event."""
        self.cursor_info_label.setText(
            f"Position: ({x},{y})"
        )

    def init_buttons(self):
        self.lock_cbox.stateChanged.connect(self._check_lock)
        self.centroids_cbox.stateChanged.connect(self._check_centroids)
        # self.trajectories_cbox.stateChanged.connect(self._check_trajectories)
        self.watch_folder_btn.clicked.connect(self.watch_folder_dialog)
        self.set_target_btn.clicked.connect(self.acquire_target_dialog)



    # @QtCore.pyqtSlot(bool)
    # def update_center_locked_label(self, state):
    #     if state == True:
    #         self.center_locked_label.setText("Center Locked: 🟢")
    #     else:
    #         self.center_locked_label.setText("Center Locked: 🔴")

    @QtCore.pyqtSlot(bool)
    def update_align_label(self, state):
        if state == True:
            self.align_label.setText("Alignment: 🟢")
        else:
            self.align_label.setText("Alignment: 🔴")

    # @QtCore.pyqtSlot(bool)
    # def update_blocked_label(self, state):
    #     if state == True:
    #         self.blocked_label.setText("Blocking: DETECTED 🔴")
    #     else:
    #         self.blocked_label.setText("Blocking: NOT 🟢")

    def _check_lock(self):
        pass
    
    def _check_centroids(self):
        pass
    
    def _check_trajectories(self):
        pass


if __name__ == "__main__":
    app = QtWidgets.QApplication([])
    win = _GuiMainWindow(None)
    win.show()
    sys.exit(app.exec_())
