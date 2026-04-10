# track_and_aim.py
# Uses your Camera class (CameraDriver.py) and sends servo commands to Arduino via COM8.

import time
import serial
import math
from CameraDriver import Camera
import Config as cfg
import cv2

face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

# ---------- Configurable parameters ----------
SERIAL_PORT = "COM8"            # your Arduino port
BAUD = 9600                     # must match Arduino sketch
MAX_UPDATES_PER_SEC = 10        # rate limit (Hz)
SMOOTH_ALPHA = 0.35             # EMA smoothing (0..1) higher = more responsive
H_FOV_DEG = 60.0                # camera horizontal FOV (approx) — tune for accuracy
V_FOV_DEG = 40.0                # camera vertical FOV (approx) — tune for accuracy
CENTER_TOL_PIX = 12             # pixels tolerance to consider "centered"
ENABLE_TRIGGER = False          # set True only after testing aiming (and update Arduino sketch)
# --------------------------------------------

def pixel_to_servo_angles(px, py, frame_w, frame_h,
                          h_fov_deg=H_FOV_DEG, v_fov_deg=V_FOV_DEG):
    """Map pixel (px,py) -> servo angles (yaw_deg, pitch_deg).
       We assume servo center 90deg = camera center. Linear approx using FOV."""
    cx, cy = frame_w / 2.0, frame_h / 2.0
    dx = px - cx   # +right
    dy = cy - py   # +up (flip image coordinates)

    pan_deg = (dx / (frame_w / 2.0)) * (h_fov_deg / 2.0)
    tilt_deg = (dy / (frame_h / 2.0)) * (v_fov_deg / 2.0)

    # Map to servo scale: center at 90 deg
    yaw = 90 + pan_deg
    pitch = 90 + tilt_deg

    # clamp to 0..180
    yaw = max(0, min(180, int(round(yaw))))
    pitch = max(0, min(180, int(round(pitch))))
    return yaw, pitch

def send_servo_cmd(ser, yaw, pitch):
    cmd = f"Y{yaw}P{pitch}\n"
    try:
        ser.write(cmd.encode())
    except Exception as e:
        print("Serial write error:", e)
    # optionally read ack: ser.readline()

def main():
    # open serial
    print("Opening serial:", SERIAL_PORT)
    ser = serial.Serial(SERIAL_PORT, BAUD, timeout=0.5)
    time.sleep(2)  # Arduino auto-reset delay

    # init camera
    cam = Camera()
    cam.start()
    print("Camera started. Searching for face / lock area...")

    # try to auto-find a face and lock on, else lock central box
    face = None
    t0 = time.time()
    while time.time() - t0 < 8:
        ret, frame = cam.cap.read()
        if not ret:
           continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)

        if len(faces) > 0:
            (x, y, w, h) = faces[0]
            face = (x, y, w, h)
        else:
            face = None

        if face is not None:
            print("Face found:", face)
            cam.lock_on(face)
            break
        time.sleep(0.1)

    if face is None:
        print("No face found → locking centered box.")
        cam.lock_on()

    # initialization for smoothing
    frame_w, frame_h = cfg.video_resolution
    smoothed_yaw = 90
    smoothed_pitch = 90
    last_send = 0.0
    update_period = 1.0 / MAX_UPDATES_PER_SEC

    print("Tracking loop started. Press Ctrl+C or 'q' in the window to stop.")
    try:
        while True:
            # Grab a live frame from the Camera object (CameraDriver manages rotation/grayscale)
            # but we need a BGR frame for display; cam.get_frame() returns a rotated grayscale.
            # Here we read raw BGR from the underlying capture for display and overlay.
            ret, frame = cam.cap.read()
            if not ret or frame is None:
                time.sleep(0.01)
                continue

            # working copy for detection: convert to gray same as CameraDriver's orientation
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            # rotate gray to match CameraDriver orientation if needed (CameraDriver rotates)
            try:
                r_gray = cv2.rotate(gray, cv2.ROTATE_90_COUNTERCLOCKWISE)
            except Exception:
                r_gray = gray

            # detect face (using Camera's cascade loader would be OK, but reuse cam.find_face())
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.3, minNeighbors=5, minSize=(40, 40))

            if len(faces) > 0:
                (x, y, w, h) = faces[0]
                found = (x, y, w, h)
            else:
                found = None


            # draw center marker
            cx_frame = frame.shape[1] // 2
            cy_frame = frame.shape[0] // 2
            cv2.circle(frame, (cx_frame, cy_frame), 5, (255, 0, 0), -1)

            if found is not None:
                (x, y, w, h) = found
                # convert coords from rotated r_gray back to display coords if necessary
                # cam.find_face() uses rotated grayscale; its coords are in that rotated frame.
                # To overlay correctly on the BGR frame we should rotate or map the coordinates.
                # Simple approach: rotate the original BGR to match r_gray for overlay.
                try:
                    disp_frame = frame.copy()
                    show_frame = disp_frame

                except Exception:
                    disp_frame = frame.copy()

                # draw on display frame
                fx, fy = int(x), int(y)
                fw, fh = int(w), int(h)
                face_center_x = fx + fw // 2
                face_center_y = fy + fh // 2
                cv2.rectangle(disp_frame, (fx, fy), (fx + fw, fy + fh), (0, 255, 0), 2)
                cv2.circle(disp_frame, (face_center_x, face_center_y), 5, (0, 0, 255), -1)
                cv2.putText(disp_frame, "Tracking", (fx, max(10, fy - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,0), 2)

                # compute servo angles from pixel in rotated frame (use frame_h/frame_w accordingly)
                # Note: find_face returned coords in rotated frame (r_gray), so width/height are r_gray.shape
                r_h, r_w = r_gray.shape
                yaw, pitch = pixel_to_servo_angles(face_center_x, face_center_y, r_w, r_h)

                # smoothing (EMA)
                smoothed_yaw = int(round(SMOOTH_ALPHA * yaw + (1 - SMOOTH_ALPHA) * smoothed_yaw))
                smoothed_pitch = int(round(SMOOTH_ALPHA * pitch + (1 - SMOOTH_ALPHA) * smoothed_pitch))

                # rate limit and send
                if (time.time() - last_send) >= update_period:
                    send_servo_cmd(ser, smoothed_yaw, smoothed_pitch)
                    last_send = time.time()
                    if cfg.DEBUG_MODE:
                        print(f"Sent -> Y{smoothed_yaw} P{smoothed_pitch}  (raw: {yaw},{pitch})")

                # show the rotated display (so overlays match detection)
                try:
                    show_frame = cv2.rotate(disp_frame, cv2.ROTATE_90_CLOCKWISE)
                except Exception:
                    show_frame = disp_frame

                cv2.imshow("Tracking View", show_frame)

            else:
                # No face found - show original frame and a centered lock box
                cv2.rectangle(frame, (cx_frame - 40, cy_frame - 40), (cx_frame + 40, cy_frame + 40), (255, 0, 0), 2)
                cv2.putText(frame, "No Face Detected", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,255), 2)
                cv2.imshow("Tracking View", frame)

            # allow quitting by pressing 'q' in window
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

            # small sleep to yield CPU
            time.sleep(0.005)

    except KeyboardInterrupt:
        print("Stopping (KeyboardInterrupt)...")

    finally:
        cv2.destroyAllWindows()
        cam.stop()
        try:
            ser.close()
        except Exception:
            pass

if __name__ == "__main__":
    main()
