import serial
import struct
import time

'''Control of Pololu Maestro servo controllers via serial.'''

class _Servo(object):
    
    '''Provides an object-oriented interface for servos. Not to be instantiated directly.'''

    maximum = 0
    minimum = 0
    range = 0
    
    def __init__(self, controller, id):
        self._id = id
        self._controller = controller
        self._speed = 0
        self._acceleration = 0
        self._target = 0
        
    def degrees_to_pwm(self, value):
        '''Convenience function only. All module code uses native pwm values.'''
        return value * (self.maximum - self.minimum) / self.range
        
    def _set_target(self, value):
        #limit checking is not provided by the controller object, so add it here
        if self.maximum != 0 and self.minimum != 0:
            value = max(min(value, self.maximum), self.minimum)
        self._target = value
        self._controller.set_target(self._id, value)

    @property
    def target(self):
        return self._target
    @target.setter
    def target(self, value):
        self._set_target(value)
        
    @property
    def position(self):
        return self._controller.get_position(self._id)
    @position.setter
    def position(self, value):
        self._set_target(value)

    @property
    def speed(self):
        return self._speed
    @speed.setter
    def speed(self, value):
        self._speed = value
        self._controller.set_speed(self._id, value)

    @property
    def acceleration(self):
        return self._acceleration
    @acceleration.setter
    def acceleration(self, value):
        self._acceleration = value
        self._controller.set_acceleration(self._id, value)


class Maestro(object):	
    
    '''Representation of a controller board.'''
    
    def __init__(self, port='/dev/ttyACM0', servos = []):
        '''Open connection to controller board.
        
        Keyword Arguments:
        port -- location of serial port as used by pyserial
        servos -- names for servo channels in order from 0, required for using the OOP interface
        '''
        self.serial = serial.Serial(port, 9600, timeout=1)
        self.servo = {}
        id = 0
        for name in servos:
            self.servo[name] = _Servo(self, id)
            id += 1
        
    def set_target(self, servo, position):
        '''position is a float representing pulse width in micro seconds.'''
        self._set_value(0x84, servo, int(position * 4))
        
    def set_speed(self, servo, speed):
        '''speed is a float representing change in pulsewidth by microseconds per millisecond.'''
        self._set_value(0x87, servo, int(speed * 4 * 10))
        
    def set_acceleration(self, servo, acceleration):
        '''acceleration is a float representing change in pulsewidth by microseconds per millisecond per millisecond.'''
        self._set_value(0x87, servo, int(acceleration * 4 * 10 * 80))
        
    def go_home():
        '''Reset to default positions as saved on the board.'''
        self.serial.write(chr(0xA2))
        
    def get_position(self, servo):
        '''Returns float representing pulse width in micro seconds.'''
        self.serial.write('{}{}'.format(chr(0x90), chr(servo)))
        response = self.serial.read(2)
        return float(struct.unpack('<H', response)[0]) / 4

    def get_moving_state(self):
        self.serial.write(chr(0x93))
        response = self.serial.read(1)
        return struct.unpack('<?', response)[0]
        
    def get_errors(self):
        self.serial.write(chr(0xA1))
        response = self.serial.read(2)
        bits = struct.unpack('<H', response)[0]
        errors = {}
        errors['serial_signal_error'] = bool(bits & 0x01)
        errors['serial_overrun_error'] = bool(bits & 0x02)
        errors['serial_rx_buffer_full'] = bool(bits & 0x03)
        errors['serial_crc_error'] = bool(bits & 0x04)
        errors['serial_protocol_error'] = bool(bits & 0x05)
        errors['serial_timeout_error'] = bool(bits & 0x06)
        errors['script_stack_error'] = bool(bits & 0x07)
        errors['script_call_stack_error'] = bool(bits & 0x08)
        errors['script_program_counter_error'] = bool(bits & 0x09)
        return errors
        
    def wait_till_stopped(self, period = 0.25):
        '''Blocks until all servos are done moving.'''
        while self.get_moving_state():
            time.sleep(period)
        
    def _set_value(self, command, servo, value):
        if value >= 16384:
            raise OverflowError
        if value < 0:
            raise ValueError
        value_hi = (value & 0b0011111110000000) >> 7
        value_lo = value & 0b1111111
        self.serial.write('{}{}{}{}'.format(chr(command), chr(servo), chr(value_lo), chr(value_hi)))
