__version__ = '0.1.0'

import sys
import time
import os
import cv2
from PIL import Image
import atexit
import Config as cfg
import numpy as np
import subprocess as sp

def create_tracker():
    """
    Create a tracker instance using whichever constructor is available on this cv2 build.
    Adjusted for OpenCV 4.12 — prefers Nano or MIL tracker.
    """
    constructors = [
        lambda: cv2.TrackerNano_create(),     # Very fast lightweight tracker
        lambda: cv2.TrackerMIL_create(),      # Older but stable tracker
        lambda: cv2.TrackerDaSiamRPN_create() # More accurate, slower
    ]
    for ctor in constructors:
        try:
            return ctor()
        except Exception:
            continue
    raise RuntimeError("No compatible tracker found! Try installing 'opencv-contrib-python' or use available tracker names.")



class Camera(object):
    def __init__(self, resolution=cfg.video_resolution):
        self.cameraProcess = None
        self.resolution = resolution
        self.is_enabled = False

        self.locked_on = False
        self.tlast = 0

        # pic dump stuff
        self.frame_n = 0
        self.pic_type = ''

        # Setup stuff
        # Use CSRT for more robust tracking
        self.tracker = create_tracker()
        cascade_name = 'haarcascade_frontalface_default.xml'
        cascade_path = os.path.join(cv2.data.haarcascades, cascade_name)
        if not os.path.exists(cascade_path):
            cascade_path = os.path.join(os.path.dirname(__file__), cascade_name)
        self.face_cascade = cv2.CascadeClassifier(cascade_path)

        if self.face_cascade.empty():
            raise FileNotFoundError(f"Cannot load cascade xml. Tried: {cascade_path}")


    @staticmethod
    def _display_image(img):
        cv2.imshow("Image", img)
        cv2.waitKey(0)


    @staticmethod
    def _save_image(img, impath):
        save_dir = os.path.abspath(getattr(cfg, "saveimg_path", "./images"))
        os.makedirs(save_dir, exist_ok=True)
        im = Image.fromarray(img)
        im.save(os.path.join(save_dir, impath))

    def start(self):
        """
        Force-select DroidCam as webcam (index 2 for your setup).
        """
        DROIDCAM_INDEX = 2  # 👈 your DroidCam index
        print(f"[CameraDriver] Starting DroidCam on index {DROIDCAM_INDEX}...")

        # Use DirectShow for Windows
        self.cap = cv2.VideoCapture(DROIDCAM_INDEX, cv2.CAP_DSHOW)
        # Force a fixed resolution and prevent auto-rotation from DroidCam
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)  # optional: disable focus flicker

        if not self.cap.isOpened():
            raise RuntimeError("❌ Could not open DroidCam. Make sure DroidCam Client is running and connected.")

        # Set resolution
        w, h = self.resolution
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)

        print("[CameraDriver] ✅ DroidCam started successfully.")


    def stop(self):
        try:
            self.cap.release()
        except Exception:
            pass


    def get_frame(self):
        """Read a frame from the camera and return a rotated grayscale image or None."""
        if not hasattr(self, 'cap') or self.cap is None:
            print("Warning: camera not started.")
            return None

        ret, img = self.cap.read()
        if not ret or img is None:
            print("Warning: failed to read frame from camera (ret=False or img None).")
            return None

        if img.size == 0:
            print("Warning: captured image has zero size.")
            return None

        # --- Force consistent orientation (always landscape) ---
        h, w = img.shape[:2]
        if h > w:
            img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
    # -------------------------------------------------------

        try:
            img[:, :, 2] = np.zeros([img.shape[0], img.shape[1]])
        except Exception:
            pass

        try:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        except Exception as e:
            print("Warning: cvtColor failed:", e)
            return None

        # Also return the color frame for visualization
        self.last_color_frame = img.copy()

        if cfg.SAVE_FRAMES:
            self.frame_n += 1
            try:
                self._save_image(gray, '{}.jpg'.format(self.frame_n))
            except Exception as e:
                print("Warning: failed to save frame:", e)

        return gray


    def reset_lock_on(self):
        """Reset the tracker in a version-safe way and mark unlocked."""
        try:
            if hasattr(self.tracker, 'clear'):
                self.tracker.clear()
            else:
                self.tracker = create_tracker()
        except Exception:
            self.tracker = create_tracker()
        self.locked_on = False


    def lock_on(self, target_bbox = None):
        """Lock the tracker on a bounding box. Wait for a valid frame first."""
        if target_bbox is None:
            (imgw, imgh) = cfg.laser_center
            (w,h) = cfg.lock_on_size_px
            h_lower = imgh - int(h/2)
            w_lower = imgw - int(w/2)
            target_bbox = (w_lower, h_lower, w, h)
        else:
            (w_lower, h_lower, w, h) = target_bbox

        # Attempt to capture a valid frame
        frame = None
        attempts = 10
        for i in range(attempts):
            frame = self.get_frame()
            if frame is not None and getattr(frame, "size", 0) != 0:
                break
            time.sleep(0.05)

        if frame is None or getattr(frame, "size", 0) == 0:
            raise RuntimeError(f"Failed to capture valid frame for lock_on() after {attempts} attempts")

        # crop target image from the valid frame (guard indices)
        h_lower = max(0, h_lower)
        w_lower = max(0, w_lower)
        self.target_img = frame[h_lower : h_lower + h, w_lower : w_lower + w]

        if cfg.DEBUG_MODE:
            try:
                self._save_image(self.target_img, 'lock_on_img.jpg')
            except Exception:
                pass

        self.reset_lock_on()

        # initialize tracker in a try/catch and retry once if it fails
        try:
            self.tracker.init(frame, target_bbox)
        except Exception as e:
            print("Warning: tracker.init() failed, recreating tracker and retrying:", e)
            self.tracker = create_tracker()
            try:
                self.tracker.init(frame, target_bbox)
            except Exception as e2:
                raise RuntimeError("tracker.init() failed after retry: " + str(e2))

        self.locked_on = True


    def get_location(self):
        """ returns (h, w) or (0,0) if tracking not available """
        if not self.locked_on:
            raise Exception('Cant track an object if not locked on...duh.')

        frame = self.get_frame()
        if frame is None or getattr(frame, "size", 0) == 0:
            print("Warning: Empty frame received; skipping tracker.update().")
            return (0, 0)

        try:
            ok, bbox = self.tracker.update(frame)
        except Exception as e:
            print("Warning: tracker.update() threw an exception:", e)
            try:
                self.reset_lock_on()
            except Exception:
                pass
            self.locked_on = False
            return (0, 0)

        tnow = time.time()

        if ok:
            (a, b, c, d) = (int(j) for j in bbox)
            h = b + int(d / 2)
            w = a + int(c / 2)
            vis = frame.copy()
            try:
                vis = cv2.rectangle(vis, (a, b), (a + c, b + d), (0, 0, 0), 2)
            except Exception:
                pass

            if cfg.DEBUG_MODE:
                if (tnow - self.tlast) > 0:
                    print("[{}, {}] - {} fps".format(h, w, 1 / (tnow - self.tlast)))
                self.tlast = tnow

            if cfg.SAVE_FRAMES:
                try:
                    self._save_image(vis, 'cv_{}.jpg'.format(self.frame_n))
                except Exception:
                    pass

            return (h, w)

        else:
            print('Tracking error: tracker returned ok=False')
            if cfg.SAVE_FRAMES:
                try:
                    self._save_image(frame, 'cv_{}.jpg'.format(self.frame_n))
                except Exception:
                    pass
            return (0, 0)


    def find_face(self):
        frame = self.get_frame()
        if hasattr(self, "last_color_frame"):
            color_frame = self.last_color_frame.copy()
        else:
            color_frame = None

        if frame is None:
            return None
        faces = self.face_cascade.detectMultiScale(frame, 1.2, 6)

        tnow = time.time()
        if cfg.DEBUG_MODE:
            print("Face Detection - {} fps".format(1 / (tnow - self.tlast) if (tnow - self.tlast) > 0 else 0))
            self.tlast = tnow

        if len(faces) > 0:
            [a, b, c, d] = faces[0]
            return (a, b, c, d)
        return None


    def show_frame(self, frame):
        (w,h) = self.resolution
        try:
            frame.shape = (h,w) # set the correct dimensions for the numpy array
        except Exception:
            pass
        cv2.imshow("skrrt", frame)


if __name__=='__main__':
    c = Camera()
    c.start()
    try:
        print('Camera started')

        face = None
        while face is None:
            face = c.find_face()
            if face is None:
                print("Searching for face...")
                time.sleep(0.1)

        print("Face found, locking on!")
        c.lock_on(face)
        print("Locked on target.")

        while True:
            try:
                h, w = c.get_location()
            except Exception as e:
                print("Lost lock, trying to reacquire...", e)
                face = c.find_face()
                if face is not None:
                    c.lock_on(face)
                else:
                    print("No face detected.")
                    time.sleep(0.1)

    finally:
        c.stop()
