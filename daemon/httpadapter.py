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
daemon.httpadapter
~~~~~~~~~~~~~~~~~

This module provides a http adapter object to manage and persist 
http settings (headers, bodies). The adapter supports both
raw URL paths and RESTful route definitions, and integrates with
Request and Response objects to handle client-server communication.
"""

from .request import Request
from .response import Response
from .dictionary import CaseInsensitiveDict

import asyncio
import inspect
import base64
import datetime
import json
from urllib.parse import urlparse

class HttpAdapter:
    """
    A mutable :class:`HTTP adapter <HTTP adapter>` for managing client connections
    and routing requests.

    The `HttpAdapter` class encapsulates the logic for receiving HTTP requests,
    dispatching them to appropriate route handlers, and constructing responses.
    It supports RESTful routing via hooks and integrates with :class:`Request <Request>` 
    and :class:`Response <Response>` objects for full request lifecycle management.

    Attributes:
        ip (str): IP address of the client.
        port (int): Port number of the client.
        conn (socket): Active socket connection.
        connaddr (tuple): Address of the connected client.
        routes (dict): Mapping of route paths to handler functions.
        request (Request): Request object for parsing incoming data.
        response (Response): Response object for building and sending replies.
    """

    __attrs__ = [
        "ip",
        "port",
        "conn",
        "connaddr",
        "routes",
        "request",
        "response",
    ]

    def __init__(self, ip, port, conn, connaddr, routes):
        """
        Initialize a new HttpAdapter instance.

        :param ip (str): IP address of the client.
        :param port (int): Port number of the client.
        :param conn (socket): Active socket connection.
        :param connaddr (tuple): Address of the connected client.
        :param routes (dict): Mapping of route paths to handler functions.
        """

        #: IP address.
        self.ip = ip
        #: Port.
        self.port = port
        #: Connection
        self.conn = conn
        #: Conndection address
        self.connaddr = connaddr
        #: Routes
        self.routes = routes or {}
        #: Request
        self.request = Request()
        #: Response
        self.response = Response()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _decode_request(self, raw_msg):
        """Convert bytes received from a socket into a safe UTF-8 string."""
        if raw_msg is None:
            return ""
        if isinstance(raw_msg, bytes):
            return raw_msg.decode("utf-8", errors="replace")
        return str(raw_msg)

    def _read_http_message(self, conn, chunk_size=4096):
        """Read one HTTP message from a normal socket.

        The original code used only one recv(1024).  That can cut off POST/PUT
        bodies.  This helper reads the first chunk, checks Content-Length, and
        continues reading until the declared body length is available.
        """
        raw = conn.recv(chunk_size)
        if not raw:
            return ""

        header_end = raw.find(b"\r\n\r\n")
        if header_end == -1:
            return self._decode_request(raw)

        header_bytes = raw[:header_end].decode("iso-8859-1", errors="replace")
        content_length = 0
        for line in header_bytes.split("\r\n")[1:]:
            if line.lower().startswith("content-length:"):
                try:
                    content_length = int(line.split(":", 1)[1].strip())
                except ValueError:
                    content_length = 0
                break

        body_start = header_end + 4
        current_body_len = len(raw) - body_start
        while current_body_len < content_length:
            chunk = conn.recv(chunk_size)
            if not chunk:
                break
            raw += chunk
            current_body_len += len(chunk)

        return self._decode_request(raw)

    async def _read_http_message_async(self, reader, chunk_size=4096):
        """Read one HTTP message from an asyncio StreamReader."""
        raw = await reader.read(chunk_size)
        if not raw:
            return ""

        header_end = raw.find(b"\r\n\r\n")
        if header_end == -1:
            return self._decode_request(raw)

        header_bytes = raw[:header_end].decode("iso-8859-1", errors="replace")
        content_length = 0
        for line in header_bytes.split("\r\n")[1:]:
            if line.lower().startswith("content-length:"):
                try:
                    content_length = int(line.split(":", 1)[1].strip())
                except ValueError:
                    content_length = 0
                break

        body_start = header_end + 4
        current_body_len = len(raw) - body_start
        while current_body_len < content_length:
            chunk = await reader.read(chunk_size)
            if not chunk:
                break
            raw += chunk
            current_body_len += len(chunk)

        return self._decode_request(raw)

    def _to_body_bytes(self, content):
        """Convert a hook return value into bytes and choose a content type."""
        if content is None:
            return b"", "text/plain; charset=utf-8"

        if isinstance(content, bytes):
            return content, "application/json; charset=utf-8"

        if isinstance(content, (dict, list, tuple)):
            return json.dumps(content).encode("utf-8"), "application/json; charset=utf-8"

        if isinstance(content, str):
            text = content
            content_type = "text/html; charset=utf-8" if text.lstrip().startswith("<") else "text/plain; charset=utf-8"
            return text.encode("utf-8"), content_type

        return str(content).encode("utf-8"), "text/plain; charset=utf-8"

    def _make_http_response(self, content=b"", status_code=200, reason="OK", headers=None):
        """Build a complete HTTP/1.1 response as bytes."""
        body, inferred_content_type = self._to_body_bytes(content)

        response_headers = {
            "Date": datetime.datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT"),
            "Server": "AsynapRous/1.0",
            "Content-Type": inferred_content_type,
            "Content-Length": str(len(body)),
            "Connection": "close",
        }

        if headers:
            response_headers.update(headers)
            response_headers["Content-Length"] = str(len(body))

        status_line = "HTTP/1.1 {} {}\r\n".format(status_code, reason)
        header_lines = "".join("{}: {}\r\n".format(k, v) for k, v in response_headers.items())
        return (status_line + header_lines + "\r\n").encode("utf-8") + body

    def _build_error_response(self, status_code, reason, message=None):
        """Build a small plain-text error response."""
        body = message or "{} {}".format(status_code, reason)
        return self._make_http_response(body, status_code=status_code, reason=reason)

    def _invoke_hook(self, req):
        """Call a synchronous route hook with request headers and body."""
        try:
            return req.hook(headers=req.headers, body=req.body)
        except TypeError:
            # Some student handlers may use positional parameters.
            return req.hook(req.headers, req.body)

    async def _invoke_hook_async(self, req):
        """Call a route hook and await it when it returns a coroutine."""
        try:
            result = req.hook(headers=req.headers, body=req.body)
        except TypeError:
            result = req.hook(req.headers, req.body)

        if inspect.isawaitable(result):
            result = await result
        return result

    # ------------------------------------------------------------------
    # Client handlers
    # ------------------------------------------------------------------
    def handle_client(self, conn, addr, routes):
        """
        Handle an incoming client connection.

        This method reads the request from the socket, prepares the request object,
        invokes the appropriate route handler if available, builds the response,
        and sends it back to the client.

        :param conn (socket): The client socket connection.
        :param addr (tuple): The client's address.
        :param routes (dict): The route mapping for dispatching requests.
        """

        # Connection handler.
        self.conn = conn        
        # Connection address.
        self.connaddr = addr
        # Request handler
        req = self.request
        # Response handler
        resp = self.response
        self.routes = routes or self.routes or {}

        # Handle the request
        try:
            msg = self._read_http_message(conn)
            req.prepare(msg, self.routes)
            print("[HttpAdapter] Invoke handle_client connection {}".format(addr))

            # Handle request hook
            if req.hook:
                #
                # TODO: handle for App hook here
                #
                hook_result = self._invoke_hook(req)
                if inspect.isawaitable(hook_result):
                    hook_result = asyncio.run(hook_result)
                response = self._make_http_response(hook_result)
            else:
                response = resp.build_response(req)

            if isinstance(response, str):
                response = response.encode("utf-8")
            conn.sendall(response)
        except Exception as e:
            print("[HttpAdapter] handle_client exception: {}".format(e))
            conn.sendall(self._build_error_response(500, "Internal Server Error", str(e)))
        finally:
            conn.close()

    async def handle_client_coroutine(self, reader, writer):
        """
        Handle an incoming client connection using stream reader writer asynchronously.

        This method reads the request from the socket, prepares the request object,
        invokes the appropriate route handler if available, builds the response,
        and sends it back to the client.

        :param conn (socket): The client socket connection.
        :param addr (tuple): The client's address.
        :param routes (dict): The route mapping for dispatching requests.
        """
        addr = writer.get_extra_info("peername")
        # Request handler
        req = self.request
        # Response handler
        resp = self.response

        try:
            print("[HttpAdapter] Invoke handle_client_coroutine connection {}".format(addr))
            msg = await self._read_http_message_async(reader)
            req.prepare(msg, self.routes or {})

            if req.hook:
                # TODO: handle for App hook here
                hook_result = await self._invoke_hook_async(req)
                response = self._make_http_response(hook_result)
            else:
                response = resp.build_response(req)

            if isinstance(response, str):
                response = response.encode("utf-8")
            writer.write(response)
            await writer.drain()
        except Exception as e:
            print("[HttpAdapter] handle_client_coroutine exception: {}".format(e))
            writer.write(self._build_error_response(500, "Internal Server Error", str(e)))
            await writer.drain()
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Response/cookie/header helpers
    # ------------------------------------------------------------------
    def extract_cookies(self, req, resp=None):
        """
        Build cookies from the :class:`Request <Request>` headers.

        :param req:(Request) The :class:`Request <Request>` object.
        :param resp: (Response) The res:class:`Response <Response>` object.
        :rtype: cookies - A dictionary of cookie key-value pairs.
        """
        cookies = CaseInsensitiveDict()
        headers = getattr(req, "headers", {}) or {}
        cookie_header = headers.get("Cookie", headers.get("cookie", ""))

        for pair in str(cookie_header).split(";"):
            pair = pair.strip()
            if not pair or "=" not in pair:
                continue
            key, value = pair.split("=", 1)
            cookies[key.strip()] = value.strip()
        return cookies

    def build_response(self, req, resp):
        """Builds a :class:`Response <Response>` object 

        :param req: The :class:`Request <Request>` used to generate the response.
        :param resp: The  response object.
        :rtype: Response
        """
        response = Response(req)
        response.raw = resp
        # Give the Response some context.
        response.request = req
        response.connection = self
        response.url = req.url.decode("utf-8") if isinstance(req.url, bytes) else req.url
        response.cookies = self.extract_cookies(req, resp)

        if getattr(resp, "reason", None):
            response.reason = resp.reason
        if getattr(resp, "headers", None):
            response.headers = resp.headers
            content_type = response.headers.get("Content-Type", "")
            if "charset=" in content_type:
                response.encoding = content_type.split("charset=", 1)[1].split(";", 1)[0].strip()

        return response

    def build_json_response(self, req, resp):
        """Builds a :class:`Response <Response>` object from JSON data

        :param req: The :class:`Request <Request>` used to generate the response.
        :param resp: The  response object.
        :rtype: Response
        """
        response = self.build_response(req, resp)
        response.headers["Content-Type"] = "application/json; charset=utf-8"
        response.encoding = "utf-8"
        return response

    def add_headers(self, request):
        """
        Add headers to the request.

        This method is intended to be overridden by subclasses to inject
        custom headers. It does nothing by default.

        
        :param request: :class:`Request <Request>` to add headers to.
        """
        if not hasattr(request, "headers") or request.headers is None:
            request.headers = CaseInsensitiveDict()

        request.headers.setdefault("User-Agent", "AsynapRous/1.0")
        request.headers.setdefault("Accept", "*/*")
        request.headers.setdefault("Connection", "close")
        return request

    def build_proxy_headers(self, proxy):
        """Returns a dictionary of the headers to add to any request sent
        through a proxy. 

        :class:`HttpAdapter <HttpAdapter>`.

        :param proxy: The url of the proxy being used for this request.
        :rtype: dict
        """
        headers = {}
        #
        # TODO: build your authentication here
        #       username, password =...
        # we provide dummy auth here
        #
        parsed = urlparse(proxy or "")

        username = parsed.username
        password = parsed.password or ""
        if username:
            token = "{}:{}".format(username, password).encode("utf-8")
            encoded = base64.b64encode(token).decode("ascii")
            headers["Proxy-Authorization"] = "Basic {}".format(encoded)

        return headers