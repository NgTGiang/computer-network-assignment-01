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
daemon.proxy
~~~~~~~~~~~~~~~~~

This module implements a simple proxy server using Python's socket and threading libraries.
It routes incoming HTTP requests to backend services based on hostname mappings and returns
the corresponding responses to clients.

Requirement:
-----------------
- socket: provides socket networking interface.
- threading: enables concurrent client handling via threads.
- response: customized :class: `Response <Response>` utilities.
- httpadapter: :class: `HttpAdapter <HttpAdapter >` adapter for HTTP request processing.
- dictionary: :class: `CaseInsensitiveDict <CaseInsensitiveDict>` for managing headers and cookies.

"""
import socket
import threading
from itertools import count

from .response import *
from .httpadapter import HttpAdapter
from .dictionary import CaseInsensitiveDict

#: A dictionary mapping hostnames to backend IP and port tuples.
#: Used to determine routing targets for incoming requests.
PROXY_PASS = {
    "192.168.56.103:8080": ("192.168.56.103", 9000),
    "app1.local": ("192.168.56.103", 9001),
    "app2.local": ("192.168.56.103", 9002),
}

# Keeps the next backend index for each hostname when round-robin is used.
_ROUND_ROBIN_STATE = {}
_ROUND_ROBIN_LOCK = threading.Lock()


def build_not_found(message="404 Not Found"):
    """Build a small HTTP 404 response."""
    body = message.encode("utf-8")
    return (
        "HTTP/1.1 404 Not Found\r\n"
        "Content-Type: text/plain\r\n"
        "Content-Length: {}\r\n"
        "Connection: close\r\n"
        "\r\n"
    ).format(len(body)).encode("utf-8") + body


def forward_request(host, port, request):
    """
    Forwards an HTTP request to a backend server and retrieves the response.

    :params host (str): IP address of the backend server.
    :params port (int): port number of the backend server.
    :params request (str): incoming HTTP request.

    :rtype bytes: Raw HTTP response from the backend server. If the connection
                  fails, returns a 404 Not Found response.
    """

    backend = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    backend.settimeout(10)

    try:
        backend.connect((host, port))
        backend.sendall(request.encode("utf-8", errors="replace"))
        response = b""
        while True:
            chunk = backend.recv(4096)
            if not chunk:
                break
            response += chunk
        return response
    except socket.error as e:
        print("[Proxy] Socket error while forwarding to {}:{} - {}".format(host, port, e))
        return build_not_found()
    finally:
        backend.close()


def _split_host_port(proxy_pass):
    """
    Convert a proxy_pass target like '127.0.0.1:9000' into ('127.0.0.1', '9000').
    """
    if isinstance(proxy_pass, tuple) and len(proxy_pass) == 2:
        return proxy_pass[0], str(proxy_pass[1])

    if not isinstance(proxy_pass, str) or ":" not in proxy_pass:
        raise ValueError("Invalid proxy_pass value: {}".format(proxy_pass))

    proxy_host, proxy_port = proxy_pass.rsplit(":", 1)
    return proxy_host, proxy_port


def _choose_backend(hostname, proxy_map, policy):
    """
    Select one backend from a list according to a distribution policy.
    """
    if not proxy_map:
        raise LookupError("No backend configured for host {}".format(hostname))

    # Current assignment config supports round-robin. Unknown policies safely
    # fall back to round-robin so the proxy still works.
    if policy in (None, "", "round-robin", "round_robin"):
        with _ROUND_ROBIN_LOCK:
            current_index = _ROUND_ROBIN_STATE.get(hostname, 0)
            selected = proxy_map[current_index % len(proxy_map)]
            _ROUND_ROBIN_STATE[hostname] = current_index + 1
        return selected

    print("[Proxy] Unsupported dist_policy '{}'; fallback to round-robin".format(policy))
    with _ROUND_ROBIN_LOCK:
        current_index = _ROUND_ROBIN_STATE.get(hostname, 0)
        selected = proxy_map[current_index % len(proxy_map)]
        _ROUND_ROBIN_STATE[hostname] = current_index + 1
    return selected


def resolve_routing_policy(hostname, routes):
    """
    Resolve hostname and distribution policy to a backend host and port.

    :params hostname (str): Host header value from the client request.
    :params routes (dict): Mapping created by start_proxy.parse_virtual_hosts.
    :rtype tuple: (proxy_host, proxy_port). Both are empty strings when not found.
    """
    if not hostname:
        print("[Proxy] Missing Host header")
        return "", ""

    proxy_map = None
    policy = "round-robin"

    if routes and hostname in routes:
        proxy_map, policy = routes[hostname]
    elif hostname in PROXY_PASS:
        proxy_map = PROXY_PASS[hostname]
    else:
        print("[Proxy] No route configured for hostname {}".format(hostname))
        return "", ""

    try:
        if isinstance(proxy_map, list):
            selected_backend = _choose_backend(hostname, proxy_map, policy)
            proxy_host, proxy_port = _split_host_port(selected_backend)
        else:
            proxy_host, proxy_port = _split_host_port(proxy_map)
    except (LookupError, ValueError) as e:
        print("[Proxy] Failed to resolve route for {}: {}".format(hostname, e))
        return "", ""

    print(
        "[Proxy] Resolved Host {} -> {}:{} using policy {}".format(
            hostname, proxy_host, proxy_port, policy
        )
    )
    return proxy_host, proxy_port


def handle_client(ip, port, conn, addr, routes):
    """
    Handles an individual client connection by parsing the request,
    determining the target backend, and forwarding the request.

    The handler extracts the Host header from the request to
    matches the hostname against known routes. In the matching
    condition,it forwards the request to the appropriate backend.

    The handler sends the backend response back to the client or
    returns 404 if the hostname is unreachable or is not recognized.

    :params ip (str): IP address of the proxy server.
    :params port (int): port number of the proxy server.
    :params conn (socket.socket): client connection socket.
    :params addr (tuple): client address (IP, port).
    :params routes (dict): dictionary mapping hostnames and location.
    """

    try:
        request = conn.recv(4096).decode("utf-8", errors="replace")
        if not request:
            conn.sendall(build_not_found("Empty request"))
            return

        hostname = ""
        for line in request.splitlines():
            if line.lower().startswith("host:"):
                hostname = line.split(":", 1)[1].strip()
                break

        print("[Proxy] {} at Host: {}".format(addr, hostname))

        # Resolve the matching destination in routes and need conver port
        # to integer value
        resolved_host, resolved_port = resolve_routing_policy(hostname, routes)
        try:
            resolved_port = int(resolved_port)
        except (TypeError, ValueError):
            print("[Proxy] Invalid port for Host {}: {}".format(hostname, resolved_port))
            resolved_host = ""

        if resolved_host:
            print(
                "[Proxy] Host name {} is forwarded to {}:{}".format(
                    hostname, resolved_host, resolved_port
                )
            )
            response = forward_request(resolved_host, resolved_port, request)
        else:
            response = build_not_found()

        conn.sendall(response)
    except socket.error as e:
        print("[Proxy] Client socket error from {}: {}".format(addr, e))
    finally:
        conn.close()


def run_proxy(ip, port, routes):
    """
    Starts the proxy server and listens for incoming connections. 

    The process dinds the proxy server to the specified IP and port.
    In each incomping connection, it accepts the connections and
    spawns a new thread for each client using `handle_client`.
 

    :params ip (str): IP address to bind the proxy server.
    :params port (int): port number to listen on.
    :params routes (dict): dictionary mapping hostnames and location.

    """

    proxy = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    proxy.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        proxy.bind((ip, port))
        proxy.listen(50)
        print("[Proxy] Listening on IP {} port {}".format(ip, port))
        while True:
            conn, addr = proxy.accept()
            #
            #  TODO: implement the step of the client incomping connection
            #        using multi-thread programming with the
            #        provided handle_client routine
            #
            client_thread = threading.Thread(
                target=handle_client,
                args=(ip, port, conn, addr, routes),
                daemon=True,
            )
            client_thread.start()
    except socket.error as e:
        print("Socket error: {}".format(e))
    finally:
        proxy.close()


def create_proxy(ip, port, routes):
    """
    Entry point for launching the proxy server.

    :params ip (str): IP address to bind the proxy server.
    :params port (int): Port number to listen on.
    :params routes (dict): Dictionary mapping hostnames and location.
    """

    run_proxy(ip, port, routes)
