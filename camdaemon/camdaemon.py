#! ./env/bin/python

import asyncio
import concurrent.futures
import errno
import io
import json
import logging
import os
import shutil
import time
import websockets


with open(os.path.join(os.path.dirname(__file__), "..",
                       "config", "default.json")) as f:
    config = json.load(f)


class RealCamera(object):
    def __enter__(self):
        import picamera
        self.cam = picamera.PiCamera(resolution=(640,480)).__enter__()
        self.buf = io.BytesIO()
        # With use_video_port turned on, we can get 30fps video, and
        # surprisingly, it only brings the load average to 0.80 or so
        # (about 25% Python, 8% Node.js, and 6% Nginx, give or take).
        # It does, however, slow down my laptop to render this fast.
        self.capiter = iter(self.cam.capture_continuous(self.buf, format='jpeg',
            use_video_port=config['use_video_port']))
        return self
    def __exit__(self, *args, **kwargs):
        self.buf.close()
        return self.cam.__exit__(*args, **kwargs)
    @asyncio.coroutine
    def wait(self):
        # Use this to yield to the scheduler, and let it process any
        # pending data on the manager socket.
        yield from asyncio.sleep(0)
    def capture(self, filename):
        self.capiter.__next__()
        with open(filename, 'wb') as fh:
            fh.write(self.buf.getbuffer())
        self.buf.seek(0)
        self.buf.truncate()
        

class FakeCamera(object):
    def __enter__(self):
        self.serial = 1
        return self
    def __exit__(self, *args, **kwargs):
        pass
    @asyncio.coroutine
    def wait(self):
        # The real camera currently runs at about 2fps unless
        # use_video_port is on.  We limit the FakeCamera to 0.1fps
        # because we really have no need to clog up networks,
        # particularly if I'm coding on Cloud9 or something.
        yield from asyncio.sleep(10)
    def capture(self, filename):
        logging.debug("Using test image %i", self.serial)
        shutil.copy(os.path.join(os.path.dirname(__file__), "testimgs",
                                 "motion%02i.jpg" % self.serial),
                    filename)
        self.serial = (self.serial % 10) + 1

 
class RealOrFakeCamera(object):
    def __enter__(self):
        use_camera = config['use_camera']
        if use_camera == 'if-enabled':
            try:
                import picamera
                self.backing = RealCamera()
                return self.backing.__enter__()
            except (ImportError, picamera.exc.PiCameraMMALError,
                    picamera.exc.PiCameraError):
                self.backing = FakeCamera()
                return self.backing.__enter__()
        elif use_camera == True:
            self.backing = RealCamera()
            return self.backing.__enter__()
        elif use_camera == False:
            self.backing = FakeCamera()
            return self.backing.__enter__()
        raise Exception('config["use_camera"] must be true, false, or "if-enabled", not %r', use_camera)
    def __exit__(self, *args, **kwargs):
        return self.backing.__exit__(*args, **kwargs)


@asyncio.coroutine
def handle_camera(ws, client_event, loop):
    serial = 0
    while True:
        yield from client_event.wait()
        logging.info("Clients connected; activating")
        with RealOrFakeCamera() as camera:
            logging.debug("Taking picture %i from %s", serial, repr(camera))
            while client_event.is_set():
                filename = 'image%02i.jpg' % serial
                camera.capture(os.path.join(config['camdir'], filename))
                logging.debug("Captured %s", filename)
                msg = json.dumps({"image": filename})
                yield from ws.send(msg)
                serial = (serial + 1) % 100
                yield from camera.wait()
        logging.info("Clients disconnected; entering standby")


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
    logging.basicConfig(format='%(asctime)s %(message)s',
                        level=logging.INFO)
    logging.info("Initializing")

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
            logging.debug("Connecting to %s", config['cammgr_url'])
            ws = yield from websockets.connect(config['cammgr_url'])
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
