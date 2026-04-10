__version__ = '0.1.0'

import Config as cfg
from simple_pid import PID
import os
import time
import math


class BottyMcBotFace(object):
    def __init__(self, serial_device):
        self.serial_device = serial_device
        self.yaw_target = 0.
        self.pitch_target = 0.
        self.yaw_vel = 0.
        self.pitch_vel = 0.
        self.trigger_start = 0
        self.is_parked = False
        

        self.configure_feather()
        self.set_pid_tuning(cfg.track_kp, cfg.track_ki, cfg.track_kd)

    """ Motion stuff """

    def configure_feather(self):
        command_string = 'C0'
        for k, v in cfg.Feather_Parameter_Chars.items():
            command_string += ' {}{}'.format(k, v)
        self.serial_device.command(command_string)

    def home(self):
        print('TODO implement this plz')

    def zero(self):
        self.serial_device.command('G92 X0 Y0')

    def enable(self):
        self.serial_device.command('M17')

    def disable(self):
        self.serial_device.command('M84')

    def trigger(self, min_pwm = cfg.trigger_min_pwm, max_pwm = cfg.trigger_max_pwm, time_held_s = cfg.trigger_hold_s, force_off = False):
        """ Call this function continuously and do other stuff while it runs, will return true when it is done """
        if self.trigger_start == 0 and force_off is False:
            self.trigger_start = time.time()
            self.serial_device.command('c1 a{}'.format(max_pwm))
        elif ((time.time() - self.trigger_start) > time_held_s) or force_off is True:
            self.trigger_start = 0
            self.serial_device.command('c1 a{}'.format(min_pwm))
            return True

        return False

    def set_pid_tuning(self, kp, ki, kd):
        self.pitch_pid = PID(kp / 1000000, ki / 1000000, kd / 1000000)
        # self.pitch_pid.output_limits = (-0.015, 0.015)
        self.yaw_pid = PID(kp / 1000000, ki / 1000000, kd / 1000000)
        # self.yaw_pid.output_limits = (-0.015, 0.015)

    def reset_pid(self):
        self.pitch_pid.reset()
        self.yaw_pid.reset()

    def absolute_move(self, yaw_rads, pitch_rads, velocity_mmps=None):
        """ Map target radians to servo degrees and send to Arduino via serial """
        # clamp into travel range [0 .. travel_rads]
        yaw_rads = max(0.0, min(cfg.yaw_travel_rads, yaw_rads))
        pitch_rads = max(0.0, min(cfg.pitch_travel_rads, pitch_rads))

        # Map radians to servo degrees 0..180 (assumes center at 0..travel mapping)
        # You may want to adjust mapping: here 0 rad -> 0 deg, travel_rads -> 180 deg
        yaw_deg = int((yaw_rads / cfg.yaw_travel_rads) * 180.0)
        pitch_deg = int((pitch_rads / cfg.pitch_travel_rads) * 180.0)

        # Save targets
        self.yaw_target = yaw_rads
        self.pitch_target = pitch_rads

        # Send to MCU (SERVO1 = yaw, SERVO2 = pitch)
        # Use serial_device.command(...) which waits for ok
        self.serial_device.command(f"SERVO1:{yaw_deg}")
        self.serial_device.command(f"SERVO2:{pitch_deg}")

    def relative_move(self, yaw_rads = 0, pitch_rads = 0, velocity_mmps = None):
        # Update target radians relative and call absolute
        new_yaw = self.yaw_target + yaw_rads
        new_pitch = self.pitch_target + pitch_rads
        self.absolute_move(new_yaw, new_pitch, velocity_mmps)

    def update_target(self, pitch_pixel_err, yaw_pixel_err, mult=1.0):
        """ Takes in raw pixel errors and determines and sends motor commands """
        # First calculate motor leads
        self.get_velocities()
        pitch_pixel_err += self.pitch_vel * cfg.lead_ahead_constant
        yaw_pixel_err += self.yaw_vel * cfg.lead_ahead_constant

        # Then run through pid with adjusted pixel targets
        pitch_move_rads = self.pitch_pid(pitch_pixel_err) * mult
        yaw_move_rads = self.yaw_pid(yaw_pixel_err) * mult

        # Then command motors
        self.relative_move(yaw_move_rads, pitch_move_rads)

        if cfg.DEBUG_MODE:
            print('PITCH: {}\tcomponents: {}\tlead: {}'.format(pitch_move_rads, self.pitch_pid.components, self.pitch_vel * cfg.lead_ahead_constant))
            print('YAW: {}\tcomponents: {}\tlead: {}'.format(yaw_move_rads, self.yaw_pid.components, self.yaw_vel * cfg.lead_ahead_constant))

        return pitch_move_rads, yaw_move_rads

    def get_velocities(self):
        """ For UNO setup we do not have motor velocity sensors.
            Keep placeholders (0,0) or attempt to read from MCU if implemented.
        """
        # If your MCU supports querying velocity, implement command & parse.
        # For now, set to zero to avoid adding lead compensation.
        self.yaw_vel = 0.0
        self.pitch_vel = 0.0
        return (self.yaw_vel, self.pitch_vel)

    def send_gcode(self, filename):
        with open(os.path.join(cfg.gcode_folder, filename)) as f:
            while(True):
                line = f.readline().strip('\n')
                if not line:
                    break
                
                if line[0] == ';':
                    # Comments start with semicolon
                    continue

                self.serial_device.command(line)

    @property
    def is_homed(self):
        raise Exception('NOT IMPLEMENTED')

    @property
    def xpos_mm(self):
        ret = self.serial_device.command('M114')
        return float(ret.split(',')[0])

    @property
    def ypos_mm(self):
        ret = self.serial_device.command('M114')
        return float(ret.split(',')[1])
