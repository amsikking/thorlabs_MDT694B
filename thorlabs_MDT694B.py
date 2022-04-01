import time
import serial

class Controller:
    '''
    Basic device adaptor for thorlabs MDT694B single channel open-loop
    piezo controller. Many more commands are available and have not been
    implemented.
    '''
    def __init__(
        self, which_port, name='MDT694B', verbose=True, very_verbose=False):
        self.name = name
        self.verbose = verbose
        self.very_verbose = very_verbose
        if self.verbose: print('%s: opening...'%self.name, end='')
        try:
            self.port = serial.Serial(
                port=which_port, baudrate=115200, timeout=5)
        except serial.serialutil.SerialException:
            raise IOError(
                '%s: no connection on port %s'%(self.name, which_port))
        assert self._send('restore')[0] == (
            'All settings restored to default values.')
        self.id = self._send('id?')
        assert self.id[0] == 'Model MDT694B Piezo Control Module'
        assert self.id[1] == 'Firmware Version: 1.10'
        if self.verbose: print(" done.")
        voltage_limits = (75, 100, 150)
        self.voltage_limit = int(self._send('vlimit?', remove_brackets=True)[0])
        assert self.voltage_limit in voltage_limits
        self.get_voltage(verbose=False)
        self._pending_cmd = None
        if self.verbose:
            for line in self.id:
                print('%s: id = %s'%(self.name, line))
            print('%s: voltage limit setting = %iv'%(
                self.name, self.voltage_limit))
            print('%s: voltage = %iv'%(self.name, self.voltage))

    def _send(self, cmd, remove_brackets=False):
        if self.very_verbose:
            print("\n%s: sending cmd = '%s'"%(self.name, cmd))
        self.port.write(bytes(cmd + '\n', encoding='ascii'))
        response = self.port.read_until(b'>').decode('ascii').rstrip('>')
        assert self.port.inWaiting() == 0
        assert response.split('\n')[0] == cmd   # check echo
        response = response.split('\n')[1]      # remove echo
        response = response.split('\r')         # split up lines
        responses = []
        for r in response:
            if r!= '':                          # remove empty lines
                if remove_brackets:
                    r = r.replace('[','').replace(']','')
                responses.append(r)
        if self.very_verbose:
            for r in responses:
                    print("%s:  response  = "%self.name, r)
        return responses

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
                self.voltage = final_voltage
                break
        if self.verbose:
            print('\n%s: voltage settled at %0.2fv'%(self.name, self.voltage))
        self._pending_cmd = None
        return None

    def get_voltage(self, verbose=True):
        self.voltage = float(self._send('xvoltage?', remove_brackets=True)[0])
        if verbose:
            print('%s: voltage = %0.2fv'%(self.name, self.voltage))
        return self.voltage

    def set_voltage(self, voltage, block=True):
        if self._pending_cmd is not None:
            self._finish_set_voltage()
        if self.verbose:
            print('%s: setting to: %0.2fv'%(self.name, voltage))
        target_voltage = float(voltage)
        assert 0 <= target_voltage <= self.voltage_limit, (
            '%s: requested voltage out of range'%self.name)
        cmd = 'xvoltage=%0.2f'%target_voltage
        self._send(cmd)
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
    piezo = Controller('COM7', verbose=True, very_verbose=False)
    print('(initialze time: %0.4fs)'%(time.perf_counter() - start))

##    piezo._send('?')

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

    print('\nSome random moves - no waiting for settle!:')
    from random import randrange
    for moves in range(5):
        random_voltage = randrange(0, 10)
        piezo.set_voltage(random_voltage, block=False)
        piezo._pending_cmd = None
    piezo.set_voltage(0)

    piezo.close()
