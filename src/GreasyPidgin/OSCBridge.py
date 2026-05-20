from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer
from pythonosc.udp_client import SimpleUDPClient
import threading


class OSCHandler:
    __slots__ = ("address", "fn", "run")

    def __init__(self, address, fn, run=True):
        self.address = str(address)
        self.fn = fn
        self.run = bool(run)

    def __call__(self, address, *args):
        if self.run:
            self.fn(address, *args)


class HandlerRegistry:
    __slots__ = ("handlers",)

    def __init__(self):
        self.handlers = {}

    def add(self, address, fn, run=True):
        h = OSCHandler(address, fn, run)
        self.handlers[h.address] = h
        return h

    def remove(self, address):
        self.handlers.pop(str(address), None)

    def set_run(self, address, state):
        h = self.handlers.get(str(address))
        if h:
            h.run = bool(state)

    def dispatch(self, address, *args):
        h = self.handlers.get(str(address))
        if h:
            h(address, *args)


class OSCBridge:

    def __init__(self,
                 in_ip="127.0.0.1", in_port=12345,
                 out_ip="127.0.0.1", out_port=23456,
                 threaded=False):

        self.threaded = bool(threaded)
        self.in_ip = str(in_ip)
        self.in_port = int(in_port)

        self.client = SimpleUDPClient(out_ip, int(out_port))
        self.handlers = HandlerRegistry()

        self.dispatcher = Dispatcher()
        self.dispatcher.set_default_handler(self._receive)

        self.server = ThreadingOSCUDPServer((self.in_ip, self.in_port), self.dispatcher)
        self._thread = None

    # ---------- send ----------
    def send(self, address, *args):
        self.client.send_message(address, list(args))

    # ---------- receive ----------
    def _receive(self, address, *args):
        # print(f"[OSC IN] {address} {args}")

        # control channel
        if address == "/osc/run":
            # /osc/run <address> <0|1>
            addr = str(args[0])
            state = bool(int(args[1]))
            self.handlers.set_run(addr, state)
            self.send("/osc/ok", "run", addr, int(state))
            return

        if address == "/osc/remove":
            addr = str(args[0])
            self.handlers.remove(addr)
            self.send("/osc/ok", "remove", addr)
            return

        if address == "/osc/list":
            payload = []
            for a, h in self.handlers.handlers.items():
                payload.extend([a, int(h.run)])
            self.send("/osc/list", *payload)
            return

        # normal dispatch
        self.handlers.dispatch(address, *args)

    # ---------- server control ----------
    def start(self):
        print("Stop with KeyboardInterrupt: CRTL+C")
        if self.threaded:
            if self._thread and self._thread.is_alive():
                return
            print(f"Listening (threaded) on {self.in_ip}:{self.in_port}")
            
            self._thread = threading.Thread(
                target=self.server.serve_forever,
                daemon=True
            )
            self._thread.start()
            return

        print(f"Listening (blocking) on {self.in_ip}:{self.in_port}")
        try:
            self.server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def stop(self):
        try:
            self.server.shutdown()
        except Exception:
            pass
        try:
            self.server.server_close()
        except Exception:
            pass