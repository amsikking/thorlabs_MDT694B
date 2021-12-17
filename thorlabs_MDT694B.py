import time
import serial

class Controller:
    '''
    Basic device adaptor for thorlabs MDT694B single channel open-loop
    piezo controller. Many more commands are available and have not been
    implemented.
    '''
    def __init__(self, which_port, name='MDT694B', verbose=True):
        self.name = name
        self.verbose = verbose
        if self.verbose: print('%s: opening...'%self.name, end='')
        try:
            self.port = serial.Serial(port=which_port, baudrate=115200)
        except serial.serialutil.SerialException:
            raise IOError(
                '%s: no connection on port %s'%(self.name, which_port))
        response = self._send(b'restore\n', response_bytes=51) # reset
        assert response == (
            b'restore\n*All settings restored to default values.\r*')
        if self.verbose: print(" done.")
        voltage_limits = (75, 100, 150)
        response = self._send(b'vlimit?\n', response_bytes=16) # check limits
        vlimit = int(response.decode('ascii')[-6:-2])
        assert vlimit in voltage_limits
        self.voltage_limit = vlimit
        if self.verbose:
            print('%s: voltage limit setting = %iv'%(self.name, vlimit))
            self.get_voltage()
        self._pending_cmd = None

    def _send(self, cmd, response_bytes=None):
        self.port.write(cmd)
        if response_bytes is not None:
            response = self.port.read(response_bytes)
        else:
            response = None
        assert self.port.inWaiting() == 0
        return response

    def _finish_set_voltage(self, polling_wait_s=0.2):
        if self._pending_cmd is None:
            return
        if self.verbose: print('%s: ...'%self.name, end='')
        while True:
            initial_voltage = self.get_voltage(verbose=False)
            if self.verbose: print('.', end='')
            time.sleep(polling_wait_s)
            final_voltage = self.get_voltage(verbose=False)
            if initial_voltage == final_voltage:
                break
        if self.verbose:
            print('\n%s: voltage settled at %0.2fv'%(self.name, final_voltage))
        self._pending_cmd = None
        return final_voltage

    def get_voltage(self, verbose=True):
        response = self._send(b'xvoltage?\n', response_bytes=20)
        voltage = float(response.decode('ascii')[-8:-2])
        if verbose:
            print('%s: voltage = %0.2fv'%(self.name, voltage))
        return voltage

    def set_voltage(self, voltage, block=True):
        if self._pending_cmd is not None:
            self._finish_set_voltage()
        if self.verbose:
            print('%s: setting to: %0.2fv'%(self.name, voltage))
        target_voltage = float(voltage)
        assert 0 <= target_voltage <= self.voltage_limit, (
            '%s: requested voltage out of range'%self.name)
        cmd = ('xvoltage=%0.2f\n'%target_voltage).encode('ascii')
        self._send(cmd, response_bytes=len(cmd) + 1) # echo
        self._pending_cmd = cmd
        if block:
            self._finish_set_voltage()
        return None

    def close(self):
        if self.verbose: print("%s: closing..."%self.name, end='')
        self.port.close()
        if self.verbose: print(" done.")
        return None

if __name__ == '__main__':
    start = time.perf_counter()
    piezo = Controller('COM7')
    print('(initialze time: %0.4fs)'%(time.perf_counter() - start))
   
    print('\nSet voltage call: regular')
    start = time.perf_counter()
    piezo.set_voltage(0)
    print('(time: %0.4fs)'%(time.perf_counter() - start))

    print('\nSet voltage call: non-blocking + finish')
    start = time.perf_counter()
    piezo.set_voltage(0, block=False)
    print('(non-blocking time: %0.4fs)'%(
        time.perf_counter() - start))
    piezo._finish_set_voltage()
    print('(non-blocking + finish time: %0.4fs)'%(
        time.perf_counter() - start))

    print('\nSet voltage: Non-blocking + forget to finish, then finish!')
    piezo.set_voltage(0, block=False)
    piezo.set_voltage(piezo.voltage_limit, block=False)
    piezo._finish_set_voltage(polling_wait_s=0.25) # adjust polling time

    print('\nSome random moves:')
    from random import randrange
    for moves in range(5):
        random_voltage = randrange(0, piezo.voltage_limit)
        piezo.set_voltage(random_voltage)
    piezo.set_voltage(0)

    piezo.close()
