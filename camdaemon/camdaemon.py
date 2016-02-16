#! ./env/bin/python

import asyncio
import codecs
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

 
class Camera(object):
    singleton = None
    def __new__(cls):
        if cls.singleton is None:
            cls.singleton = super(Camera, cls).__new__(cls)
        return cls.singleton
    def __init__(self):
        self.users = 0
        self.backing = None
        self.backing_withobj = None

    def __get_backing(self):
        use_camera = config['use_camera']
        if use_camera == 'if-enabled':
            try:
                import picamera
                self.backing = RealCamera().__enter__()
                return self.backing
            except (ImportError, picamera.exc.PiCameraMMALError,
                    picamera.exc.PiCameraError):
                self.backing = FakeCamera().__enter__()
                return self.backing
        elif use_camera == True:
            self.backing = RealCamera().__enter__()
            return self.backing
        elif use_camera == False:
            self.backing = FakeCamera().__enter__()
            return self.backing
        raise Exception('config["use_camera"] must be true, false, or "if-enabled", not %r', use_camera)

    def __enter__(self):
        if self.backing is None:
            self.backing = self.__get_backing()
        self.users += 1
        return self.backing
    def __exit__(self, *args, **kwargs):
        self.users -= 1
        if self.users == 0:
            self.backing.__exit__(*args, **kwargs)
            self.backing = None
        

@asyncio.coroutine
def scgi_client_callback(reader, writer):
    logging.info("New SCGI client")
    try:
        headerlen_str = b""
        while True:
            headerlen_char = yield from reader.readexactly(1)
            if headerlen_char == b':':
                break
            headerlen_str += headerlen_char
        headerlen = int(codecs.decode(headerlen_str))
        header_str = yield from reader.readexactly(headerlen - 1)
        terminator = yield from reader.readexactly(2)
        assert terminator == b'\0,'
        header_array = header_str.split(b'\0')
        headers = {}
        while header_array:
            value = codecs.decode(header_array.pop())
            key = codecs.decode(header_array.pop())
            headers[key] = value
        logging.debug("SCGI request: %r", headers)

        logging.info("%s %s %s", headers["REMOTE_ADDR"],
                     headers["REQUEST_METHOD"], headers["REQUEST_URI"])

        if headers["REQUEST_METHOD"] != "GET":
            writer.write(b"Status: 405 Method Not Allowed\r\n\r\n")
            writer.write_eof()
            yield from writer.drain()
            return
        if headers["DOCUMENT_URI"] == "/cam/vid/_headers":
            writer.write(b"Status: 200 OK\r\nContent-Type: text/plain\r\n\r\n")
            writer.write(codecs.encode(repr(headers)))
            writer.write_eof()
            yield from writer.drain()
            return
        if headers["DOCUMENT_URI"] != "/cam/vid":
            writer.write(b"Status: 404 Not Found\r\n\r\n")
            writer.write_eof()
            yield from writer.drain()
            return

        writer.write(b"Status: 200 OK\r\nContent-Type: text/plain\r\n\r\n")
        for i in range(5):
            writer.write(b"TODO\n")
            yield from writer.drain()
            yield from asyncio.sleep(1)
        writer.write_eof()
        yield from writer.drain()
    except asyncio.IncompleteReadError:
        pass


@asyncio.coroutine
def handle_camera(ws, client_event, loop):
    serial = 0
    while True:
        yield from client_event.wait()
        logging.info("Clients connected; activating")
        with Camera() as camera:
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

    scgi_server = asyncio.start_server(scgi_client_callback, port=8082,
                                       loop=loop)

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
