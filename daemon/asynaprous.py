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
deamon.asynaprous
~~~~~~~~~~~~~~~~~

This module provides a AsynapRous object to deploy RESTful url web app with routing
"""

from .backend import create_backend
import functools
import inspect


class AsynapRous:
    """The fully mutable :class:`AsynapRous <AsynapRous>` object, which is a lightweight,
    mutable web application router for deploying RESTful URL endpoints.

    The `AsynapRous` class provides a decorator-based routing system for building simple
    RESTful web applications.  The class allows developers to register route handlers 
    using decorators and launch a TCP-based backend server to serve RESTful requests. 
    Each route is mapped to a handler function based on HTTP method and path. It mappings
    supports tracking the combined HTTP methods and path route mappings internally.

    Usage::
      >>> import daemon.asynaprous
      >>> app = AsynapRous()
      >>> @app.route('/login', methods=['POST'])
      >>> def login(headers="guest", body="anonymous"):
      >>>     return {'message': 'Logged in'}

      >>> @app.route('/hello', methods=['GET'])
      >>> def hello(headers, body):
      >>>     return {'message': 'Hello, world!'}

      >>> app.run()
    """

    def __init__(self):
        """
        Initialize a new AsynapRous instance.

        Sets up an empty route registry and prepares placeholders for IP and port.
        """
        self.routes = {}
        self.ip = None
        self.port = None
        return

    def prepare_address(self, ip, port):
        """
        Configure the IP address and port for the backend server.

        :param ip (str): The IP address to bind the server.
        :param port (str): The port number to listen on.
        """
        if not ip:
            raise ValueError("ip must not be empty")

        try:
            port = int(port)
        except (TypeError, ValueError):
            raise ValueError("port must be an integer")

        if port < 1 or port > 65535:
            raise ValueError("port must be in range 1..65535")

        self.ip = ip
        self.port = port

    def route(self, path, methods=None):
        """
        Decorator to register a route handler for a specific path and HTTP methods.

        :param path (str): The URL path to route.
        :param methods (list): A list of HTTP methods (e.g., ['GET', 'POST']) to bind.

        :rtype: function - A decorator that registers the handler function.
        """
        if methods is None:
            methods = ['GET']
        elif isinstance(methods, str):
            methods = [methods]

        if not isinstance(path, str) or not path:
            raise ValueError("route path must be a non-empty string")

        if not path.startswith('/'):
            path = '/' + path

        normalized_methods = []
        for method in methods:
            if not isinstance(method, str) or not method.strip():
                raise ValueError("HTTP method must be a non-empty string")
            normalized_methods.append(method.strip().upper())

        def decorator(func):
            if not callable(func):
                raise TypeError("route handler must be callable")

            if inspect.iscoroutinefunction(func):
                @functools.wraps(func)
                async def async_wrapper(*args, **kwargs):
                    print("[AsynapRous] running async function... [{}] {}".format(
                        normalized_methods, path
                    ))
                    return await func(*args, **kwargs)

                handler = async_wrapper
            else:
                @functools.wraps(func)
                def sync_wrapper(*args, **kwargs):
                    print("[AsynapRous] running sync function... [{}] {}".format(
                        normalized_methods, path
                    ))
                    return func(*args, **kwargs)

                handler = sync_wrapper

            # Attach route metadata to both the original function and the registered handler.
            func._route_path = path
            func._route_methods = list(normalized_methods)
            handler._route_path = path
            handler._route_methods = list(normalized_methods)
            handler._original_handler = func

            for method in normalized_methods:
                route_key = (method, path)
                if route_key in self.routes:
                    print("[AsynapRous] warning: overwrite route {} {}".format(method, path))
                self.routes[route_key] = handler

            return handler

        return decorator

    def run(self):
        """
        Start the backend server and begin handling requests.

        This method launches the TCP server using the configured IP and port,
        and dispatches incoming requests to the registered route handlers.

        :raise: Error if IP or port has not been configured.
        """
        if self.ip is None or self.port is None:
            raise RuntimeError(
                "AsynapRous app needs an address. Call app.prepare_address(ip, port) first."
            )

        print("[AsynapRous] starting app on {}:{}".format(self.ip, self.port))
        if self.routes:
            print("[AsynapRous] registered routes:")
            for (method, path), handler in self.routes.items():
                async_mark = " **ASYNC**" if inspect.iscoroutinefunction(handler) else ""
                print("   + [{}] {} -> {}{}".format(method, path, handler.__name__, async_mark))

        create_backend(self.ip, self.port, self.routes)
        
