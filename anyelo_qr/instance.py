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
        """Si ya hay otra copia abierta, le avisa y devuelve True.
        Basta con conectarse: en Windows el mensaje puede perderse si esta copia se cierra enseguida."""
        sock = QLocalSocket()
        sock.connectToServer(self.name)
        if not sock.waitForConnected(400):
            return False
        sock.write(b"show")
        sock.flush()
        sock.waitForBytesWritten(400)
        sock.waitForReadyRead(300)        # le da tiempo a la otra copia de reaccionar antes de cerrar
        sock.disconnectFromServer()
        return True

    def listen(self, callback: Callable[[], None]) -> None:
        self._callback = callback
        QLocalServer.removeServer(self.name)      # limpia restos de una sesión que se cerró mal
        self.server = QLocalServer(self)
        self.server.listen(self.name)
        self.server.newConnection.connect(self._on_connection)

    def _on_connection(self):
        """Cada conexión nueva es un aviso: otra copia quiere que esta se muestre."""
        while self.server and self.server.hasPendingConnections():
            sock = self.server.nextPendingConnection()
            self._sockets.append(sock)
            sock.disconnected.connect(lambda s=sock: self._forget(s))
            sock.write(b"ok")
            sock.flush()
            if self._callback:
                self._callback()

    def _forget(self, sock: QLocalSocket):
        if sock in self._sockets:
            self._sockets.remove(sock)
        sock.deleteLater()
