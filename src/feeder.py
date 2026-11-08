"""Treat dispenser interface.

``MockFeeder`` logs only (laptop demo without hardware).
``SerialFeeder`` sends a one-line command to an ESP32/Arduino over USB serial; the
microcontroller drives the servo. Protocol: host sends ``D\\n``, device replies ``OK\\n``.
"""
from __future__ import annotations

import logging
import threading

log = logging.getLogger(__name__)


class Feeder:
    def dispense(self) -> bool:
        raise NotImplementedError


class MockFeeder(Feeder):
    def __init__(self) -> None:
        self.count = 0

    def dispense(self) -> bool:
        self.count += 1
        log.info("[feeder] (mock) treat dispensed #%d", self.count)
        return True


class SerialFeeder(Feeder):
    def __init__(self, port: str, baudrate: int = 115200, timeout_s: float = 2.0):
        import serial  # pyserial, imported lazily so it is optional
        self._serial = serial.Serial(port, baudrate=baudrate, timeout=timeout_s)
        self._lock = threading.Lock()

    def dispense(self) -> bool:
        with self._lock:
            self._serial.reset_input_buffer()
            self._serial.write(b"D\n")
            reply = self._serial.readline().strip()
        ok = reply == b"OK"
        if not ok:
            log.error("[feeder] unexpected reply: %r", reply)
        return ok
