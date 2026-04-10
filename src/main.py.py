# -*- coding: utf-8 -*-
import cv2
import pigpio
import numpy as np
from picamera2 import Picamera2
import time
import sys

# ==========================================
# ⚙️ INDEPENDENT LIMITS (Yahan se tune karo)
# ==========================================
PAN_PIN = 18
TILT_PIN = 13

# ⚠️ PAN LIMIT (Horizontal): Agar laser left/right bahar ja rahi hai, 
# toh is number ko KAM karo (e.g., 120, 100, ya 80).
PAN_LIMIT = 120 

# ⚠️ TILT LIMIT (Vertical): Tune this separately if needed.
TILT_LIMIT = 180 

FRAME_W = 320
FRAME_H = 240

# --- TRACKING TUNING ---
SENSITIVITY = 0.15 # Smoothness (0.1 to 0.3)
DEADZONE = 15      # Center stability

# --- ORIENTATION ---
FLIP_METHOD = -1   # 180 Flip (Hardware dependent)
INVERT_PAN = True
INVERT_TILT = True

# =========================
# INIT
# =========================
pi = pigpio.pi()
if not pi.connected:
    print("Run: sudo pigpiod")
    sys.exit()

BASE_VAL = 1500
curr_p, curr_t = BASE_VAL, BASE_VAL

# Calculate Independent Ranges
P_MIN, P_MAX = BASE_VAL - PAN_LIMIT, BASE_VAL + PAN_LIMIT
T_MIN, T_MAX = BASE_VAL - TILT_LIMIT, BASE_VAL + TILT_LIMIT

# Apply Inversions logic
if INVERT_PAN: P_MIN, P_MAX = P_MAX, P_MIN
if INVERT_TILT: T_MIN, T_MAX = T_MAX, T_MIN

face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

picam2 = Picamera2()
config = picam2.create_preview_configuration(main={"size": (FRAME_W, FRAME_H), "format": "RGB888"})
picam2.configure(config)
picam2.start()

# Home
pi.set_servo_pulsewidth(PAN_PIN, BASE_VAL)
pi.set_servo_pulsewidth(TILT_PIN, BASE_VAL)

# =========================
# MAIN LOOP
# =========================
print(f"[SYSTEM ACTIVE] Pan Limit: +/- {PAN_LIMIT} | Tilt Limit: +/- {TILT_LIMIT}")

try:
    while True:
        frame = picam2.capture_array()[:, :, :3]
        frame = cv2.flip(frame, FLIP_METHOD)

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.2, 5)

        if len(faces) > 0:
            (x, y, w, h) = faces[0]
            cx, cy = x + w // 2, y + h // 2

            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
            cv2.circle(frame, (cx, cy), 5, (0, 0, 255), -1)

            # --- INDEPENDENT INTERPOLATION ---
            # Har axis apni range ke andar hi map hogi
            target_p = np.interp(cx, [0, FRAME_W], [P_MIN, P_MAX])
            target_t = np.interp(cy, [0, FRAME_H], [T_MIN, T_MAX])

            # Deadzone Check
            if abs(cx - 160) > DEADZONE or abs(cy - 120) > DEADZONE:
                # Smooth Tracking
                curr_p = int((target_p * SENSITIVITY) + (curr_p * (1 - SENSITIVITY)))
                curr_t = int((target_t * SENSITIVITY) + (curr_t * (1 - SENSITIVITY)))

                pi.set_servo_pulsewidth(PAN_PIN, curr_p)
                pi.set_servo_pulsewidth(TILT_PIN, curr_t)
        else:
            # Releasing motors to prevent humming/heating when target lost
            pi.set_servo_pulsewidth(PAN_PIN, 0)
            pi.set_servo_pulsewidth(TILT_PIN, 0)

        cv2.imshow("Calibrated Sentry", frame)
        if cv2.waitKey(1) & 0xFF == 27: break

finally:
    pi.set_servo_pulsewidth(PAN_PIN, 0)
    pi.set_servo_pulsewidth(TILT_PIN, 0)
    picam2.stop()
    cv2.destroyAllWindows()
    pi.stop()