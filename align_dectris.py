import _gui
from PyQt5 import QtWidgets, QtCore, QtGui
import logging
import sys
from modules import mc
import numpy as np
from modules import Workers
import libusb_package
import usb.core
import usb.backend.libusb1
from datetime import datetime
import threading
from init_dialog import InitDialog
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QHBoxLayout
import os

usb.backend.libusb1.get_backend(
    find_library=libusb_package.find_library)

class StarGuide(_gui._GuiMainWindow):
    align_signal = QtCore.pyqtSignal(bool)

    def __init__(self, cmd_arg, output_folder, *args, **kwargs):
        
        self.t_init = datetime.now()

        self.output_folder = output_folder

        super().__init__(cmd_arg, log_level=logging.INFO, *args, **kwargs)


        self.logger = logging.getLogger("main")
        self.logger.info('Initializing GUI without Hardwares.\n')
        self.logger.info(f'Main Thread ID: {threading.get_ident()}')

        self.mc = mc.NewFocus8742USB.create('0x104d', '0x4000')
        # self.mc = None
        self.folder_watcher = Workers.FolderWatcherWorker()
        self.align_worker = Workers.AlignWorker(motor_controller=self.mc)

        
        self.save_folder_signal.connect(self.folder_watcher.update_folder_watched)

        self.folder_watcher.image_ready.connect(self.update_dectris_image)
        self.folder_watcher.centroid_ready.connect(self.update_dectris_centroid)
        self.folder_watcher.ellipse_points_ready.connect(self.plot_ellipse_points)
        
        self.align_worker.image_ready.connect(self.update_dectris_image)
        self.align_worker.centroid_ready.connect(self.update_dectris_centroid)
        self.align_worker.target_ready.connect(self.update_dectris_target)

        
        self.acquire_btn.clicked.connect(self.align_worker.acquire_motion_matrix)
        self.acquire_target_signal.connect(self.align_worker.acquire_target)
        self.savemm_btn.clicked.connect(self.align_worker.save_motion_matrix)
        
        self.align_signal.connect(self.update_align_label)
        self.align_worker.ellipse_points_ready.connect(self.plot_ellipse_points)

    def _check_lock(self, state):

        if state == QtCore.Qt.Checked:
            self.align_signal.emit(True)
            self.folder_watcher.centroid_ready.connect(self.align_worker.align)
            self.folder_watcher.centroids.clear()
            # self.logger.info("Alignment ENABLED")

        if state == QtCore.Qt.Unchecked:
            self.align_signal.emit(False)
            self.folder_watcher.centroid_ready.disconnect(self.align_worker.align)
            self.folder_watcher.centroids.clear()
            # self.logger.info("Alignment DISABLED")



    def closeEvent(self, evt):
        reply = QtWidgets.QMessageBox.question(
            self,
            "GUI control",
            "Are you sure you want to quit?",
            QtWidgets.QMessageBox.Yes,
            QtWidgets.QMessageBox.No,
        )

        if reply == QtWidgets.QMessageBox.No:
            return evt.ignore()
        self.logger.info(f'GUI close event triggerd with event {evt}')


        # self.cam_worker.cam_worker_thread.quit()
        self.folder_watcher.worker_thread.quit()
        self.align_worker.worker_thread.quit()

        # self.cam_worker.cam_worker_thread.wait()
        self.folder_watcher.worker_thread.wait()
        self.align_worker.worker_thread.wait()
        self.logger.debug('Folder watcher thread exited.')
        super().closeEvent(evt)
        self.logger.debug('_GUI parent object close event triggered.')
        
        

def init_logging(log_folder):
    if os.path.exists(log_folder) != True:
        os.makedirs(log_folder)

    # full log
    logging.basicConfig(filename=f'./{log_folder}/full_log.log',
                        filemode='a',
                        format='%(asctime)s, %(levelname)-8s \
[%(filename)s:%(lineno)d]\n%(message)s\n',
                        datefmt='%Y-%m-%d %I:%M %S %p - %A',
                        level=logging.DEBUG)

    # info log with same format
    info_fh = logging.FileHandler(filename=f'./{log_folder}/info_log.log')
    info_fh.setLevel(logging.INFO)
    info_fh.setFormatter(logging.root.handlers[0].formatter)
    logging.getLogger().addHandler(info_fh)


if __name__ == "__main__":
    app = QtWidgets.QApplication([])
    ex = InitDialog()
    ex.show()
    app.exec_()
    log_folder = './log/' + ex.getName()
    del (ex)
    
    init_logging(log_folder)

    sg = StarGuide(None, output_folder=log_folder)
    sg.show()
    app.exec_()
    sys.exit()
