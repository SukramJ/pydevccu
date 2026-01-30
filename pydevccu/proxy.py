"""
ServerProxy implementation with lock when request is executing
"""

from __future__ import annotations

import threading
import xmlrpc.client


# pylint: disable=too-few-public-methods
class LockingServerProxy(xmlrpc.client.ServerProxy):
    """
    ServerProxy implementation with lock when request is executing
    """

    def __init__(self, *args, **kwargs):
        """
        Initialize new proxy for server and get local ip
        """
        self.lock = threading.Lock()
        xmlrpc.client.ServerProxy.__init__(self, *args, **kwargs)

    def __request(self, *args, **kwargs):
        """
        Call method on server side
        """

        with self.lock:
            parent = xmlrpc.client.ServerProxy
            # pylint: disable=protected-access
            return parent._ServerProxy__request(self, *args, **kwargs)

    # pylint: disable=arguments-differ
    def __getattr__(self, *args, **kwargs):
        """
        Magic method dispatcher
        """

        return xmlrpc.client._Method(self.__request, *args, **kwargs)
