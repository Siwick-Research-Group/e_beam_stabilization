from time import localtime, strftime, time
from PyQt5 import QtCore, QtWidgets, QtGui
from collections import deque
from copy import copy, deepcopy
import logging as log
import weakref
import pyqtgraph as pg
from pyqtgraph.Qt import QtGui, QtWidgets
from pyqtgraph.graphicsItems.ViewBox.ViewBoxMenu import ui_template
import numpy as np
from PyQt5.QtCore import pyqtSignal, pyqtSlot


class ImageViewWidget(pg.ImageView):
    x_size = 0
    y_size = 0
    image = None
    cursor_changed = pyqtSignal(tuple)

    def __init__(self, parent=None, cmap="grey"):
        log.debug("initializing ImageViewWidget")
        super().__init__()
        self.setParent(parent)
        self.setPredefinedGradient(cmap)
        self.setLevels(0, 255)
        self.view.invertY(True)
        self.view.setAspectLocked(True)
        self.view.setBackgroundColor('grey')

        self.proxy = pg.SignalProxy(
            self.scene.sigMouseMoved, rateLimit=60, slot=self.__callback_move
        )

        self.max_label = pg.LabelItem(justify="right")
        # self.frame_top = pg.InfiniteLine(angle=0, movable=False)
        # self.frame_bottom = pg.InfiniteLine(angle=0, movable=False)
        # self.frame_left = pg.InfiniteLine(angle=90, movable=False)
        # self.frame_right = pg.InfiniteLine(angle=90, movable=False)
        # self.frames = [
        #     self.frame_top,
        #     self.frame_bottom,
        #     self.frame_left,
        #     self.frame_right,
        # ]

        # self.crosshair_h = pg.InfiniteLine(angle=45, movable=False)
        # self.crosshair_v = pg.InfiniteLine(angle=135, movable=False)

        self.addItem(self.max_label)
        
        colors = [
            (0, 0, 0),
            (4, 5, 61),
            (84, 42, 55),
            (15, 87, 60),
            (208, 17, 141),
            (255, 255, 255)
        ]
 
        # color map
        cmap = pg.ColorMap(pos=np.linspace(0.0, 1.0, 6), color=colors)
 
        # setting color map to the image view
        self.setColorMap(cmap)

    def setImage(self, raw_image, *args, max_label=True, **kwargs):
        self.image = raw_image

        self.x_size, self.y_size = self.image.shape[:2]

        if max_label:
            self.max_label.setText(
                f'<span style="font-size: 32pt">{int(self.image.max())}</span>'
            )
        else:
            self.max_label.setText("")

        super().setImage(
            self.image,
            *args,
            **kwargs,
        )

    @pyqtSlot(tuple)
    def __callback_move(self, evt):
        """
        callback function for mouse movement on image
        """
        qpoint = self.view.mapSceneToView(evt[0])
        x = int(qpoint.x())
        y = int(qpoint.y())
        if x < 0 or x >= self.x_size:
            self.cursor_changed.emit((np.nan, np.nan))
            return
        if y < 0 or y >= self.y_size:
            self.cursor_changed.emit((np.nan, np.nan))
            return
        self.cursor_changed.emit((x, y))

    # @pyqtSlot(bool)
    # def show_frame(self, state):
    #     if state:
    #         self.frame_top.setPos(self.y_size)
    #         self.frame_bottom.setPos(0)
    #         self.frame_left.setPos(0)
    #         self.frame_right.setPos(self.x_size)
    #         for f in self.frames:
    #             self.addItem(f)
    #         return
    #     items_in_view = copy(self.view.addedItems)
    #     for i in items_in_view:
    #         if isinstance(i, pg.InfiniteLine):
    #             if i.angle in [0, 90]:
    #                 try:
    #                     self.view.addedItems.remove(i)
    #                     self.view.removeItem(i)
    #                 except ValueError:
    #                     pass

    # @pyqtSlot(bool)
    # def show_crosshair(self, state):
    #     if state:
    #         self.crosshair_h.setPos((self.x_size / 2, self.y_size / 2))
    #         self.addItem(self.crosshair_h)
    #         self.crosshair_v.setPos((self.x_size / 2, self.y_size / 2))
    #         self.addItem(self.crosshair_v)
    #         return
    #     items_in_view = copy(self.view.addedItems)
    #     for i in items_in_view:
    #         if isinstance(i, pg.InfiniteLine):
    #             if i.angle in [45, 135]:
    #                 try:
    #                     self.view.addedItems.remove(i)
    #                     self.view.removeItem(i)
    #                 except ValueError:
    #                     pass


class TimeAxisItem(pg.AxisItem):
    """ Displays the time in H:M for HistoryPlot widgets """

    def tickStrings(self, values, scale, spacing):
        try:
            return [strftime("%H:%M", localtime(value)) for value in values]
        # When scrolling quickly and nothign is plotted, something raises an OSError
        # This will only come into play when the gun is not connected.
        except OSError:
            return list(range(len(values)))


class RecentHistoryPlotWidget(pg.PlotWidget):
    """ 
    Plots the recent history of a measurement. 
    """

    def __init__(self, maxlen, ylabel="", *args, **kwargs):
        """
        Parameters
        ----------
        maxlen : int
            Maximum number of data points to show. 
        """
        super().__init__(
            axisItems={"bottom": TimeAxisItem(orientation="bottom")}, *args, **kwargs
        )

        # Data containers
        self.times = list()
        self.measurements = list()

        self.getPlotItem().getAxis("left").setLabel(ylabel)
        # self.getPlotItem().getAxis("bottom").setLabel("Local time (HH:MM)")

        self._measurements_data_item = pg.PlotDataItem(
            symbol="o",
            symbolBrush=pg.mkBrush("r"),
            symbolPen=None,
            pen=None,
            symbolSize=3,
            connect='finite'
        )
        self.addItem(self._measurements_data_item)

    @QtCore.pyqtSlot(float, float)
    def add_measurement(self, unix_time, measurement):
        """
        Add a measurement to the plot.
        Parameters
        ----------
        unix_time : float
            Epoch time in seconds
        measurement: float
            Measurement value.
        """
        self.times.append(unix_time)
        self.measurements.append(measurement)

        self._measurements_data_item.setData(
            x=np.array(self.times), y=np.array(self.measurements)
        )

    @QtCore.pyqtSlot()
    def clear(self):
        """ Clear plot """
        self._measurements_data_item.clear()



# class SettingsLabel(QtWidgets.QLabel):
#     def __init__(self, parent=None):
#         super().__init__(parent)
#         self.bf = QtGui.QFont()
#         self.bf.setBold(True)
#         self.nf = QtGui.QFont()
#         self.nf.setBold(False)

#     def bold(self):
#         self.setFont(self.bf)

#     def normal(self):
#         self.setFont(self.nf)
