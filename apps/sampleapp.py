#
# Copyright (C) 2026 pdnguyen of HCMC University of Technology VNU-HCM.
# All rights reserved.
# This file is part of the CO3093/CO3094 course,
# and is released under the "MIT License Agreement". Please see the LICENSE
# file that should have been included as part of this package.
#
# AsynapRous release
#
# The authors hereby grant to Licensee personal permission to use
# and modify the Licensed Source Code for the sole purpose of studying
# while attending the course
#


"""
app.sampleapp
~~~~~~~~~~~~~~~~~

"""

import sys
import os
import importlib.util
import json
import uuid
from urllib.parse import parse_qs

from   daemon import AsynapRous

app = AsynapRous()

USERS = {"admin": "123456", "user1": "abc123"}
SESSIONS = {}

@app.route('/login', methods=['POST'])
def login(headers="guest", body="anonymous"):
    """
    Handle user login via POST request.

    This route simulates a login process and prints the provided headers and body
    to the console.

    :param headers (str): The request headers or user identifier.
    :param body (str): The request body or login payload.
    """
    print("[SampleApp] Logging in {} to {}".format(headers, body))

    if isinstance(body, bytes):
        body_text = body.decode("utf-8", errors="replace")
    else:
        body_text = str(body)

    body_text = body_text.strip()

    try:
        payload = json.loads(body_text) if body_text else {}
    except json.JSONDecodeError:
        payload = {key: values[0] for key, values in parse_qs(body_text).items()}

    username = payload.get("username", "")
    password = payload.get("password", "")

    if USERS.get(username) != password:
        data = {"success": False, "message": "Invalid username or password"}
        json_str = json.dumps(data)
        return json_str.encode("utf-8"), 401, {}

    session_id = uuid.uuid4().hex
    SESSIONS[session_id] = username

    data = {"success": True, "message": "Login successful", "username": username}
    json_str = json.dumps(data)

    return json_str.encode("utf-8"), 200, {
        "Set-Cookie": "session_id={}; Path=/; HttpOnly".format(session_id)
    }

@app.route('/check-auth', methods=['GET'])
def check_auth(headers="guest", body="anonymous"):
    cookie = headers.get("cookie", "") if hasattr(headers, "get") else ""
    session_id = ""

    for item in cookie.split(";"):
        if "=" in item:
            key, value = item.strip().split("=", 1)
            if key == "session_id":
                session_id = value

    username = SESSIONS.get(session_id)

    if not username:
        data = {"authenticated": False, "message": "Unauthorized"}
        json_str = json.dumps(data)
        return json_str.encode("utf-8"), 401, {}

    data = {"authenticated": True, "username": username}
    json_str = json.dumps(data)

    return json_str.encode("utf-8"), 200, {}

@app.route("/echo", methods=["POST"])
def echo(headers="guest", body="anonymous"):
    print("[SampleApp] received body {!r}".format(body))

    if isinstance(body, bytes):
        body_text = body.decode("utf-8", errors="replace")
    else:
        body_text = str(body)

    body_text = body_text.strip()

    try:
        message = json.loads(body_text)
    except json.JSONDecodeError:
        form_data = parse_qs(body_text)
        if form_data:
            message = {key: values[0] for key, values in form_data.items()}
        else:
            message = {"message": body_text}

    data = {"received": message}
    json_str = json.dumps(data)

    return json_str.encode("utf-8"), 200, {}

@app.route('/hello', methods=['PUT'])
async def hello(headers, body):
    """
    Handle greeting via PUT request.

    This route prints a greeting message to the console using the provided headers
    and body.

    :param headers (str): The request headers or user identifier.
    :param body (str): The request body or message payload.
    """
    print("[SampleApp] ['PUT'] **ASYNC** Hello in {} to {}".format(headers, body))
    data =  {"id": 1, "name": "Alice", "email": "alice@example.com"}

    # Convert to JSON string
    json_str = json.dumps(data)
    return (json_str.encode("utf-8"))

def create_sampleapp(ip, port):
    # Prepare and launch the RESTful application
    app.prepare_address(ip, port)
    app.run()
