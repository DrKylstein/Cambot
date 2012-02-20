import sys
from PySide import QtCore
from PySide import QtGui
from maestro import Maestro
import cv
import math

#OpenCV -> Qt code from Rafael Barreto
#http://rafaelbarreto.com/2011/08/27/a-pyqt-widget-for-opencv-camera-preview/
class OpenCVQImage(QtGui.QImage):

    def __init__(self, opencvBgrImg):
        depth, nChannels = opencvBgrImg.depth, opencvBgrImg.nChannels
        if depth != cv.IPL_DEPTH_8U or nChannels != 3:
            raise ValueError("the input image must be 8-bit, 3-channel")
        w, h = cv.GetSize(opencvBgrImg)
        opencvRgbImg = cv.CreateImage((w, h), depth, nChannels)
        # it's assumed the image is in BGR format
        cv.CvtColor(opencvBgrImg, opencvRgbImg, cv.CV_BGR2RGB)
        self._imgData = opencvRgbImg.tostring()
        super(OpenCVQImage, self).__init__(self._imgData, w, h, \
            QtGui.QImage.Format_RGB888)

class CameraDevice(QtCore.QObject):
    
    _DEFAULT_FPS = 30
    new_frame = QtCore.Signal(cv.iplimage)
    
    def __init__(self, camera_id=0, parent=None):
        super(CameraDevice, self).__init__(parent)
        self._camera = cv.CaptureFromCAM(camera_id)
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._queryFrame)
        self._timer.setInterval(100/self.fps)
        
        self.set_paused(False)
        
    def _queryFrame(self):
        frame = cv.QueryFrame(self._camera)
        self.new_frame.emit(frame)
        
    #@property
    def paused(self):
        return not self._timer.isActive()
    #@paused.setter
    def set_paused(self, value):
        if value:
            self._timer.stop()
        else:
            self._timer.start()
    
    @property
    def frame_size(self):
        width = int(cv.GetCaptureProperty(self._camera, cv.CV_CAP_PROP_FRAME_WIDTH))
        height = int(cv.GetCaptureProperty(self._camera, cv.CV_CAP_PROP_FRAME_HEIGHT))
        return (width, height)
        
    @property
    def fps(self):
        fps = int(cv.GetCaptureProperty(self._camera, cv.CV_CAP_PROP_FPS))
        if fps <= 0:
            fps = self._DEFAULT_FPS
        return fps

class CameraWidget(QtGui.QWidget):
    
    new_frame = QtCore.Signal(cv.iplimage)
    
    def __init__(self, camera_device, parent=None):
        super(CameraWidget, self).__init__(parent)
        self._frame = None
        self._camera_device = camera_device
        self._camera_device.new_frame.connect(self._on_new_frame)
        
        width, height = self._camera_device.frame_size
        if width == 0:
            width = 640
        if height == 0:
            height = 480
        self.setMaximumSize(width, height)
        self.setMinimumSize(width, height)
        
    def _on_new_frame(self, frame):
        self._frame = cv.CloneImage(frame)
        self.new_frame.emit(self._frame)
        self.update()
        
    def changeEvent(self, e):
        if e.type() == QtCore.QEvent.EnabledChange:
            if self.isEnabled():
                self._cameraDevice.newFrame.connect(self._on_new_frame)
            else:
                self._cameraDevice.newFrame.disconnect(self._on_new_frame)

    def paintEvent(self, e):
        if self._frame is None:
            return
        painter = QtGui.QPainter(self)
        painter.drawImage(QtCore.QPoint(0, 0), OpenCVQImage(self._frame))
# end of code based on Barreto's work

class Controls(QtGui.QWidget):
    def __init__(self, parent):
        super(Controls, self).__init__(parent)
        self.pan_left_button = QtGui.QPushButton('Pan Left')
        self.pan_right_button = QtGui.QPushButton('Pan Right')
        self.tilt_up_button = QtGui.QPushButton('Tilt Up')
        self.tilt_down_button = QtGui.QPushButton('Tilt Down')
        self.center_button = QtGui.QPushButton('Center')
        #self.pause_camera = QtGui.QCheckBox('Pause')
        self.toggle_face_tracking = QtGui.QCheckBox('Face Tracking')
        
        self.panDial = QtGui.QDial()
        self.tiltDial = QtGui.QDial()
        
        main_layout = QtGui.QVBoxLayout()
        self.setLayout(main_layout)
        main_layout.addWidget(self.panDial)
        main_layout.addWidget(self.tiltDial)
        direction_layout = QtGui.QGridLayout()
        main_layout.addLayout(direction_layout)
        direction_layout.addWidget(self.pan_left_button, 1,0)
        direction_layout.addWidget(self.pan_right_button, 1,2)
        direction_layout.addWidget(self.tilt_up_button, 0,1)
        direction_layout.addWidget(self.tilt_down_button, 2,1)
        direction_layout.addWidget(self.center_button, 1,1)
        main_layout.addWidget(self.toggle_face_tracking)
        


class MainWindow(QtGui.QMainWindow):
    
    def _create_actions(self):
        #self._new_action = QAction("&New", self)
        #self._open_action = QAction("&Open", self)
        #self._save_action = QAction("&Save", self)
        #self._save_as_action = QAction("Save &As", self)
        #self._options_action = QAction("&Options", self)
        self._quit_action = QtGui.QAction("E&xit", self)
        self._quit_action.triggered.connect(self.close)
    
    def _create_menus(self):
        fileMenu = self.menuBar().addMenu("&File")
        #fileMenu.addAction(self._new_action)
        #fileMenu.addAction(self._open_action)
        #fileMenu.addAction(self._save_action)
        #fileMenu.addAction(self._save_as_action)
        fileMenu.addAction(self._quit_action)

        #windowMenu = self.menuBar().addMenu("&Window")

    def _create_toolbars(self):
        pass
    
    def __init__(self):
        QtGui.QMainWindow.__init__(self)
        self._create_actions()
        self._create_menus()
        self._create_toolbars()
        self.controls = Controls(self)
        self.setCentralWidget(self.controls)

class Cambot(QtCore.QObject):
    
    controller = Maestro('/dev/serial/by-id/usb-Pololu_Corporation_Pololu_Micro_Maestro_6-Servo_Controller_00022544-if00', ['pan', 'tilt'])
    pan = controller.servo['pan']
    tilt = controller.servo['tilt']
    CENTER = (1560, 1560)

    def __init__(self, parent):
        super(Cambot, self).__init__(parent)
        self.pan.minimum = 720
        self.pan.minimum = 2300
        self.pan.speed = 0.8
        self.pan.acceleration = 0.005
        self.pan.range = 160

        self.tilt.minimum = 720
        self.tilt.minimum = 2300
        self.tilt.speed = 0.8
        self.tilt.acceleration = 0.005
        self.tilt.range = 160
        
    def pan_left(self):
        self.pan.position += self.pan.degrees_to_pwm(10)
        
    def pan_right(self):
        self.pan.position -= self.pan.degrees_to_pwm(10)
        
    def tilt_up(self):
        self.tilt.position -= self.tilt.degrees_to_pwm(10)
        
    def tilt_down(self):
        self.tilt.position += self.tilt.degrees_to_pwm(10)
        
    def center(self):
        self.pan.position = self.CENTER[0]#pan.minimum + ((pan.maximum - pan.minimum)/2)
        self.tilt.position = self.CENTER[1]#tilt.minimum + ((tilt.maximum - tilt.minimum)/2)

    def setPan(self, v):
        self.pan.position = v
        
    def setTilt(self, v):
        self.tilt.position = v

    def on_new_frame(self, image):
        '''Face tracking function.'''
        # Face Detection using OpenCV. 
        # Adapted from Nirav Patel http://eclecti.cc 5/20/2008, 
        # in turn based on sample code by Roman Stanchak
        grayscale = cv.CreateImage(cv.GetSize(image), 8, 1)
        cv.CvtColor(image, grayscale, cv.CV_BGR2GRAY)
        storage = cv.CreateMemStorage()
        cv.EqualizeHist(grayscale, grayscale)
        cascade = cv.Load('haarcascade_frontalface_alt.xml')
        faces = cv.HaarDetectObjects(grayscale, cascade, storage, 1.2, 2, cv.CV_HAAR_DO_CANNY_PRUNING, (100,100))
        def get_delta(pos, span, tolerance):
            frame_center = span/2
            delta = frame_center - pos
            if abs(delta) < tolerance:
                return 0
            return math.sin(delta * math.pi / span) * 5
        if faces:
            centers = []
            for face in faces:
                centers.append((face[0][0] + (face[0][2] / 2), face[0][1] + (face[0][3] / 2)))
            center_of_mass = [0,0]
            for center in centers:
                center_of_mass[0] += center[0]
                center_of_mass[1] += center[1]
            center_of_mass[0] /= len(centers)
            center_of_mass[1] /= len(centers)
                
            frame_size = cv.GetSize(image)
            
            xdelta = get_delta(center_of_mass[0], frame_size[0], 50)
            ydelta = get_delta(center_of_mass[1], frame_size[1], 50)
            
            self.pan.position += self.pan.degrees_to_pwm(xdelta)
            self.tilt.position -= self.tilt.degrees_to_pwm(ydelta)


if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    main_window = MainWindow()
    
    cambot = Cambot(None)
    
    main_window.controls.pan_left_button.clicked.connect(cambot.pan_left)
    main_window.controls.pan_right_button.clicked.connect(cambot.pan_right)
    main_window.controls.tilt_up_button.clicked.connect(cambot.tilt_up)
    main_window.controls.tilt_down_button.clicked.connect(cambot.tilt_down)
    main_window.controls.center_button.clicked.connect(cambot.center)
    main_window.controls.panDial.setRange(cambot.pan.minimum, cambot.pan.maximum)
    main_window.controls.panDial.setValue(cambot.CENTER[0])
    main_window.controls.panDial.valueChanged.connect(cambot.setPan)
    main_window.controls.tiltDial.setRange(cambot.tilt.minimum, cambot.tilt.maximum)
    main_window.controls.tiltDial.setValue(cambot.CENTER[1])
    main_window.controls.tiltDial.valueChanged.connect(cambot.setTilt)

    camera = CameraDevice()
    
    def set_face_tracking(b):
        if b:
            camera.new_frame.connect(cambot.on_new_frame)
        else:
            camera.new_frame.disconnect(cambot.on_new_frame)
    
    main_window.controls.toggle_face_tracking.toggled.connect(set_face_tracking)
    
    preview = CameraWidget(camera)
    preview_dock = QtGui.QDockWidget('Preview')
    preview_dock.setWidget(preview)
    main_window.addDockWidget(QtCore.Qt.LeftDockWidgetArea, preview_dock)

    main_window.show()
    #preview.show()
    
    app.exec_()