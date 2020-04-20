import os, re, time, platform
from serial import Serial
from serial.serialutil import SerialException
from datetime import datetime
class LZFoxReader(object):
    CMD_GET_VERSION = b"GET VERSION\n"
    CMD_GET_VOLTAGE = b"GET VOLTAGE\n"
    CMD_GET_BACKUP = b"GET BACKUP\n"
    CMD_SET_READOUT_MODE = b"SET MODE READOUT\n"

    PUNCH_START = 251
    PUNCH_FINISH = 252

    def __init__(self, port=None, debug=False, logger=None):
        self._debug = debug
        self._logger = logger
        self._logger.debug('Initing LZFox Reader')
        if port is not None:
            self._logger.debug('Port is not none trying to connect')
            self._connect_master_station(port)
        else:
            self._logger.debug('Port is empty looking for port')
            self.port = self._find_port()
        self.init_card_data()
        

    def _find_port(self):
        errors = 'no serial ports found'
        scan_ports = []
        if platform.system() == 'Linux':
            scan_ports = [os.path.join('/dev', f) for f in os.listdir('/dev') if
                            re.match('ttyUSB.*', f)]
        elif platform.system() == 'Windows':
            scan_ports = ['COM' + str(i) for i in range(32)]
        else:
            raise LZFoxException('Unsupported platform: %s' % platform.system())
        
        if len(scan_ports) > 0:
            for port in scan_ports:
                self._logger.debug('Trying port: {}'.format(port))
                try:
                    self._logger.debug('Trying port: {}'.format(port))
                    self._connect_master_station(port)
                    return port
                except LZFoxException as msg:
                    errors += 'port %s: %s\n' % (port, msg)
        raise LZFoxException('No LZFox master station found. Possible reasons: %s' % errors)

    def init_card_data(self):
        self.ret = {}
        self.ret['punches'] = []
        self.ret['card_type'] = 'LXFOX'
        self.ret['start'] = None
        self.ret['finish'] = None
        self.ret['check'] = None
        self.ret['card_number'] = 0

    def get_card_data(self):
        return self.ret

    def _connect_master_station(self, port):
        try:
            self._logger.debug('Opening serial for port: {} on baud: {}'.format(port, 38400))
            self._serial = Serial(port, baudrate=38400, timeout=5)
            # Master station reset on serial open.
            # Wait little time for it startup
            time.sleep(2)
        except (SerialException, OSError):
            raise LZFoxException("Could not open port '%s'" % port)

        try:
            self._serial.reset_input_buffer()
        except (SerialException, OSError):
            raise LZFoxException("Could not flush port '%s'" % port)

        self.port = port
        self.baudrate = self._serial.baudrate
        self.set_readout_mode()
        version = self.read_version()
        if version is not None:
            self._logger.info("Master station %s on port '%s' connected" % (version, port))
        
    def read_version(self):
        response = self._send_command(self.CMD_GET_VERSION)
        if response:
            match = re.search('.*:(.*)\\r\\n', response.decode('utf-8'))
        return match[1] if match else None

    def set_readout_mode(self):
        self._logger.debug("Setting readout mode")
        response = self._send_command(self.CMD_SET_READOUT_MODE)
        self._logger.debug("Readout response: {}".format(response))
        if response:
            match = re.search('.*:([A-Z]+)\s?\\r\\n', response.decode('utf-8'))
            if not match or match[1] != 'READOUT':
                raise LZFoxException("Invalid response from master station on SET MODE - {}: {}".format('READOUT', response))
            self._serial.readline() # fetch last '>'
            return True
        return False

    def _send_command(self, cmd):
        self._serial.write(cmd)
        time.sleep(0.1)
        return self._read_serial()

    def poll_card(self):
        read_data = self._serial.readline()
        line = read_data.decode('utf-8')
        if line.startswith('Card:'):
            match = re.search('Card: (.{2}) (.{2}) (.{2}) (.{2})', line)
            if match:
                card_number_str = "{}{}{}{}".format(match[1], match[2], match[3], match[4])
                card_number = int('0x' + card_number_str, 16) # hex to int
                self.ret['card_number'] = card_number

                punches_data = self._serial.readline()
                punches_line = punches_data.decode('utf-8')

                if punches_line.endswith('%\r\n'):
                    self._parse_punch_data(punches_line)
                    self._logger.debug(self.ret)
                    return self.ret
        return False
        
    def _parse_punch_data(self, data):
        punches = re.findall('(\d+,\d+)', data)
        for punch in punches:
            row = punch.split(',')
            control = int(row[0])
            time = datetime.fromtimestamp(int(row[1]))
            if control == self.PUNCH_START:
                self.ret['start'] = time
            elif control == self.PUNCH_FINISH:
                self.ret['finish'] = time
            else:
                self.ret['punches'].append((control, time))

    def _read_serial(self):
        read_data = self._serial.readline()
        self._logger.debug('Read first line: {}'.format(read_data))
        if read_data not in [b'\r\n', b'>\r\n']: # if first returned line is either of those, then there is no Error, else we throw an Exception
            raise LZFoxException("Invalid response from master station: {}".format(read_data.decode('utf-8')))
        read_data = self._serial.readline()
        return read_data

    def disconnect(self):
        self._serial.close()
    
    def reconnect(self):
        self.disconnect()
        self._connect_master_station(self._serial.port)


class LZFoxException(Exception):
    pass


class LZFoxTimeout(LZFoxException):
    pass