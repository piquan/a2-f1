#! ./ENV/bin/python

import asyncio
import concurrent.futures
import errno
import logging
import json
import os
import shutil
import time
import websockets


with open(os.path.join(os.path.dirname(__file__), "..", "system", "config.json")) as f:
    config = json.load(f)
    print(repr(config))


class RealCamera(object):
    def __enter__(self):
        import picamera
        self.cam = picamera.PiCamera(resolution=(640,480)).__enter__()
        return self
    def __exit__(self, *args, **kwargs):
        self.cam.__exit__(*args, **kwargs)
    def wait(self):
        pass
    @asyncio.coroutine
    def capture(self, filename):
        self.cam.capture(filename)
        
        
class FakeCamera(object):
    def __enter__(self):
        self.serial = 1
        return self
    def __exit__(self, *args, **kwargs):
        pass
    @asyncio.coroutine
    def wait(self):
        yield from asyncio.sleep(10)
    def capture(self, filename):
        logging.debug("Using test image %i", self.serial)
        shutil.copy(os.path.join(os.path.dirname(__file__), "testimgs",
                                 "motion%02i.jpg" % self.serial),
                    filename)
        self.serial = (self.serial % 10) + 1
        
        
def getcam():
    if config['usecamera']:
        return RealCamera()
    else:
        return FakeCamera()


@asyncio.coroutine
def handle_camera(ws, client_event, loop):
    serial = 0
    camera = getcam()
    while True:
        yield from client_event.wait()
        logging.debug("Clients connected, taking pictures")
        with getcam() as camera:
            logging.debug("Taking picture %i from %s", serial, repr(camera))
            while client_event.is_set():
                filename = 'image%02i.jpg' % serial
                camera.capture(os.path.join(config['camdir'], filename))
                logging.debug("Captured %s", filename)
                msg = json.dumps({"image": filename})
                yield from ws.send(msg)
                serial = (serial + 1) % 100
                yield from camera.wait()
        logging.debug("No clients, waiting")


@asyncio.coroutine
def handle_server_messages(ws, client_event, loop):
    while True:
        logging.debug("Watching for cpanel message")
        msg_json = yield from ws.recv()
        logging.debug("cpanel message: %s", msg_json)
        msg = json.loads(msg_json)
        if "client_count" in msg:
            client_count = msg["client_count"]
            logging.debug("Client count: %i", client_count)
            if client_count == 0:
                client_event.clear()
            else:
                client_event.set()


@asyncio.coroutine
def asyncmain(loop):
    logging.basicConfig(level=logging.DEBUG)
    logging.debug("Initializing")

    try:
        os.mkdir(config['camdir'])
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise

    # Preserve these coroutines throughout the loop, so that they don't
    # lose their state during reconnects.
    client_event = asyncio.Event()

    while True:
        try:
            logging.debug("Connecting to %s", config['cpanel_cammgr_url'])
            ws = yield from websockets.connect(config['cpanel_cammgr_url'])
            logging.debug("Connected")

            tasks = [handle_server_messages(ws, client_event, loop),
                     handle_camera(ws, client_event, loop)]
            done, pending = yield from asyncio.wait(tasks,
                                return_when=concurrent.futures.FIRST_EXCEPTION)
            logging.debug("Long-running tasks exited: %r ; %r", done, pending)
            raise done.pop().exception()
        except ConnectionRefusedError as e:
            logging.warning("Connection error (retrying in 5 seconds): %s", e)
            yield from asyncio.sleep(5)
        except websockets.exceptions.InvalidHandshake as e:
            logging.warning("Connection error (retrying in 5 seconds): %s", e)
            yield from asyncio.sleep(5)
        except websockets.exceptions.ConnectionClosed as e:
            logging.warning("Server disconnected: %s %s", e.code, e.reason)
            yield from asyncio.sleep(1)


def main():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(asyncmain(loop))
    loop.close()


if __name__ == '__main__':
    main()
