from PyQt5 import QtGui
from PyQt5.QtWidgets import QWidget, QApplication, QLabel, QVBoxLayout, QPushButton, QGridLayout, QHBoxLayout
from PyQt5.QtGui import QPixmap
import sys
import cv2
from PyQt5.QtCore import pyqtSignal, pyqtSlot, Qt, QThread
import numpy as np
from time import sleep
import imutils
import imageio

class VideoThread(QThread):
    change_pixmap_signal = pyqtSignal(np.ndarray)
    hit_signal = pyqtSignal(bool)
    hit_success_signal= pyqtSignal(bool)

    def __init__(self,ctrl):
        super().__init__()
        self._run_flag = True
        self.ctrl = ctrl


    def rotate_image(self,image,angle):
        image_center = tuple(np.array(image.shape[1::-1])/2)
        rot_mat = cv2.getRotationMatrix2D(image_center,angle,1.0)
        result = cv2.warpAffine(image,rot_mat,image.shape[1::-1],flags=cv2.INTER_LINEAR)
        return result

    def load_video_frames(self,clipname):
        # capture from web cam
        cap = cv2.VideoCapture(clipname)

        # Load all frames of the video into a list
        all_frames = []
        ret = True
        while ret:
            ret, frame = cap.read()
            all_frames.append(frame)

        # shut down capture system
        cap.release()
        return all_frames

    def load_gif_frames(self,gifname):
        # Load all the frames from a gif animation file
        gif_reader = imageio.get_reader(gifname)
        gif_length = gif_reader.get_length()
        missile_frames = []
        frm_cnt = 0
        while frm_cnt < gif_length:
            missile_frame = gif_reader.get_data(frm_cnt)
            missile_frames.append(missile_frame)
            frm_cnt += 1
        return missile_frames

    def detect_plane(self,image):
        # Convert the image to grayscale
        image_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Threshold the image so only plane pixels are left white and all remaining pixels are converted to black
        # You may adjust the threshold value (170 in our case) when using any other video
        ret, image_thresh = cv2.threshold(image_gray, 170, 255, 0)

        # Even if you adjust the threshold very carefully it is very difficult to find a threshold value where all pixels of plane are white and rest of the image is black.
        # The best we could achieve was to get multiple segments of plane in white pixels while there was no other white pixel anywhere in the frame.
        # So we decided to find all those segments using the method of finding Contours below.
        contours, hierarchy = cv2.findContours(image_thresh, 1, 2)

        # Here we are computing the location and size of each segment and making list of the coordinates for top left and bottom right corners of each segment
        top_xs = []
        top_ys = []
        bottom_xs = []
        bottom_ys = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)

            top_xs.append(x)
            top_ys.append(y)
            bottom_xs.append(x + w)
            bottom_ys.append(y + h)

        # We want to include all segments of the plane so we will find the top left corner and bottom right corner such that it includes:
        # * Left Most Segment
        # * Right Most Segment
        # * Top most segments
        # * Bottom most segment

        if len(top_xs) > 0:
            top_x = min(top_xs)             # Set the top_x value to be from left most segment
            top_y = min(top_ys)             # Set the top_x value to be from top heighest segment
            bottom_x = max(bottom_xs)       # Set the bottom_x value to be from right most segment
            bottom_y = max(bottom_ys)       # Set the bottom_y value to be from lowest segment

            return top_x,top_y,bottom_x,bottom_y

        else:
            return 0,0,0,0

    def run(self):

        all_frames = self.load_video_frames('video/clip_video.mp4')
        missile_frames = self.load_gif_frames('resource/rocket1.gif')
        blast_frames = self.load_gif_frames('resource/blast.gif')


        i=0           # Starting index from video frames; 0 is the index of first video frame
        max_w = 0     # Maximum width of Detected Plane in all frames
        max_h = 0     # Maximum height of Detected Plane in all frames

        missile_frame_count=0       # Starting index from missile gif frames

        # The missile is animated to target the plane with gradually decreasing the size, changing the angle and location on the screen.

        # Initially the size of missile image is 1000 and over the time it is decreased to 100 to make it look like it is moving away from the user and closer to the plane.
        # For this purpose we needed a list of sizes ranging from 1000 to 100.
        # The list below is created by subracting 10 from initial size to the point it reaches the final size.
        # Later this list will be used the resize the missile starting from the first value in the list to the last value in the list.
        # Note: The list is only initialized here, the actual values are computed during the execution to suite best for current location of target aircraft
        widths = [val for val in range(1000,100,-10)]
        width_cnt = 0 # Setting the initial index of missile width to be 0 (the first value in the list of widths)

        # Initially the size of missile image is rotated to -300 degrees and over the time it is rotated to 300 degrees to make it look like it is changing angle to target the enemy plane.
        # For this purpose we needed a list of angles ranging from -300 degrees to 300 degrees.
        # The list below is created by adding 10 degree from initial angle of -300 degrees to the point it reaches the final angle of impact, 300 degrees.
        # Later this list will be used the rotate the missile image from the first value in the list to the last value in the list.
        # Note: The list is only initialized here, the actual values are computed during the execution to suite best for current location of target aircraft
        angles = [val for val in range(-300,300,10)]
        angles_cnt = 0 # Setting the initial index of missile angle to be 0 (the first value in the list of angles)

        # Initially the size of missile image is placed at (x,y) location (1500, 1500) and over the time it is moved to (10,10) to make it look like it is changing the location to be closer to the target plane.
        # For this purpose we needed lists of x,y coordiantes ranging from 1500 to 10 pixel each.
        # The lists below is created by subtracting 10 pixels from initial location of 1500 pixels to the point it reaches the final location of impact, 10 pixels.
        # Later this list will be used the move the missile image from the starting position in the list to the last position in the list.
        # Note: The list is only initialized here, the actual values are computed during the execution to suite best for current location of target aircraft
        orig_y_offset = 1500        # Setting the initial position of missile to be 1500 on y-axis
        orig_x_offset = 1500        # Setting the initial position of missile to be 1500 on x-axis
        y_offset = orig_y_offset    # Setting the current y-axis position to be initial position
        x_offset = orig_x_offset    # Setting the current y-axis position to be initial position
        y_offsets = [val for val in range(y_offset,10,-10)]
        x_offsets = [val for val in range(x_offset, 10, -10)]
        y_offset_cnt = 0 # Setting the initial index of missile position on y-axis to be 0 on y-axis (the first value in the list of y-axis values)
        x_offset_cnt = 0 # Setting the initial index of missile position on x-axis  to be 0 on x-axis (the first value in the list of x-axis values)

        while self._run_flag:
            # We need to add some delay otherwise video will play very fast. YOu may adjust the delay in each frame to control the video speed.
            sleep(0.01)

            # If reached the last frame, then reset the index to be 0, to start the video from begining
            if i==len(all_frames)-1:
                i=0

            # Take the ith frame
            frame = all_frames[i]

            # Resize the frame
            frame= imutils.resize(frame, width=500)

            # Considering the requirements of the project, we wrote an easy to understand and light weight method to detect the plane.
            # In future if you want to use deep learning or any other advanced method, you may just replace this method with your desired method and rest of the program will work fine.
            top_x, top_y, bottom_x, bottom_y = self.detect_plane(frame)

            if not (top_x==top_y==bottom_x==bottom_y):


                if self.ctrl["track"]:
                    # If tracking flag is ON, then it will display the bounding box on the detected object
                    cv2.rectangle(frame, (top_x-20,top_y-20), (bottom_x+20,bottom_y+20), (0, 255, 0), 2)


                if self.ctrl['lock']:
                    # If lock flag is ON, then we will crop the image such that it object location will remain constant in the video frame
                    # This is to simulate the target locking done by LD-POD camera by continuosly following the moving object
                    plane_width = bottom_x - top_x
                    max_w = max(plane_width, max_w)     # Width of the object detected may vary in each frame, but we want to compute the frame width based on the maximum width of the object
                    bottom_x2 = top_x + max_w

                    plane_height = bottom_y - top_y
                    max_h = max(plane_height, max_h)    # Height of the object detected may vary in each frame, but we want to compute the frame height based on the maximum height of the object
                    bottom_y2 = top_y + max_h

                    # Crop the frame width (50,50) margin from top left corner and (150,150) margin from bottom right corner
                    # You may want to use equal margins at top left and bottom right corners e.g. (50,50) and (50,50). It will put the object in center of the screen.
                    # In our video, we don't have much space available on top and left side of the object therefore used (50,50) margin unlikne (150,150) at bottom right
                    frame = frame[top_y-50:bottom_y2+100,top_x-50:bottom_x2+150]

                    # IF "hit" flag is on, the video will also show a missible animation.
                    # The size, location and orientation of the missile will depend upon the trajectory defined the the lists of iwdths, angles. x_offsets and y_offsets
                    if self.ctrl['hit']:

                        # Select next frame from missile animation. Select first frame if reached end of the animation
                        missile_frame = missile_frames[missile_frame_count % len(missile_frames)]


                        if missile_frame is not None:

                            #### RESIZE THE MISSILE IMAGE
                            # select the width of missile frame from the list. The list has bigger numbers for width, we actually want to use 10th of that size
                            width = widths[width_cnt]/10
                            # increment in the index of widths in line. After reaching the end of the list, the index is not changed further and width remains constant for rest of the frames.
                            width_cnt=min(width_cnt+1,len(widths)-1)
                            # resize the missile image
                            missile_frame = imutils.resize(missile_frame, width=int(width))


                            #### ROTATE THE MISSILE IMAGE
                            # select the angle of missile frame from the list. The list has bigger numbers for angles, we actually want to use 10th of that size
                            angle = angles[angles_cnt]/10
                            # increment in the index of angles in line. After reaching the end of the list, the index is not changed further and angle remains constant for rest of the frames.
                            angles_cnt = min(angles_cnt+1,len(angles)-1)
                            # rotate the missile image
                            missile_frame = self.rotate_image(missile_frame,angle)

                            try:
                                y_offsets = [val for val in range(y_offsets[1], 360 + int((bottom_y2 - 30) / 2), -10)]
                                y_offset = int(y_offsets[0]/10)
                            except:

                                blast_frame_count=0

                                self.hit_signal.emit(True)

                                self.ctrl["run"]=False
                                self.hit_success_signal.emit(True)


                                while self.ctrl['run']==False:
                                    last_frame = frame.copy()
                                    blast_frame = blast_frames[blast_frame_count % len(blast_frames)]
                                    blast_frame = imutils.resize(blast_frame, width=50)
                                    if blast_frame is not None:
                                        b_x1 = 0
                                        b_x2 = blast_frame.shape[1]
                                        b_y1 = 0
                                        b_y2 = blast_frame.shape[0]

                                        if y_offset + b_y2 > last_frame.shape[0]:
                                            b_y2 = last_frame.shape[0] - y_offset

                                        if x_offset + b_x2 > last_frame.shape[1]:
                                            b_x2 = last_frame.shape[1] - x_offset

                                        y1, y2 = y_offset-10, y_offset + b_y2-10
                                        x1, x2 = x_offset-20, x_offset + b_x2-20

                                        alpha_blast = blast_frame[b_y1:b_y2, b_x1:b_x2, 3] / 255.0
                                        alpha_last_frame = 1.0 - alpha_blast

                                        for c in range(0, 3):
                                            last_frame[y1:y2, x1:x2, c] = (
                                                        alpha_blast * ~blast_frame[b_y1:b_y2, b_x1:b_x2,
                                                                        c] + alpha_last_frame * last_frame[y1:y2, x1:x2, c])
                                        self.change_pixmap_signal.emit(last_frame)
                                        blast_frame_count +=1
                                        sleep(0.01)
                                angles_cnt = 0
                                width_cnt = 0
                                y_offset_cnt = 0
                                x_offset_cnt = 0
                                y_offset = orig_y_offset
                                y_offsets = [val for val in range(y_offset, 10, -10)]
                                x_offset = orig_x_offset
                                x_offsets = [val for val in range(x_offset, 10, -10)]

                            try:

                                x_offsets = [val for val in range(x_offsets[1] if len(x_offsets) > 0 else x_offset, 360 + int((bottom_x2 - 30) / 2), -10)]
                                x_offset = int(x_offsets[0]/10)

                            except:
                                last_frame = frame.copy()
                                blast_frame_count = 0
                                self.hit_signal.emit(True)

                                self.ctrl["run"] = False
                                self.hit_success_signal.emit(True)
                                while self.ctrl['run'] == False:
                                    blast_frame = blast_frames[blast_frame_count % len(blast_frames)]
                                    if blast_frame is not None:
                                        b_x1 = 0
                                        b_x2 = blast_frame.shape[1]
                                        b_y1 = 0
                                        b_y2 = blast_frame.shape[0]



                                        if y_offset + b_y2 > last_frame.shape[0]:
                                            b_y2 = last_frame.shape[0] - y_offset

                                        if x_offset + b_x2 > last_frame.shape[1]:
                                            b_x2 = last_frame.shape[1] - x_offset

                                        y1, y2 = y_offset, y_offset + b_y2
                                        x1, x2 = x_offset, x_offset + b_x2

                                        alpha_blast = blast_frame[:,:, 3] / 255.0
                                        alpha_last_frame = 1.0 - alpha_blast

                                        for c in range(0,3):
                                            last_frame[y1:y2, x1:x2, c] = (
                                                    alpha_blast * blast_frame[:,:,
                                                                  c] + alpha_last_frame * last_frame[y1:y2, x1:x2,
                                                                                          c])
                                        self.change_pixmap_signal.emit(last_frame)
                                        blast_frame_count += 1
                                        sleep(0.05)
                                angles_cnt = 0
                                width_cnt = 0
                                y_offset_cnt = 0
                                x_offset_cnt = 0
                                y_offset = orig_y_offset
                                y_offsets = [val for val in range(y_offset, 10, -10)]
                                x_offset = orig_x_offset
                                x_offsets = [val for val in range(x_offset, 10, -10)]

                            y_offset_cnt = min(y_offset_cnt+1,len(y_offsets)-1)


                            m_x1 = 0
                            m_x2 = missile_frame.shape[1]
                            m_y1 = 0
                            m_y2 = missile_frame.shape[0]

                            if y_offset+m_y2 > frame.shape[0]:
                                m_y2=frame.shape[0]-y_offset

                            if x_offset+m_x2 > frame.shape[1]:
                                m_x2=frame.shape[1]-x_offset


                            y1,y2 = y_offset,y_offset+m_y2
                            x1,x2 = x_offset,x_offset+m_x2



                            alpha_missile = missile_frame[m_y1:m_y2,m_x1:m_x2,3] / 255.0
                            alpha_frame = 1.0 - alpha_missile

                            for c in range(0,3):
                                frame[y1:y2,x1:x2,c] = (alpha_missile * missile_frame[m_y1:m_y2,m_x1:m_x2,c] + alpha_frame * frame[y1:y2,x1:x2,c])

                self.change_pixmap_signal.emit(frame)
            i=i+1
            missile_frame_count += 1



    def stop(self):
        """Sets run flag to False and waits for thread to finish"""
        self._run_flag = False
        self.wait()


class App(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("LD POD demo")
        self.disply_width = 640
        self.display_height = 480
        # create the label that holds the image
        self.image_label = QLabel(self)
        self.image_label.resize(self.disply_width, self.display_height)
        # create a text label
        self.textLabel = QLabel('Controls')

        self.lockButton= QPushButton(self)
        self.lockButton.setText("Lock Target")
        self.lockButton.clicked.connect(self.lockTarget)

        self.trackButton = QPushButton(self)
        self.trackButton.setText("Tracking On")
        self.trackButton.clicked.connect(self.trackTarget)

        self.hitButton = QPushButton(self)
        self.hitButton.setText("Hit the Target")
        self.hitButton.clicked.connect(self.hitTarget)

        self.restartButton = QPushButton(self)
        self.restartButton.setText("Restart")
        self.restartButton.clicked.connect(self.restart)

        layout = QGridLayout()
        layout.setRowStretch(2,1)
        layout.addWidget(self.image_label,0,0)


        hbox = QHBoxLayout()
        hbox.addWidget(self.trackButton)
        hbox.addWidget(self.lockButton)
        hbox.addWidget(self.hitButton)
        hbox.addWidget(self.restartButton)

        layout.addLayout(hbox,1,0)

        self.lockButton.setDisabled(True)
        self.hitButton.setDisabled(True)
        self.restartButton.setDisabled(True)

        # set the vbox layout as the widgets layout
        self.setLayout(layout)

        self.ctrl = {"track":False,"lock":False,"hit":False,"run":True}
        # create the video capture thread
        self.thread = VideoThread(self.ctrl)
        # connect its signal to the update_image slot
        self.thread.change_pixmap_signal.connect(self.update_image)
        self.thread.hit_signal.connect(self.resetMissile)
        self.thread.hit_success_signal.connect(self.enableRestart)

        # start the thread
        self.thread.start()

    def closeEvent(self, event):
        self.thread.stop()
        event.accept()

    def restart(self):
        self.ctrl["run"]=True
        self.restartButton.setDisabled(True)




    def lockTarget(self):

        if self.ctrl["lock"]==False:
            self.ctrl['lock']=True
            self.lockButton.setText("Release Target")
            self.hitButton.setEnabled(True)
        else:
            self.ctrl['lock']=False
            self.lockButton.setText("Lock Target")
            self.hitButton.setDisabled(True)

    def trackTarget(self):
        if self.ctrl["track"]==False:
            self.ctrl['track']=True
            self.trackButton.setText("Tracking Off")
            self.lockButton.setEnabled(True)


        else:
            self.ctrl['track']=False
            self.trackButton.setText("Tracking On")
            self.lockButton.setDisabled(True)
            self.ctrl['lock'] = False
            self.lockButton.setText("Lock Target")
            self.hitButton.setDisabled(True)

    def hitTarget(self):
        if self.ctrl["hit"]==False:
            self.ctrl['hit']=True
            self.hitButton.setText("Missile Launched")
            self.hitButton.setDisabled(True)

    @pyqtSlot(bool)
    def enableRestart(self,hit_success):
        if hit_success:
            self.ctrl["run"] = False
            self.ctrl['track'] = False
            self.ctrl['lock'] = False
            self.restartButton.setEnabled(True)

    @pyqtSlot(bool)
    def resetMissile(self,lauch_success):
        if lauch_success:
            self.ctrl['hit'] = False
            self.hitButton.setText("Hit the Target")
            self.hitButton.setEnabled(True)

    @pyqtSlot(np.ndarray)
    def update_image(self, cv_img):
        """Updates the image_label with a new opencv image"""
        qt_img = self.convert_cv_qt(cv_img)
        self.image_label.setPixmap(qt_img)

    def convert_cv_qt(self, cv_img):
        """Convert from an opencv image to QPixmap"""
        rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        convert_to_Qt_format = QtGui.QImage(rgb_image.data, w, h, bytes_per_line, QtGui.QImage.Format_RGB888)
        p = convert_to_Qt_format.scaled(self.disply_width, self.display_height, Qt.KeepAspectRatio)
        return QPixmap.fromImage(p)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    a = App()
    a.show()
    sys.exit(app.exec_())