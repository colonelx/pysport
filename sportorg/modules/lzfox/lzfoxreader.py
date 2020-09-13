import datetime
import logging
from threading import main_thread, Event
import os
import platform
import re
import time
from PySide2.QtCore import QThread, Signal
from queue import Queue, Empty
from sportorg.common.singleton import singleton
from sportorg.models import memory
from sportorg.utils.time import time_to_otime
from sportorg.libs.lzfox.lzfoxreader import LZFoxReader

class LZFoxReaderCommand:
    def __init__(self, command, data=None):
        self.command = command
        self.data = data


class LZFoxReaderThread(QThread):
    POLL_TIMEOUT = 0.2
    def __init__(self, port, queue, stop_event, logger, debug=False):
        super().__init__()
        # self.setName(self.__class__.__name__)
        self.setObjectName(self.__class__.__name__)
        self._port = port
        self._queue = queue
        self._stop_event = stop_event
        self._logger = logger
        self._debug = debug

    def run(self):
        try:
            lzfox = LZFoxReader(port=self._port, logger=logging.root)
            self._logger.debug('reader thread')
        except Exception as e:
            self._logger.error(str(e))
            return

        while True:
            if not main_thread().is_alive() or self._stop_event.is_set():
                lzfox.disconnect()
                self._logger.debug('Stop lzfox reader')
                return
            time.sleep(self.POLL_TIMEOUT)
            try:
                data = lzfox.poll_card()
                if data:
                    self._logger.debug('Adding to queue: {}'.format(data))
                    self._queue.put(LZFoxReaderCommand('card_data', data), timeout=1)
            except Exception as e:
                self._logger.error(str(e))
                return


class ResultThread(QThread):
    data_sender = Signal(object)

    def __init__(self, queue, stop_event, logger, start_time=None):
        super().__init__()
        # self.setName(self.__class__.__name__)
        self.setObjectName(self.__class__.__name__)
        self._queue = queue
        self._stop_event = stop_event
        self._logger = logger
        self.start_time = start_time

    def run(self):
        time.sleep(3)
        while True:
            try:
                cmd = self._queue.get(timeout=5)
                if cmd.command == 'card_data':
                    result = self._get_result(self._check_data(cmd.data))
                    self.data_sender.emit(result)
                    #backup.backup_data(cmd.data)
            except Empty:
                if not main_thread().is_alive() or self._stop_event.is_set():
                    break
            except Exception as e:
                self._logger.error(str(e))
        self._logger.debug('Stop adder result')

    def _check_data(self, card_data):
        return card_data

    @staticmethod
    def _get_result(card_data):
        result = memory.race().new_result(memory.ResultLZFox)
        result.card_number = card_data['card_number'] 

        for i in range(len(card_data['punches'])):
            t = card_data['punches'][i][1]
            if t:
                split = memory.Split()
                split.code = str(card_data['punches'][i][0])
                split.time = time_to_otime(t)
                split.days = memory.race().get_days(t)
                print(split.__dict__)
                if split.code != '0' and split.code != '':
                    result.splits.append(split)

        if card_data['start']:
            result.start_time = time_to_otime(card_data['start'])
        if card_data['finish']:
            result.finish_time = time_to_otime(card_data['finish'])

        return result

    @staticmethod
    def time_to_sec(value, max_val=86400):
        if isinstance(value, datetime.datetime):
            ret = value.hour * 3600 + value.minute * 60 + value.second + value.microsecond / 1000000
            if max_val:
                ret = ret % max_val
            return ret

        return 0

@singleton
class LZFoxReaderClient:
    def __init__(self):
        self._queue = Queue()
        self._stop_event = Event()
        self._reader_thread = None
        self._result_thread = None
        self._logger = logging.root
        self._call_back = None

    def set_call(self, value):
        if self._call_back is None:
            self._call_back = value
        return self

    def _start_reader_thread(self):
        if self._reader_thread is None:
            self._reader_thread = LZFoxReaderThread(
                self.port,
                self._queue,
                self._stop_event,
                self._logger,
                debug=True
            )
            self._reader_thread.start()
        # elif not self._reader_thread.is_alive():
        elif self._reader_thread.isFinished():
            self._reader_thread = None
            self._start_reader_thread()

    def _start_result_thread(self):
        if self._result_thread is None:
            self._result_thread = ResultThread(
                self._queue,
                self._stop_event,
                self._logger,
                self.get_start_time()
            )
            if self._call_back is not None:
                self._result_thread.data_sender.connect(self._call_back)
            self._result_thread.start()
        # elif not self._result_thread.is_alive():
        elif self._result_thread.isFinished():
            self._result_thread = None
            self._start_result_thread()

    def is_alive(self):
        if self._reader_thread is not None and self._result_thread is not None:
            # return self._reader_thread.is_alive() and self._result_thread.is_alive()
            return not self._reader_thread.isFinished() and not self._result_thread.isFinished()

        return False

    def start(self):
        print('here')
        self.port = self.choose_port()
        self._stop_event.clear()
        self._start_reader_thread()
        self._start_result_thread()

    def stop(self):
        self._stop_event.set()
        self._logger.info('Closing connection')

    def toggle(self):
        if self.is_alive():
            self.stop()
            return
        self.start()

    @staticmethod
    def get_start_time():
        start_time = memory.race().get_setting('system_zero_time', (8, 0, 0))
        return datetime.datetime.today().replace(
            hour=start_time[0],
            minute=start_time[1],
            second=start_time[2],
            microsecond=0
        )

    def choose_port(self):
        return memory.race().get_setting('system_port', None)