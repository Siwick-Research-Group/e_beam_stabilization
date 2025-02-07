import numpy as np
import cv2
from collections import deque
from pyueye import ueye
import numpy as np


class uEyeCamera:
    def __init__(self, HID=0):
        # ---------------------------------------------------------------------------------------------------------------------------------------
        # Variables
        # 0: first available camera;  1-254: The camera with the specified camera ID
        self.hCam = ueye.HIDS(HID)
        self.sInfo = ueye.SENSORINFO()
        self.cInfo = ueye.CAMINFO()
        self.pcImageMemory = ueye.c_mem_p()
        self.MemID = ueye.int()
        self.rectAOI = ueye.IS_RECT()
        self.pitch = ueye.INT()
        # 24: bits per pixel for color mode; take 8 bits per pixel for monochrome
        self.nBitsPerPixel = ueye.INT(24)
        # 3: channels for color mode(RGB); take 1 channel for monochrome
        self.channels = 3
        self.m_nColorMode = ueye.INT()       # Y8/RGB16/RGB24/REG32
        self.bytes_per_pixel = int(self.nBitsPerPixel / 8)
        self.pixelclock = ueye.UINT()
        # ---------------------------------------------------------------------------------------------------------------------------------------
        # print("START")
        # print()

        # Starts the driver and establishes the connection to the camera
        self.nRet = ueye.is_InitCamera(self.hCam, None)
        if self.nRet != ueye.IS_SUCCESS:
            print("is_InitCamera ERROR")

        # Reads out the data hard-coded in the non-volatile camera memory and writes it to the data structure that cInfo points to
        self.nRet = ueye.is_GetCameraInfo(self.hCam, self.cInfo)
        if self.nRet != ueye.IS_SUCCESS:
            print("is_GetCameraInfo ERROR")

        # You can query additional information about the sensor type used in the camera
        self.nRet = ueye.is_GetSensorInfo(self.hCam, self.sInfo)
        if self.nRet != ueye.IS_SUCCESS:
            print("is_GetSensorInfo ERROR")

        self.nRet = ueye.is_ResetToDefault(self.hCam)
        if self.nRet != ueye.IS_SUCCESS:
            print("is_ResetToDefault ERROR")

        # Set display mode to DIB
        self.nRet = ueye.is_SetDisplayMode(self.hCam, ueye.IS_SET_DM_DIB)

        # Set the right color mode
        if int.from_bytes(self.sInfo.nColorMode.value, byteorder='big') == ueye.IS_COLORMODE_BAYER:
            # setup the color depth to the current windows setting
            ueye.is_GetColorDepth(
                self.hCam, self.nBitsPerPixel, self.m_nColorMode)
            self.bytes_per_pixel = int(self.nBitsPerPixel / 8)
            # print("IS_COLORMODE_BAYER: ", )
            # print("\tm_nColorMode: \t\t", self.m_nColorMode)
            # print("\tnBitsPerPixel: \t\t", self.nBitsPerPixel)
            # print("\tbytes_per_pixel: \t\t", self.bytes_per_pixel)
            # print()

        elif int.from_bytes(self.sInfo.nColorMode.value, byteorder='big') == ueye.IS_COLORMODE_CBYCRY:
            # for color camera models use RGB32 mode
            self.m_nColorMode = ueye.IS_CM_BGRA8_PACKED
            self.nBitsPerPixel = ueye.INT(32)
            self.bytes_per_pixel = int(self.nBitsPerPixel / 8)
            # print("IS_COLORMODE_CBYCRY: ", )
            # print("\tm_nColorMode: \t\t", self.m_nColorMode)
            # print("\tnBitsPerPixel: \t\t", self.nBitsPerPixel)
            # print("\tbytes_per_pixel: \t\t", self.bytes_per_pixel)
            # print()

        elif int.from_bytes(self.sInfo.nColorMode.value, byteorder='big') == ueye.IS_COLORMODE_MONOCHROME:
            # for color camera models use RGB32 mode
            self.m_nColorMode = ueye.IS_CM_MONO8
            self.nBitsPerPixel = ueye.INT(8)
            self.bytes_per_pixel = int(self.nBitsPerPixel / 8)
            # print("IS_COLORMODE_MONOCHROME: ", )
            # print("\tm_nColorMode: \t\t", self.m_nColorMode)
            # print("\tnBitsPerPixel: \t\t", self.nBitsPerPixel)
            # print("\tbytes_per_pixel: \t\t", self.bytes_per_pixel)
            # print()

        else:
            # for monochrome camera models use Y8 mode
            self.m_nColorMode = ueye.IS_CM_MONO8
            self.nBitsPerPixel = ueye.INT(8)
            self.bytes_per_pixel = int(self.nBitsPerPixel / 8)
            # print("else")

        # Can be used to set the size and position of an "area of interest"(AOI) within an image
        # self.nRet = ueye.is_AOI(self.hCam, ueye.IS_AOI_IMAGE_SET_AOI, ueye.IS_RECT(s32X=240, s32Y=212, s32Width=800, s32Height=600), ueye.sizeof(self.rectAOI))
        self.nRet = ueye.is_AOI(
            self.hCam, ueye.IS_AOI_IMAGE_GET_AOI, self.rectAOI, ueye.sizeof(self.rectAOI))
        if self.nRet != ueye.IS_SUCCESS:
            print("is_AOI ERROR")

        self.width = self.rectAOI.s32Width
        self.height = self.rectAOI.s32Height

        # Set PixelClock
        if ueye.is_PixelClock(self.hCam, ueye.IS_PIXELCLOCK_CMD_SET, ueye.UINT(12), ueye.sizeof(self.pixelclock)):
            print('error while setting pixelclock')
        ueye.is_PixelClock(self.hCam, ueye.IS_PIXELCLOCK_CMD_GET,
                           self.pixelclock, ueye.sizeof(self.pixelclock))

        # Prints out some information about the camera and the sensor
        # print("Camera model:\t\t", self.sInfo.strSensorName.decode('utf-8'))
        # print("Camera serial no.:\t", self.cInfo.SerNo.decode('utf-8'))
        # print("Maximum image width:\t", self.width)
        # print("Maximum image height:\t", self.height)

        self.allocate_image_memory()
        # self.centroids = deque(maxlen=1000)
        # self.centroids.append([np.NaN, np.NaN])
        # self.centroids.append([np.NaN, np.NaN])

    def allocate_image_memory(self):
        # ---------------------------------------------------------------------------------------------------------------------------------------

        # Allocates an image memory for an image having its dimensions defined by width and height and its color depth defined by nBitsPerPixel
        self.nRet = ueye.is_AllocImageMem(
            self.hCam, self.width, self.height, self.nBitsPerPixel, self.pcImageMemory, self.MemID)
        if self.nRet != ueye.IS_SUCCESS:
            print("is_AllocImageMem ERROR")
        else:
            # Makes the specified image memory the active memory
            self.nRet = ueye.is_SetImageMem(
                self.hCam, self.pcImageMemory, self.MemID)
            if self.nRet != ueye.IS_SUCCESS:
                print("is_SetImageMem ERROR")
            else:
                # Set the desired color mode
                self.nRet = ueye.is_SetColorMode(self.hCam, self.m_nColorMode)

        # Activates the camera's live video mode (free run mode)
        self.nRet = ueye.is_CaptureVideo(self.hCam, ueye.IS_DONT_WAIT)
        if self.nRet != ueye.IS_SUCCESS:
            print("is_CaptureVideo ERROR")

        # Enables the queue mode for existing image memory sequences
        self.nRet = ueye.is_InquireImageMem(
            self.hCam, self.pcImageMemory, self.MemID, self.width, self.height, self.nBitsPerPixel, self.pitch)
        if self.nRet != ueye.IS_SUCCESS:
            print("is_InquireImageMem ERROR")
        # else:
            # print("Press q to leave the programm")

    def get_image(self):
        array = ueye.get_data(self.pcImageMemory, self.width,
                              self.height, self.nBitsPerPixel, self.pitch, copy=False)
        self.bytes_per_pixel = int(self.nBitsPerPixel / 8)
        # ...reshape it in an numpy array...
        self.frame = np.reshape(
            array, (self.height.value, self.width.value, self.bytes_per_pixel))
        return self.frame

#! Moved to worker object
    # def get_centroid(self):
    #     self.get_image()
    #     try:
    #         MAX = max(np.percentile(self.frame, 99), 127)
    #         ret, thresh = cv2.threshold(self.frame, MAX, 255, 0)
    #         M = cv2.moments(thresh)
    #         try:
    #             self.centroid = np.array(
    #                 [float(M['m01']/M['m00']), float(M['m10']/M['m00'])])
    #         except ZeroDivisionError:
    #             self.centroid = np.array([np.nan, np.nan])
    #         # self.frame = self.get_image()
    #         # m,n, _ = self.frame.shape
    #         # self.centroid = np.unravel_index(np.argmax(self.frame), (m,n))
    #         # print(centroid, self.centroid)
    #     except (RuntimeWarning, ValueError) as e:
    #         self.centroid = np.array([np.nan, np.nan])
    #         pass
    #     self.centroids.append(self.centroid)
    #     return self.centroid

# ! Moved to worker object
    # def get_mean_centroid(self, num_c):
    #     centroids = np.array(self.centroids)
    #     if len(centroids) < num_c:
    #         return np.nanmean(centroids, axis=0)[::-1]
    #     else:
    #         return np.nanmean(centroids[:num_c:-1, :], axis=0)[::-1]

    def __del__(self):
        name = self.sInfo.strSensorName.decode('utf-8')
        # Releases an image memory that was allocated using is_AllocImageMem() and removes it from the driver management
        ueye.is_FreeImageMem(self.hCam, self.pcImageMemory, self.MemID)

        # Disables the hCam camera handle and releases the data structures and memory areas taken up by the uEye camera
        ueye.is_ExitCamera(self.hCam)
        # print(f'Camera {name} closed')
