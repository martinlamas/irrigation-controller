import json
import re
import socket
import time

from machine import Pin, reset
from ntptime import settime

WLAN_SSID = ""
WLAN_PASSWORD = ""
WLAN_CONNECT_DELAY = 10

REQUEST_LINE_REGEX = re.compile(
    r"^(GET|HEAD|POST|PUT|DELETE|CONNECT|OPTIONS|TRACE|PATCH)\s+.+"
)

RESPONSE_STATUS_TEXT = {
    200: "OK",
    404: "Not Found",
    405: "Method Not Allowed",
}


ROUTES = [
    {
        "method": "GET",
        "path": "/valve/status",
        "handler": lambda cl, valve: handle_get_valve_status(cl, valve),
    },
    {
        "method": "POST",
        "path": "/valve/open",
        "handler": lambda cl, valve: handle_open_valve(cl, valve),
    },
    {
        "method": "POST",
        "path": "/valve/close",
        "handler": lambda cl, valve: handle_close_valve(cl, valve),
    },
]


class Valve:
    def __init__(self):
        self.relay_pin = Pin(5, mode=Pin.OUT, value=0)

    def open(self):
        self.relay_pin.value(1)

    def close(self):
        self.relay_pin.value(0)

    def is_open(self):
        return self.relay_pin.value() == 1


def get_route(path):
    try:
        return next((r for r in ROUTES if r["path"] == path))
    except StopIteration:
        return None


def send_json_response(cl, status_code, body=None):
    cl.send(f"HTTP/1.1 {status_code} {RESPONSE_STATUS_TEXT[status_code]}\r\n")

    if body:
        body_str = json.dumps(body)

        cl.send("Content-Type: application/json\r\n")
        cl.send("Content-Length: " + str(len(body_str)) + "\r\n\r\n")
        cl.send(body_str)
    else:
        cl.send("\r\n")

    cl.close()


def handle_get_valve_status(cl, valve):
    send_json_response(cl, 200, {"status": "open" if valve.is_open() else "closed"})


def handle_open_valve(cl, valve):
    valve.open()
    send_json_response(cl, 200)


def handle_close_valve(cl, valve):
    valve.close()
    send_json_response(cl, 200)


def process_request(cl_file):
    method = None
    path = None

    while True:
        line = cl_file.readline()

        if not line or line == b"\r\n":
            break

        decoded_line = line.decode("utf-8")

        if REQUEST_LINE_REGEX.match(decoded_line):
            method = decoded_line.split()[0]
            path = decoded_line.split()[1]

    return method, path


def wlan_connect():
    import network

    network.hostname("irrigation-controller")

    wlan = network.WLAN(network.STA_IF)

    if not wlan.active():
        wlan.active(True)

    if not wlan.isconnected():
        while not wlan.isconnected():
            wlan.connect(WLAN_SSID, WLAN_PASSWORD)
            time.sleep(WLAN_CONNECT_DELAY)

    print("Connected to WLAN:", wlan.ifconfig())


def main():
    wlan_connect()
    settime()

    valve = Valve()

    addr = socket.getaddrinfo("0.0.0.0", 80)[0][-1]

    s = socket.socket()
    s.bind(addr)
    s.listen(1)

    print("Listening on", addr)

    while True:
        cl, addr = s.accept()

        print("Client connected from", addr)
        cl_file = cl.makefile("rwb", 0)

        method, path = process_request(cl_file)

        route = get_route(path)

        if not route:
            send_json_response(cl, 404)
        elif method is not route["method"]:
            send_json_response(cl, 405)
        else:
            handle_request = route["handler"]
            handle_request(cl, valve)


try:
    main()
except:
    reset()
