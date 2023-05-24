#from .user import 90kv_intouch
import json
import requests
import time
from threading import Thread
from queue import Queue, Empty, Full

def syncData(deviceLocation):

	data = {"device":deviceLocation}

	r = requests.post(
		'https://hybihib2.glitch.me/',
		json=data
	)

	return(float(r.text))

class AveragingServer(Thread):

    def __init__(self, num_devices):
        self.queue = Queue()
        if type(num_devices) is not int or num_devices < 1:
            raise ValueError('num_devices must be at least 1.')
        self.num_devices = num_devices
        self.canceling = False
        self.current_avg = 0
        self.ever_connected = False
        Thread.__init__(self)

    def cancel(self):
        self.canceling = True

    def current_average(self):
        return self.current_avg

    def add_location(self, location):
        try:
            self.queue.put_nowait(location)
        except Full:
            self._trim_queue()
            self.queue.put_nowait(location)

    def _trim_queue(self):
        while self.queue.qsize() > self.num_devices*10:
            # always trim in multiples of the number of devices writing synchronously to the queue
            try:
                for _ in range(self.num_devices):
                    self.queue.get_nowait()
            except Empty:
                break # qsize > 0 does not guarantee item available

    def run(self):
        print('averaging client start')
        while not self.canceling:
            self._trim_queue()
            try:
                for _ in range(self.num_devices):
                    self.current_avg = syncData(self.queue.get_nowait())
                    if not self.ever_connected:
                        print(f'connected to remote server. current queue size: {self.queue.qsize()}. current average: {self.current_average()}')
                        self.ever_connected = True
            except Empty:
                pass
            time.sleep(.1)
        print(f'canceled averaging server thread; shutting down. final queue size: {self.queue.qsize()}. final average: {self.current_average()}')
        return False

if __name__ == '__main__':
    avg_server = AveragingServer(2)
    try:
        avg_server.start()
        avs = avg_server
        import pdb; pdb.set_trace()
    finally:
        avg_server.cancel()

