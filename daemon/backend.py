#
# Copyright (C) 2026 pdnguyen of HCMC University of Technology VNU-HCM.
# All rights reserved.
# This file is part of the CO3093/CO3094 course.
#
# AsynapRous release
#
# The authors hereby grant to Licensee personal permission to use
# and modify the Licensed Source Code for the sole purpose of studying
# while attending the course
#

"""
daemon.backend
~~~~~~~~~~~~~~~~~

This module provides a backend object to manage and persist backend daemon. 
It implements a basic backend server using Python's socket and threading libraries.
It supports handling multiple client connections concurrently and routing requests using a
custom HTTP adapter.

Requirements:
--------------
- socket: provide socket networking interface.
- threading: Enables concurrent client handling via threads.
- response: response utilities.
- httpadapter: the class for handling HTTP requests.
- CaseInsensitiveDict: provides dictionary for managing headers or routes.


Notes:
------
- The server create daemon threads for client handling.
- The current implementation error handling is minimal, socket errors are printed to the console.
- The actual request processing is delegated to the HttpAdapter class.

Usage Example:
--------------
>>> create_backend("127.0.0.1", 9000, routes={})

"""

import socket
import threading
import argparse

import asyncio
import inspect

from .response import *
from .httpadapter import HttpAdapter
from .dictionary import CaseInsensitiveDict

import selectors
sel = selectors.DefaultSelector()

# Select one of: "threading", "callback", "coroutine".
# - threading: one thread handles each accepted client socket.
# - callback: selector/event-loop style server socket readiness handling.
# - coroutine: asyncio StreamReader/StreamWriter handling.
mode_async = "threading"


def handle_client(ip, port, conn, addr, routes):
    """
    Initializes an HttpAdapter instance and delegates the client handling logic to it.

    :param ip (str): IP address of the server.
    :param port (int): Port number the server is listening on.
    :param conn (socket.socket): Client connection socket.
    :param addr (tuple): client address (IP, port).
    :param routes (dict): Dictionary of route handlers.
    """
    print("[Backend] Invoke handle_client accepted connection from {}".format(addr))
    daemon = HttpAdapter(ip, port, conn, addr, routes)

    try:
        daemon.handle_client(conn, addr, routes)
    except Exception as exc:
        print("[Backend] Error while handling client {}: {}".format(addr, exc))
        try:
            conn.close()
        except OSError:
            pass


# Callback for handling new client (itself run in sync mode)
def handle_client_callback(server, ip, port, routes):
    """
    Initialize connection instance and delegates the client handling logic to it.

    :param ip (str): IP address of the server.
    :param port (int): Port number the server is listening on.
    :param routes (dict): Dictionary of route handlers.
    """
    try:
        conn, addr = server.accept()
        conn.setblocking(True)  # HttpAdapter currently uses blocking recv/sendall.
    except BlockingIOError:
        return
    except OSError as exc:
        print("[Backend] Callback accept error: {}".format(exc))
        return

    print("[Backend] Invoke handle_client_callback accepted connection from {}".format(addr))
    # Handle client
    handle_client(ip, port, conn, addr, routes)


# Coroutine async/await for handling new client
async def handle_client_coroutine(reader, writer, routes=None):
    """
    Coroutine in async communication to initialize connection instance
    then delegates the client handling logic to it.

    :param reader (StreamReader): Stream reader wrapper.
    :param writer (StreamWriter): Stream writer wrapper.
    :param routes (dict): Dictionary of route handlers.
    """
    routes = routes or {}
    addr = writer.get_extra_info("peername")
    print("[Backend] Invoke handle_client_coroutine accepted connection from {}".format(addr))

    # Handle client in asynchronous mode
    daemon = HttpAdapter(None, None, None, addr, routes)
    try:
        await daemon.handle_client_coroutine(reader, writer)
    except Exception as exc:
        print("[Backend] Coroutine client error {}: {}".format(addr, exc))
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


async def async_server(ip="0.0.0.0", port=7000, routes=None):
    """Start the coroutine-based backend server."""
    routes = routes or {}
    print("[Backend] async_server **ASYNC** listening on port {}".format(port))
    if routes != {}:
        print("[Backend] route settings")
        for key, value in routes.items():
            isCoFunc = ""
            if inspect.iscoroutinefunction(value):
                isCoFunc += "**ASYNC** "
            print("   + ('{}', '{}'): {}{}".format(key[0], key[1], isCoFunc, str(value)))

    server = await asyncio.start_server(
        lambda reader, writer: handle_client_coroutine(reader, writer, routes),
        ip,
        port,
    )
    async with server:
        await server.serve_forever()


def _print_routes(routes):
    """Print route settings in the same format for all backend modes."""
    if routes != {}:
        print("[Backend] route settings")
        for key, value in routes.items():
            isCoFunc = ""
            if inspect.iscoroutinefunction(value):
                isCoFunc += "**ASYNC** "
            print("   + ('{}', '{}'): {}{}".format(key[0], key[1], isCoFunc, str(value)))


def run_backend(ip, port, routes):
    """
    Starts the backend server, binds to the specified IP and port, and listens for incoming
    connections. The selected non-blocking/concurrent strategy is controlled by mode_async.

    :param ip (str): IP address to bind the server.
    :param port (int): Port number to listen on.
    :param routes (dict): Dictionary of route handlers.
    """
    global mode_async

    routes = routes or {}
    print("[Backend] run_backend with routes={}".format(routes))

    # Coroutine implementation: asyncio event loop + async TCP server.
    if mode_async == "coroutine":

       asyncio.run(async_server(ip, port, routes))
       return

    # Process socket object
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server.bind((ip, port))
        server.listen(50)

        print("[Backend] Listening on port {}".format(port))
        _print_routes(routes)

        # Callback implementation: the listening socket is non-blocking and
        # selector.select() wakes up only when a new connection is ready.
        if mode_async == "callback":
            server.setblocking(False)
            sel.register(server, selectors.EVENT_READ, (handle_client_callback, ip, port, routes))

            while True:
                events = sel.select(timeout=None)
                for key, mask in events:
                    callback, cb_ip, cb_port, cb_routes = key.data
                    callback(key.fileobj, cb_ip, cb_port, cb_routes)

        # Multi-thread implementation: accept quickly in the main thread, then
        # process each client in its own daemon thread.
        elif mode_async == "threading":
            while True:
                conn, addr = server.accept()
                client_thread = threading.Thread(
                    target=handle_client,
                    args=(ip, port, conn, addr, routes),
                    daemon=True,
                )
                client_thread.start()

        # Safe fallback: handle clients sequentially, useful for debugging.
        else:
            print("[Backend] Unknown mode_async='{}'; using sequential mode".format(mode_async))
            while True:
                conn, addr = server.accept()
                handle_client(ip, port, conn, addr, routes)

    except KeyboardInterrupt:
        print("\n[Backend] Server stopped by user")
    except socket.error as e:
        print("Socket error: {}".format(e))
    finally:
        try:
            if mode_async == "callback":
                sel.unregister(server)
        except Exception:
            pass
        try:
            server.close()
        except OSError:
            pass


def create_backend(ip, port, routes={}):
    """
    Entry point for creating and running the backend server.

    :param ip (str): IP address to bind the server.
    :param port (int): Port number to listen on.
    :param routes (dict, optional): Dictionary of route handlers. Defaults to empty dict.
    """

    run_backend(ip, port, routes)