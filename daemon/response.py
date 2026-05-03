#
# Copyright (C) 2026 pdnguyen of HCMC University of Technology VNU-HCM.
# All rights reserved.
# This file is part of the CO3093/CO3094 course.
#
# AsynApRous release
#
# The authors hereby grant to Licensee personal permission to use
# and modify the Licensed Source Code for the sole purpose of studying
# while attending the course
#

"""
daemon.response
~~~~~~~~~~~~~~~~~

This module provides a :class: `Response <Response>` object to manage and persist 
response settings (cookies, auth, proxies), and to construct HTTP responses
based on incoming requests. 

The current version supports MIME type detection, content loading and header formatting
"""
import datetime
import os
import mimetypes
import inspect
import asyncio
from http import HTTPStatus

from .dictionary import CaseInsensitiveDict

BASE_DIR = ""

class Response():   
    """The :class:`Response <Response>` object, which contains a
    server's response to an HTTP request.

    Instances are generated from a :class:`Request <Request>` object, and
    should not be instantiated manually; doing so may produce undesirable
    effects.

    :class:`Response <Response>` object encapsulates headers, content, 
    status code, cookies, and metadata related to the request-response cycle.
    It is used to construct and serve HTTP responses in a custom web server.

    :attrs status_code (int): HTTP status code (e.g., 200, 404).
    :attrs headers (dict): dictionary of response headers.
    :attrs url (str): url of the response.
    :attrsencoding (str): encoding used for decoding response content.
    :attrs history (list): list of previous Response objects (for redirects).
    :attrs reason (str): textual reason for the status code (e.g., "OK", "Not Found").
    :attrs cookies (CaseInsensitiveDict): response cookies.
    :attrs elapsed (datetime.timedelta): time taken to complete the request.
    :attrs request (PreparedRequest): the original request object.

    Usage::

      >>> import Response
      >>> resp = Response()
      >>> resp.build_response(req)
      >>> resp
      <Response>
    """

    __attrs__ = [
        "_content",
        "_header",
        "status_code",
        "method",
        "headers",
        "url",
        "history",
        "encoding",
        "reason",
        "cookies",
        "elapsed",
        "request",
        "body",
        "reason",
    ]


    def __init__(self, request=None):
        """
        Initializes a new :class:`Response <Response>` object.

        : params request : The originating request object.
        """

        self._content = b""
        self._content_consumed = False
        self._next = None
        self._header = b""

        #: Integer Code of responded HTTP Status, e.g. 404 or 200.
        self.status_code = None

        #: Case-insensitive Dictionary of Response Headers.
        #: For example, ``headers['content-type']`` will return the
        #: value of a ``'Content-Type'`` response header.
        self.headers = CaseInsensitiveDict()

        #: URL location of Response.
        self.url = None

        #: Encoding to decode with when accessing response text.
        self.encoding = None

        #: A list of :class:`Response <Response>` objects from
        #: the history of the Request.
        self.history = []

        #: Textual reason of responded HTTP Status, e.g. "Not Found" or "OK".
        self.reason = None

        #: A of Cookies the response headers.
        self.cookies = CaseInsensitiveDict()

        #: The amount of time elapsed between sending the request
        self.elapsed = datetime.timedelta(0)

        #: The :class:`PreparedRequest <PreparedRequest>` object to which this
        #: is a response.
        self.request = request
        self.body = b""

    def get_mime_type(self, path):
        """
        Determines the MIME type of a file based on its path.

        "params path (str): Path to the file.

        :rtype str: MIME type string (e.g., 'text/html', 'image/png').
        """

        try:
            mime_type, _ = mimetypes.guess_type(path or "")
        except Exception:
            return 'application/octet-stream'
        return mime_type or 'application/octet-stream'

    def prepare_content_type(self, mime_type='text/html'):
        """
        Prepares the Content-Type header and determines the base directory
        for serving the file based on its MIME type.

        :params mime_type (str): MIME type of the requested resource.

        :rtype str: Base directory path for locating the resource.

        :raises ValueError: If the MIME type is unsupported.
        """
        
        base_dir = ""

        # Validate header attr existence
        if not hasattr(self, "headers") or self.headers is None:
            self.headers = CaseInsensitiveDict()

        if '/' not in mime_type:
            mime_type = 'application/octet-stream'

        # Processing mime_type based on main_type and sub_type
        main_type, sub_type = mime_type.split('/', 1)
        print("[Response] Processing main_type={} sub_type={}".format(main_type, sub_type))

        self.headers['Content-Type'] = mime_type

        if main_type == 'text':
            # Static text resources: html pages live in www, CSS/JS/text-like files live in static.
            if sub_type == 'html':
                base_dir = BASE_DIR + "www/"
            elif sub_type in ('plain', 'css', 'csv', 'xml', 'javascript'):
                base_dir = BASE_DIR + "static/"
            else:
                base_dir = BASE_DIR + "static/"
        elif main_type == 'image':
            base_dir = BASE_DIR+"static/"
        elif main_type == 'application':
        #
        #  TODO: process other mime_type
        #        application/xml       
        #        application/zip
        #        ...
        #        text/csv
        #        text/xml
        #        ...
        #        video/mp4 
        #        video/mpeg
        #        ...
        #
        # REST handlers normally return JSON.  Static app assets can also be served here.
            if sub_type == 'json':
                base_dir = BASE_DIR + "apps/"
            elif sub_type in ('javascript', 'xml', 'zip', 'pdf', 'octet-stream'):
                base_dir = BASE_DIR + "static/"
            else:
                base_dir = BASE_DIR + "apps/"

        elif main_type == 'video':
            base_dir = BASE_DIR + "static/"

        elif main_type == 'audio':
            base_dir = BASE_DIR + "static/"

        else:
            raise ValueError("Invalid MIME type: main_type={} sub_type={}".format(main_type,sub_type))

        return base_dir


    def build_content(self, path, base_dir):
        """
        Loads the objects file from storage space.

        :params path (str): relative path to the file.
        :params base_dir (str): base directory where the file is located.

        :rtype tuple: (int, bytes) representing content length and content data.
        """

        """Loads the requested object file from storage."""
        safe_path = os.path.normpath(path.lstrip('/'))

        # Prevent directory traversal such as /../../secret.txt.
        if safe_path.startswith('..') or os.path.isabs(safe_path):
            print("[Response] Unsafe path rejected: {}".format(path))
            return -1, b""

        filepath = os.path.join(base_dir, safe_path)
        print("[Response] Serving the object at location {}".format(filepath))
            #
            #  TODO: implement the step of fetch the object file
            #        store in the return value of content
            #
        if not os.path.isfile(filepath):
            print("[Response] File not found: {}".format(filepath))
            return -1, b""

        try:
            with open(filepath, "rb") as f:
                content = f.read()
        except OSError as e:
            print("[Response] build_content exception: {}".format(e))
            return -1, b""

        return len(content), content

    def _status_line(self):
        """Build the HTTP status line, e.g. HTTP/1.1 200 OK."""
        status_code = self.status_code or 200
        reason = self.reason
        if reason is None:
            try:
                reason = HTTPStatus(status_code).phrase
            except ValueError:
                reason = "OK"
        return "HTTP/1.1 {} {}".format(status_code, reason)

    def _set_cookie_headers(self, headers):
        """Copy response cookies into Set-Cookie headers."""
        if not self.cookies:
            return

        cookie_lines = []
        for key, value in self.cookies.items():
            cookie_lines.append("{}={}; Path=/; HttpOnly".format(key, value))

        # Multiple Set-Cookie headers are allowed, so store as a list marker here.
        headers['Set-Cookie'] = cookie_lines

    def build_response_header(self, request):
        """
        Constructs the HTTP response headers based on the class:`Request <Request>
        and internal attributes.

        :params request (class:`Request <Request>`): incoming request object.

        :rtypes bytes: encoded HTTP response header.
        """
        
        """Constructs encoded HTTP response headers."""
        reqhdr = request.headers or CaseInsensitiveDict()

        if not hasattr(self, "headers") or self.headers is None:
            self.headers = CaseInsensitiveDict()

        # Basic status/body headers.
        headers = CaseInsensitiveDict()
        headers['Date'] = datetime.datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")
        headers['Server'] = 'AsynapRous/1.0'
        headers['Content-Type'] = self.headers.get('Content-Type', 'text/html')
        headers['Content-Length'] = str(len(self._content or b""))
        headers['Connection'] = 'close'
        headers['Cache-Control'] = 'no-cache'
        headers['Pragma'] = 'no-cache'

        # Keep useful client context when it is present, but do not create fake auth headers.
        if reqhdr.get('Authorization'):
            self.auth = reqhdr.get('Authorization')
        elif hasattr(request, 'auth'):
            self.auth = request.auth
        else:
            self.auth = None

        if reqhdr.get('Accept-Language'):
            headers['Content-Language'] = reqhdr.get('Accept-Language').split(',')[0]

        # Allow caller-added headers to override defaults except Content-Length.
        for key, value in self.headers.items():
            if key.lower() == 'content-length':
                continue
            headers[key] = value

        self._set_cookie_headers(headers)

        lines = [self._status_line()]
        for key, value in headers.items():
            if isinstance(value, (list, tuple)):
                for item in value:
                    lines.append("{}: {}".format(key, item))
            else:
                lines.append("{}: {}".format(key, value))

        fmt_header = "\r\n".join(lines) + "\r\n\r\n"
        return fmt_header.encode('utf-8')

    def build_notfound(self):
        """
        Constructs a standard 404 Not Found HTTP response.

        :rtype bytes: Encoded 404 response.
        """

        return (
                "HTTP/1.1 404 Not Found\r\n"
                "Accept-Ranges: bytes\r\n"
                "Content-Type: text/html\r\n"
                "Content-Length: 13\r\n"
                "Cache-Control: max-age=86000\r\n"
                "Connection: close\r\n"
                "\r\n"
                "404 Not Found"
            ).encode('utf-8')

    def _normalize_content(self, content):
        """Convert handler/file content into bytes."""
        if content is None:
            return b""
        if isinstance(content, bytes):
            return content
        if isinstance(content, bytearray):
            return bytes(content)
        return str(content).encode('utf-8')

    def _run_hook(self, request):
        """Execute a matched AsynapRous route handler and return bytes."""
        result = request.hook(headers=request.headers, body=request.body)
        if inspect.isawaitable(result):
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # In a running loop, the coroutine should be awaited by the async adapter.
                    raise RuntimeError("Coroutine hook cannot be synchronously awaited while loop is running")
                result = loop.run_until_complete(result)
            except RuntimeError:
                result = asyncio.run(result)
        return self._normalize_content(result)

    def build_response(self, request, envelop_content=None):
        """
        Builds a full HTTP response including headers and content based on the request.

        :params request (class:`Request <Request>`): incoming request object.

        :rtype bytes: complete HTTP response using prepared headers and content.
        """
        print("[Response] Start build response with req {}".format(request))

        self.request = request
        path = request.path or '/index.html'
        route_path = path.split('?', 1)[0]

        # RESTful route response: if Request.prepare() found a route hook, call it.
        if getattr(request, 'hook', None):
            try:
                self.status_code = 200
                self.reason = 'OK'
                self.headers['Content-Type'] = 'application/json'
                self._content = self._run_hook(request)
                self._header = self.build_response_header(request)
                return self._header + self._content
            except Exception as e:
                print("[Response] route hook exception: {}".format(e))
                self.status_code = 500
                self.reason = 'Internal Server Error'
                self.headers['Content-Type'] = 'text/plain'
                self._content = b"500 Internal Server Error"
                self._header = self.build_response_header(request)
                return self._header + self._content

        mime_type = self.get_mime_type(route_path)
        print("[Response] {} path {} mime_type {}".format(request.method, request.path, mime_type))

        try:
            base_dir = self.prepare_content_type(mime_type)
        except ValueError:
            return self.build_notfound()

        # TODO: add support objects
        # If caller provides dynamic content, use it instead of reading a file.
        if envelop_content is not None:
            self.status_code = 200
            self.reason = 'OK'
            self._content = self._normalize_content(envelop_content)
            self._header = self.build_response_header(request)
            return self._header + self._content

        content_length, content = self.build_content(route_path, base_dir)
        if content_length < 0:
            return self.build_notfound()

        self.status_code = 200
        self.reason = 'OK'
        self._content = content
        self._header = self.build_response_header(request)

        return self._header + self._content
