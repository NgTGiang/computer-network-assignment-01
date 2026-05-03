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
daemon.request
~~~~~~~~~~~~~~~~~

This module provides a Request object to manage and persist 
request settings (cookies, auth, proxies).
"""

import base64
import json as json_module
from urllib.parse import urlparse

from .dictionary import CaseInsensitiveDict


class Request():
    """The fully mutable "class" `Request <Request>` object,
    containing the exact bytes that will be sent to the server.

    Instances are generated from a "class" `Request <Request>` object, and
    should not be instantiated manually; doing so may produce undesirable
    effects.

    Usage::

      >>> import deamon.request
      >>> req = request.Request()
      ## Incoming message obtain aka. incoming_msg
      >>> r = req.prepare(incoming_msg)
      >>> r
      <Request>
    """
    __attrs__ = [
        "method",
        "url",
        "headers",
        "body",
        "_raw_headers",
        "_raw_body",
        "reason",
        "cookies",
        "body",
        "routes",
        "hook",
    ]

    def __init__(self):
        #: HTTP verb to send to the server.
        self.method = None
        #: HTTP URL to send the request to.
        self.url = None
        #: dictionary of HTTP headers.
        self.headers = CaseInsensitiveDict()
        #: HTTP path
        self.path = None
        #: The cookies set used to create Cookie header
        self.cookies = CaseInsensitiveDict()
        #: request body to send to the server.
        self.body = ""
        #: The raw header
        self._raw_headers = ""
        #: The raw body
        self._raw_body = ""
        #: Routes
        self.routes = {}
        #: Hook point for routed mapped-path
        self.hook = None
        #: HTTP version.
        self.version = None
        #: Authentication information prepared from headers/url/user input.
        self.auth = None

    def extract_request_line(self, request):
        """Extract HTTP method, path and version from the first request line."""
        try:
            lines = request.splitlines()
            if not lines:
                return None, None, None

            first_line = lines[0].strip()
            method, path, version = first_line.split()

            if path == '/':
                path = '/index.html'
        except Exception:
            return None, None, None

        return method.upper(), path, version
             
    def prepare_headers(self, request):
        """Prepares the given HTTP headers."""
        raw_headers, _ = self.fetch_headers_body(request)
        lines = raw_headers.split('\r\n')
        headers = CaseInsensitiveDict()

        # Skip request line. Header fields are formatted as: Name: value
        for line in lines[1:]:
            if not line or ':' not in line:
                continue
            key, val = line.split(':', 1)
            headers[key.strip()] = val.strip()

        return headers

    def fetch_headers_body(self, request):
        """Prepares the given HTTP headers."""
        # Split request into header section and body section
        parts = request.split("\r\n\r\n", 1)  # split once at blank line

        _headers = parts[0]
        _body = parts[1] if len(parts) > 1 else ""
        return _headers, _body

    def prepare(self, request, routes=None):
        """Prepares the entire request with the given parameters."""
        if request is None:
            request = ""
        if isinstance(request, bytes):
            request = request.decode("utf-8", errors="replace")

        # Prepare the request line from the request header
        print("[Request] prepare request msg {}".format(request))

        self._raw_headers, self._raw_body = self.fetch_headers_body(request)
        self.headers = self.prepare_headers(request)
        self.body = self._raw_body

        self.method, self.path, self.version = self.extract_request_line(request)
        print("[Request] {} path {} version {}".format(self.method, self.path, self.version))

        #
        # @bksysnet Preapring the webapp hook with AsynapRous instance
        # The default behaviour with HTTP server is empty routed
        #
        # TODO manage the webapp hook in this mounting point
        #

        # Keep both url and path.  For routing, remove query string only.
        self.url = self.path
        route_path = self.path.split('?', 1)[0] if self.path else None

        # Manage the webapp hook mounting point for AsynapRous routes.
        self.routes = routes or {}
        self.hook = None
        if self.routes:
            print("[Request] Routing METHOD {} path {}".format(
                self.method, route_path
            ))
            self.hook = self.routes.get((self.method, route_path))
            print("[Request] Hook is {}".format(self.hook))

#
        #  TODO: implement the cookie function here
        #        by parsing the header            #

        # Parse Cookie header into self.cookies.
        self.cookies = self.prepare_cookies(self.headers.get('Cookie', ''))

        # Parse Authorization header, if the client sent one.
        auth_header = self.headers.get('Authorization')
        if auth_header:
            self.auth = self.prepare_auth(auth_header)

        return self

    def prepare_body(self, data=None, files=None, json=None):
        """Prepare request body and synchronize the Content-Length header."""
        if json is not None:
            body = json_module.dumps(json)
            self.headers['Content-Type'] = 'application/json'
        elif data is None:
            body = ""
        elif isinstance(data, bytes):
            body = data
        elif isinstance(data, str):
            body = data
        else:
            body = str(data)

        # This small framework does not implement multipart upload yet, but keep
        # a marker so callers can detect that files were supplied.
        if files:
            self.files = files

        self.body = body
        self.prepare_content_length(body)
        return body

    def prepare_content_length(self, body):
        """Set Content-Length based on the byte length of the body."""
        if self.headers is None:
            self.headers = CaseInsensitiveDict()

        if body is None:
            length = 0
        elif isinstance(body, bytes):
            length = len(body)
        else:
            length = len(str(body).encode('utf-8'))

        self.headers['Content-Length'] = str(length)
        return length

    def prepare_auth(self, auth, url=""):
        """Prepare HTTP Basic authentication.

        Supported input forms:
        - tuple/list: (username, password)
        - string beginning with "Basic ": existing Authorization header
        - string beginning with "Bearer ": existing bearer token
        - URL containing user:password credentials
        """
        if self.headers is None:
            self.headers = CaseInsensitiveDict()

        if not auth and url:
            parsed = urlparse(url)
            if parsed.username is not None:
                auth = (parsed.username, parsed.password or "")

        if isinstance(auth, (tuple, list)) and len(auth) == 2:
            username, password = auth
            token = '{}:{}'.format(username, password).encode('utf-8')
            encoded = base64.b64encode(token).decode('ascii')
            value = 'Basic {}'.format(encoded)
            self.headers['Authorization'] = value
            self.auth = ('basic', username, password)
            return value

        if isinstance(auth, str):
            value = auth.strip()
            lower_value = value.lower()

            if lower_value.startswith('basic '):
                self.headers['Authorization'] = value
                try:
                    decoded = base64.b64decode(value.split(None, 1)[1]).decode('utf-8')
                    username, password = decoded.split(':', 1)
                    self.auth = ('basic', username, password)
                except Exception:
                    self.auth = ('basic', None, None)
                return value

            if lower_value.startswith('bearer '):
                self.headers['Authorization'] = value
                self.auth = ('bearer', value.split(None, 1)[1])
                return value

            # Treat a plain string as a precomputed Authorization value.
            self.headers['Authorization'] = value
            self.auth = value
            return value

        self.auth = None
        return None

    def prepare_cookies(self, cookies):
        """Parse or serialize HTTP cookies.

        When `cookies` is a Cookie header string, return a CaseInsensitiveDict.
        When `cookies` is a dict-like object, also update the Cookie request
        header with the serialized cookie pairs.
        """
        parsed_cookies = CaseInsensitiveDict()

        if self.headers is None:
            self.headers = CaseInsensitiveDict()

        if not cookies:
            return parsed_cookies

        if isinstance(cookies, str):
            for pair in cookies.split(';'):
                pair = pair.strip()
                if not pair or '=' not in pair:
                    continue
                key, value = pair.split('=', 1)
                parsed_cookies[key.strip()] = value.strip()
        else:
            for key, value in dict(cookies).items():
                parsed_cookies[str(key)] = str(value)
            self.headers['Cookie'] = '; '.join(
                '{}={}'.format(key, value)
                for key, value in parsed_cookies.items()
            )

        return parsed_cookies
