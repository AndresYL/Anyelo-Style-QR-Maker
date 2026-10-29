"""Una sola copia del programa: si lo abres de nuevo, trae a la primera al frente."""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QObject
from PySide6.QtNetwork import QLocalServer, QLocalSocket

DEFAULT_NAME = "AnyeloStyleQR-instance"


class InstanceGuard(QObject):
    def __init__(self, name: str = DEFAULT_NAME):
        super().__init__()
        self.name = name
        self.server: QLocalServer | None = None
        self._callback: Callable[[], None] | None = None
        self._sockets: list[QLocalSocket] = []

    def notify_running(self) -> bool:
        """Si ya hay otra copia abierta, le pide que se muestre y devuelve True."""
        sock = QLocalSocket()
        sock.connectToServer(self.name)
        if sock.waitForConnected(400):
            sock.write(b"show")
            sock.flush()
            sock.waitForBytesWritten(400)
            sock.disconnectFromServer()
            return True
        return False

    def listen(self, callback: Callable[[], None]) -> None:
        self._callback = callback
        QLocalServer.removeServer(self.name)      # limpia restos de una sesión que se cerró mal
        self.server = QLocalServer(self)
        self.server.listen(self.name)
        self.server.newConnection.connect(self._on_connection)

    def _on_connection(self):
        while self.server and self.server.hasPendingConnections():
            sock = self.server.nextPendingConnection()
            self._sockets.append(sock)
            sock.readyRead.connect(lambda s=sock: self._on_data(s))
            if sock.bytesAvailable():
                self._on_data(sock)

    def _on_data(self, sock: QLocalSocket):
        sock.readAll()
        if self._callback:
            self._callback()
