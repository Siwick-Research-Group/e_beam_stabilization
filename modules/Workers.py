"""
collection of workers. The workers are threadded so they won't affect the main-window.
Use emit to interact with main-window
"""

from time import sleep
import logging
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QObject, QThread,QFileSystemWatcher
import numpy as np
from collections import deque
from enum import IntEnum
import h5py
import warnings
from modules.utils import monitor_to_array
from modules.center_finder import find_image_center
from uedinst.dectris import Quadro
from . import IP, PORT 
from time import time

from glob import glob
import os
import sys 
from PyQt5 import QtWidgets


class FolderWatcherWorker(QFileSystemWatcher):
    """
    Class that watches a folder for new HDF5 images and processes them in a non-blocking fashion.
    """

    image_ready = pyqtSignal(np.ndarray)
    new_file_ready = pyqtSignal(str)
    ellipse_points_ready = pyqtSignal(np.ndarray)
    centroid_ready = pyqtSignal(np.ndarray)

    def __init__(self):
        super().__init__()

        self.worker_thread = QThread()
        self.moveToThread(self.worker_thread)
        self.worker_thread.start()

        self.logger = logging.getLogger("folder_watcher")
        self.logger.info(f"Folder watcher thread: {self.worker_thread.currentThreadId()}")
        self.directoryChanged.connect(self.find_newest_file)
        self.new_file_ready.connect(self.process_image)
        
        self.latest_file = None
        self.snapshot = []
        self.experiment_path = None
            
        self.centroids = deque(maxlen=5)
    
    def add_centroid_to_deque(self, centroid):
        self.centroids.append(centroid)
        if len(self.centroids) == self.centroids.maxlen:
            avg = np.mean(self.centroids, axis=0)
            self.logger.info(f'Centroid found from {self.centroids.maxlen} imgs: {avg}'.ljust(25))
            self.centroid_ready.emit(avg)
            self.centroids.clear()

    def david_find_newest_file(self):
        # Find files from the folders you care about ...
        sub_folders = []
        sub_folders.append(os.path.join(self.experiment_path,'pump_off'))
        sub_folders.extend(glob(os.path.join(self.experiment_path,'scan_*')))

        files = []
        for sub_directory in sub_folders:
            files.extend(glob(os.path.join(sub_directory, '*.h5')))
        
        try:
            _latest_file = max(files, key=os.path.getctime)
        except ValueError:
            self.logger.error("One of the files Not Found while sorting by creation time.")
        if _latest_file != self.latest_file and _latest_file not in self.snapshot:
            self.new_file_ready.emit(_latest_file)
            # self.logger.info(f'{_latest_file}')
            self.latest_file = _latest_file
            self.snapshot = files


    def find_newest_file(self, path):
        if os.path.isdir(path):
            subdirs = [os.path.join(path, d) for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))]
            if subdirs:
                path = max(subdirs, key=os.path.getmtime)
            if "scan" in os.path.basename(path):
                if "scan" in os.path.basename(self.directories()[-1]) and int(os.path.basename(self.directories()[-1])[5:]) != int(os.path.basename(path)[5:]):
                    self.removePath(self.directories()[-1])
                self.addPath(os.path.join(self.experiment_path, os.path.basename(path)))

            try:
                if sum(1 for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))) > 0 and ("pump_off" in path or "scan" in path):
                    _latest_file = max(glob(os.path.join(path, '*.h5')), key=os.path.getctime)
                    if _latest_file != self.latest_file:
                        self.new_file_ready.emit(_latest_file)
                        self.latest_file = _latest_file
                        # self.logger.info(f"{_latest_file}: detected.")

            except ValueError:
                self.logger.error("One of the files Not Found while sorting by creation time.")
        

    @ pyqtSlot(str)
    def update_folder_watched(self,new_experiment_path = None):
        if self.directories:
            [self.removePath(p) for p in self.directories()]
        
        if new_experiment_path != None:
            self.experiment_path = new_experiment_path
        self.addPath(self.experiment_path)
        self.addPath(os.path.join(self.experiment_path, "pump_off"))

        
        
    @ pyqtSlot(str)
    def process_image(self, file_path):
        # self.logger.info('Processing Image.')
        mask = np.rot90(~(np.load('log/full_dectris_mask.npy').astype(bool)), k=3)
        sleep(.5)
        try:
            with h5py.File(file_path, 'r') as f:
                image = f['entry/data/data'][...].squeeze()  # Extract the (1,512,512) image
                exposure = f['entry/instrument/detector/count_time'][...] # normalize the intensity to 1 second
                # exposure = exposure.astype(np.uint32)
                image = image.astype(np.float64)
                image /= exposure
                image = np.rot90(image, k=3) * mask


        except Exception as e:
            self.logger.error(f"Error reading file {file_path}: {e}")
            return

        self.image_ready.emit(image)
        try:
            center, pts_fitted = find_image_center(image)
            self.ellipse_points_ready.emit(pts_fitted)
            # self.logger.info(f"center is {center}")
        except Exception as e:
            self.logger.error(f"Error finding centroid in {file_path}: {e}")
            return  
        
        self.add_centroid_to_deque(center)

    def __del__(self):
        pass
    
        


class MOTOR_TYPES(IntEnum):
    NO_MOTOR = 0
    MOTOR_UKNOWN = 1
    TINY = 2
    STANDARD = 3

import numpy as np
import logging
from PyQt5.QtCore import QObject, QThread, pyqtSignal, pyqtSlot
from time import sleep

class AlignWorker(QObject):
    """
    Worker that aligns a single mirror based on centroid data from FolderWatcherWorker.
    Also acquires motion matrix based on DectrisImageGrabber
    """
    
    alignment_done = pyqtSignal()
    
    image_ready = pyqtSignal(np.ndarray)
    centroid_ready = pyqtSignal(np.ndarray)
    target_ready = pyqtSignal(list)
    ellipse_points_ready = pyqtSignal(np.ndarray)
    
    def __init__(self, motor_controller=None):
        super().__init__()
        
        self.motor_controller = motor_controller
        
        self.MOTOR_CHANNELS = [3,4]
        self.MOTOR_TYPE = MOTOR_TYPES.TINY
        self.MOTOR_VELOCITY = 100  # was 1750
        self.MOTOR_ACCELERATION = 1000  # was 100_000

        if self.motor_controller !=None:
            for m_channel in self.MOTOR_CHANNELS:
                self.motor_controller.set_type(m_channel, self.MOTOR_TYPE)
                self.motor_controller.set_velocity(m_channel, self.MOTOR_VELOCITY)
                self.motor_controller.set_acceleration(m_channel, self.MOTOR_ACCELERATION)
        
        self.worker_thread = QThread()
        self.moveToThread(self.worker_thread)
        self.worker_thread.start()
        
        self.logger = logging.getLogger("align_worker")
        self.logger.info(f"Alignment worker thread: {self.worker_thread.currentThreadId()}")
        self.load_motion_matrix()
        self.load_target()
        
        
    @pyqtSlot(np.ndarray)
    def align(self, centroid):
        """
        Align the mirror based on the centroid position.
        """
        if np.any(np.isnan(centroid)):
            self.logger.warning("Centroid contains NaN values, skipping alignment.")
            return
        
        offsets = self.target - centroid
        
        motor_movements = self.mm @ offsets  # Adjust movement based on x-axis
        
        self.logger.info(f"Offset = {offsets}")
        self.logger.info(f"motor move = {motor_movements}")

        if np.linalg.norm(offsets) > 5:
            return
        
        for m_channel, m_move in zip(self.MOTOR_CHANNELS, motor_movements):
            self.__move_rel(m_channel, m_move)
    
    @ pyqtSlot()
    def load_motion_matrix(self):
        """Ideally this would prompt you select a file."""
        try:
            self.mm = np.loadtxt(
                './config_data/motion_matrix.txt', dtype=float)

            self.logger.info('Motion matrix located. Entries:\n' +
                             f'{self.mm}')
        except FileNotFoundError:
            print("No file found with name 'motion_matrix.txt'.")

            self.logger.info('Motion matrix NOT FOUND.')
            return False

        return True
    
    
    @ pyqtSlot()
    def load_target(self):
        """Ideally this would prompt you select a file."""
        try:
            self.target = np.loadtxt(
                './config_data/target.txt', dtype=float)

            self.logger.info('Target located. Entries:\n' +
                             f'{self.target}')
        except FileNotFoundError:

            self.logger.info('Target NOT FOUND.')
            return False

        return True
    
    
    @pyqtSlot()
    def acquire_motion_matrix(self, n_sample=1):
        self.logger.info("Acquiring motion matrix...")
        
        self.connect_dectris()
        
        mm = np.zeros((n_sample, 2, 2))

        AMM_STEP = 100

        for idn in range(n_sample):
            mm_n = np.zeros((2, 2))
            for i, m_channel in enumerate(self.MOTOR_CHANNELS):
                self.logger.debug("NEGATIVE Moving motor channel " + f"{m_channel} ")
                negative_move = -AMM_STEP
                self.__move_rel(m_channel, negative_move)
                image1 = self.get_dectris_image()
                self.image_ready.emit(image1)
                
                centroid1, _ = find_image_center(image1)
                
                self.centroid_ready.emit(centroid1)
            ############################################################################################################
                self.logger.debug("POSITIVE Moving motor channel " + f"{m_channel} ")
                positive_move = 2 * AMM_STEP
                self.__move_rel(m_channel, positive_move)
                image2 = self.get_dectris_image()
                self.image_ready.emit(image2)
                centroid2, _ = find_image_center(image2)
                self.centroid_ready.emit(centroid2)
                for j, (new_pos, old_pos) in enumerate(zip(centroid2, centroid1)):
                    mm_n[j, i] = (new_pos - old_pos) / AMM_STEP

                self.__move_rel(m_channel, -AMM_STEP)

            mm[idn] = mm_n
            

        self.mm = np.linalg.inv(np.average(mm, axis=0))
        self.logger.info("New motion matrix: \n" + f"{self.mm}")
        self.disconnect_dectris()
        
        
    @pyqtSlot()
    def acquire_target(self):
        q = self.connect_dectris()
        centroid = np.array([np.nan, np.nan])
        
        while np.any(np.isnan(centroid)):
            image = self.get_dectris_image()
            self.image_ready.emit(image)
            centroid, pts_fitted = find_image_center(image)
            self.ellipse_points_ready.emit(pts_fitted)
            self.logger.info('nan centroid found, retrying...')
        self.disconnect_dectris()
        self.centroid_ready.emit(centroid)
        self.target = centroid
        self.save_target()
    
    def save_target(self):
        try:
            target_dir = './config_data/target.txt'
            np.savetxt(target_dir, self.target)
            self.logger.info(f"Target Saved @: {self.target}")
            return True
        except AttributeError:
            self.logger.info(f"Trying to save target but no target yet.")
            return False
    
    

    @ pyqtSlot()
    def save_motion_matrix(self):
        try:
            mm_dir = './config_data/motion_matrix.txt'
            np.savetxt(mm_dir, self.mm)
            self.logger.info(f"Motion matrix SAVED to {mm_dir}.")
            return True
        except AttributeError:
            self.logger.info(f"Trying to save motion matrix but no MM yet!")
            return False
    
    def __move_rel(self, motor_channel, dist, blocked=True):
        if abs(dist) >=0.5:
            dist = int(np.rint(dist))
            self.motor_controller.set_relative(motor_channel, dist)

        if blocked:
            while not self.motor_controller.done(motor_channel):
                sleep(0.1)
            sleep(0.1)


    def connect_dectris(self,exposure_sec = 1):
        q = Quadro(
            IP,
            PORT
        )
        try:
            _ = q.state
            self.logger.info(f"Direct Connection to Detris Established")
        except OSError:
            self.logger.warning("DectrisImageGrabber could not establish connection to detector")
    
        # prepare the hardware for taking images
        if q.state == "na":
            self.logger.info('Dectris not initialized.')
            exit()
    
        q.mon.clear()
        q.fw.clear()
        q.fw.mode = "disabled"
        q.mon.mode = "enabled"
        q.incident_energy = 1e5
        q.count_time = exposure_sec
        q.frame_time = exposure_sec
        q.trigger_mode = 'ints'
        q.ntrigger = 1
        self.q = q
    
    def get_dectris_image(self):
        self.q.mon.clear()
        self.q.ntrigger = 1
        self.q.arm()
        # logic for different trigger modes
        if self.q.trigger_mode == "ints":
            self.q.trigger()
            sleep(0.1)
            while self.q.state != "idle":
                sleep(0.05)
            sleep(0.5)
            self.q.disarm()
        dectris_img = monitor_to_array(self.q.mon.last_image)
        self.q.mon.clear()
        return dectris_img
    
    def disconnect_dectris(self):
        del(self.q)
        
            
            
if __name__ == "__main__":
    try:
        print("yay")
        app = QtWidgets.QApplication([])
        watcher = FolderWatcherWorker('.')
        print("Watcher created.")
        
        sys.exit(app.exec_())
    except KeyboardInterrupt:
        sys.exit()
    
    