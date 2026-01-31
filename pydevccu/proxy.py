"""ServerProxy implementation with lock when request is executing."""

from __future__ import annotations

import threading
from typing import Any
import xmlrpc.client


# pylint: disable=too-few-public-methods
class LockingServerProxy(xmlrpc.client.ServerProxy):
    """ServerProxy implementation with lock when request is executing."""

    def __init__(self, uri: str, *args: Any, **kwargs: Any) -> None:
        """Initialize new proxy for server and get local ip."""
        self.lock = threading.Lock()
        self._uri = uri
        xmlrpc.client.ServerProxy.__init__(self, uri, *args, **kwargs)

    @property
    def uri(self) -> str:
        """Return the server URI."""
        return self._uri

    def __request(self, *args: Any, **kwargs: Any) -> Any:
        """Call method on server side."""
        with self.lock:
            parent = xmlrpc.client.ServerProxy
            # Access parent's private method via name mangling
            return parent._ServerProxy__request(self, *args, **kwargs)  # type: ignore[attr-defined]

    def __getattr__(self, *args: Any, **kwargs: Any) -> Any:
        """Magic method dispatcher."""
        return xmlrpc.client._Method(self.__request, *args, **kwargs)
