import logging
from queue import Queue
from threading import Event

from PyQt5.QtCore import QThread, pyqtSignal

from sportorg.core.singleton import singleton
from .client import ClientThread
from .server import ServerThread, Command


class ResultThread(QThread):
    data_sender = pyqtSignal(object)

    def __init__(self, queue, stop_event, logger=None):
        super().__init__()
        # self.setName(self.__class__.__name__)
        self._queue = queue
        self._stop_event = stop_event
        self._logger = logger

    def run(self):
        while True:
            cmd = self._queue.get()
            self.data_sender.emit(cmd)


@singleton
class Teamwork(object):
    def __init__(self):
        self._in_queue = Queue()
        self._out_queue = Queue()
        self._stop_event = Event()
        self.factory = {
            'client': ClientThread,
            'server': ServerThread
        }
        self._thread = None
        self._result_thread = None
        self._call_back = None
        self._logger = logging.root

        self.host = ''
        self.port = 50010
        self.connection_type = 'client'

    def set_call(self, value):
        if self._call_back is None:
            self._call_back = value
        return self

    def set_options(self, host, port, connection_type):
        self.host = host
        self.port = port
        self.connection_type = connection_type

    def _start_thread(self):
        if self.connection_type not in self.factory.keys():
            return
        if self._thread is None:
            self._thread = self.factory[self.connection_type](
                (self.host, self.port),
                self._in_queue,
                self._out_queue,
                self._stop_event,
                self._logger
            )
            self._thread.start()
        elif not self._thread.is_alive():
            self._thread = None
            self._start_thread()

    def _start_result_thread(self):
        if self._result_thread is None:
            self._result_thread = ResultThread(
                self._out_queue,
                self._stop_event,
                self._logger
            )
            if self._call_back is not None:
                self._result_thread.data_sender.connect(self._call_back)
            self._result_thread.start()
        # elif not self._result_thread.is_alive():
        elif self._result_thread.isFinished():
            self._result_thread = None
            self._start_result_thread()

    def is_alive(self):
        return self._thread is not None and self._thread.is_alive() \
               and self._result_thread is not None and not self._result_thread.isFinished()

    def stop(self):
        self._stop_event.set()

    def start(self):
        self._stop_event.clear()
        self._in_queue.queue.clear()
        self._out_queue.queue.clear()

        self._start_thread()
        self._start_result_thread()

    def toggle(self):
        if self.is_alive():
            self.stop()
        else:
            self.start()

    def send(self, data):
        if self.is_alive():
            if isinstance(data, Command):
                self._in_queue.put(data)
                return
            self._in_queue.put(Command(data))
