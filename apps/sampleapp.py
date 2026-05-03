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
~~~~~~~~~~~~~

A small RESTful hybrid chat application for the AsynapRous framework.

Supported APIs:
    POST /login
    POST /submit-info
    GET  /get-list
    POST /add-list
    POST /connect-peer
    POST /broadcast-peer
    POST /send-peer
    GET  /channels
    GET  /messages
    POST /echo
    PUT  /hello
"""

import json
import socket
import time
from typing import Any, Dict, List, Optional, Tuple

from daemon import AsynapRous

app = AsynapRous()

# ---------------------------------------------------------------------------
# In-memory application state
# ---------------------------------------------------------------------------

USERS: Dict[str, Dict[str, Any]] = {}
PEERS: Dict[str, Dict[str, Any]] = {}
CHANNELS: Dict[str, Dict[str, Any]] = {
    "general": {
        "name": "general",
        "members": set(),
        "messages": [],
        "access": "public",
    }
}

DEFAULT_CHANNEL = "general"


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def json_response(payload: Dict[str, Any], status: str = "ok") -> bytes:
    """Serialize a response object to UTF-8 JSON bytes."""
    payload.setdefault("status", status)
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def parse_json_body(body: Any) -> Dict[str, Any]:
    """Parse the HTTP body safely and always return a dictionary."""
    if body is None:
        return {}
    if isinstance(body, bytes):
        body = body.decode("utf-8", errors="replace")
    if not str(body).strip():
        return {}
    try:
        data = json.loads(body)
        if isinstance(data, dict):
            return data
        return {"value": data}
    except json.JSONDecodeError:
        return {"text": str(body)}


def normalize_peer(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Validate and normalize peer information from a request body."""
    peer_id = str(data.get("peer_id") or data.get("username") or "").strip()
    host = str(data.get("ip") or data.get("host") or "").strip()
    port = data.get("port")

    if not peer_id or not host or port is None:
        return None

    try:
        port = int(port)
    except (TypeError, ValueError):
        return None

    return {
        "peer_id": peer_id,
        "ip": host,
        "port": port,
        "last_seen": int(time.time()),
    }


def get_channel(name: str = DEFAULT_CHANNEL) -> Dict[str, Any]:
    """Return a channel, creating it when it does not exist."""
    name = name or DEFAULT_CHANNEL
    if name not in CHANNELS:
        CHANNELS[name] = {
            "name": name,
            "members": set(),
            "messages": [],
            "access": "public",
        }
    return CHANNELS[name]


def serialize_channel(channel: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a channel object into JSON-safe data."""
    return {
        "name": channel["name"],
        "members": sorted(channel["members"]),
        "message_count": len(channel["messages"]),
        "access": channel.get("access", "public"),
    }


def save_message(
    channel_name: str,
    sender: str,
    message: str,
    receiver: Optional[str] = None,
) -> Dict[str, Any]:
    """Append an immutable message to a channel."""
    channel = get_channel(channel_name)
    item = {
        "id": len(channel["messages"]) + 1,
        "sender": sender or "anonymous",
        "receiver": receiver,
        "message": message,
        "timestamp": int(time.time()),
    }
    channel["messages"].append(item)
    channel["members"].add(sender or "anonymous")
    if receiver:
        channel["members"].add(receiver)
    return item


def send_peer_message(peer: Dict[str, Any], message: Dict[str, Any]) -> Tuple[bool, str]:
    """Send one JSON message to a peer using a short non-blocking TCP attempt."""
    payload = json.dumps(message, ensure_ascii=False).encode("utf-8")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1.0)

    try:
        sock.connect((peer["ip"], int(peer["port"])))
        sock.setblocking(False)
        total_sent = 0
        while total_sent < len(payload):
            try:
                sent = sock.send(payload[total_sent:])
                if sent == 0:
                    return False, "socket connection broken"
                total_sent += sent
            except BlockingIOError:
                time.sleep(0.01)
        return True, "sent"
    except OSError as exc:
        return False, str(exc)
    finally:
        sock.close()


# ---------------------------------------------------------------------------
# RESTful route handlers
# ---------------------------------------------------------------------------

@app.route("/login", methods=["POST"])
def login(headers="guest", body="anonymous"):
    """Authenticate/register a user for the sample chat application."""
    data = parse_json_body(body)
    username = str(data.get("username") or data.get("peer_id") or "guest").strip()
    password = str(data.get("password") or "").strip()

    if not username:
        return json_response({"message": "username is required"}, status="error")

    USERS[username] = {
        "username": username,
        "password": password,
        "last_login": int(time.time()),
    }
    get_channel(DEFAULT_CHANNEL)["members"].add(username)

    return json_response({
        "message": "login successfully",
        "username": username,
        "channels": [DEFAULT_CHANNEL],
    })


@app.route("/submit-info", methods=["POST"])
def submit_info(headers="guest", body="anonymous"):
    """Register or update the current peer in the centralized tracker."""
    data = parse_json_body(body)
    peer = normalize_peer(data)

    if peer is None:
        return json_response({
            "message": "peer_id/username, ip/host, and port are required"
        }, status="error")

    PEERS[peer["peer_id"]] = peer
    get_channel(data.get("channel", DEFAULT_CHANNEL))["members"].add(peer["peer_id"])

    return json_response({
        "message": "peer registered",
        "peer": peer,
        "total_peers": len(PEERS),
    })


@app.route("/get-list", methods=["GET", "POST"])
def get_list(headers="guest", body="anonymous"):
    """Return the active peer list for peer discovery."""
    return json_response({
        "message": "active peer list",
        "peers": list(PEERS.values()),
        "total_peers": len(PEERS),
    })


@app.route("/add-list", methods=["POST"])
def add_list(headers="guest", body="anonymous"):
    """Add one peer or many peers to the centralized tracker."""
    data = parse_json_body(body)
    raw_peers = data.get("peers")
    if raw_peers is None:
        raw_peers = [data]
    if not isinstance(raw_peers, list):
        return json_response({"message": "peers must be a list"}, status="error")

    added: List[Dict[str, Any]] = []
    rejected: List[Any] = []
    for item in raw_peers:
        if not isinstance(item, dict):
            rejected.append(item)
            continue
        peer = normalize_peer(item)
        if peer is None:
            rejected.append(item)
            continue
        PEERS[peer["peer_id"]] = peer
        added.append(peer)

    return json_response({
        "message": "peer list updated",
        "added": added,
        "rejected": rejected,
        "total_peers": len(PEERS),
    })


@app.route("/connect-peer", methods=["POST"])
def connect_peer(headers="guest", body="anonymous"):
    """Return target peer information so the caller can create a direct P2P connection."""
    data = parse_json_body(body)
    peer_id = str(data.get("peer_id") or "").strip()

    if not peer_id:
        return json_response({"message": "peer_id is required"}, status="error")

    peer = PEERS.get(peer_id)
    if peer is None:
        return json_response({"message": "peer not found"}, status="error")

    return json_response({
        "message": "peer found",
        "peer": peer,
    })


@app.route("/send-peer", methods=["POST"])
def send_peer(headers="guest", body="anonymous"):
    """Send a direct message to one peer and save it in the channel history."""
    data = parse_json_body(body)
    target_id = str(data.get("target") or data.get("peer_id") or "").strip()
    sender = str(data.get("sender") or "anonymous").strip()
    text = str(data.get("message") or data.get("text") or "").strip()
    channel_name = str(data.get("channel") or DEFAULT_CHANNEL).strip()

    if not target_id or not text:
        return json_response({"message": "target/peer_id and message are required"}, status="error")

    peer = PEERS.get(target_id)
    if peer is None:
        return json_response({"message": "target peer not found"}, status="error")

    saved = save_message(channel_name, sender, text, receiver=target_id)
    ok, detail = send_peer_message(peer, {
        "type": "direct-message",
        "channel": channel_name,
        "data": saved,
    })

    return json_response({
        "message": "direct message processed",
        "delivered": ok,
        "detail": detail,
        "saved_message": saved,
    }, status="ok" if ok else "error")


@app.route("/broadcast-peer", methods=["POST"])
def broadcast_peer(headers="guest", body="anonymous"):
    """Broadcast a message to every known peer except the sender."""
    data = parse_json_body(body)
    sender = str(data.get("sender") or "anonymous").strip()
    text = str(data.get("message") or data.get("text") or "").strip()
    channel_name = str(data.get("channel") or DEFAULT_CHANNEL).strip()

    if not text:
        return json_response({"message": "message is required"}, status="error")

    saved = save_message(channel_name, sender, text)
    results = []
    for peer_id, peer in PEERS.items():
        if peer_id == sender:
            continue
        ok, detail = send_peer_message(peer, {
            "type": "broadcast-message",
            "channel": channel_name,
            "data": saved,
        })
        results.append({"peer_id": peer_id, "delivered": ok, "detail": detail})

    return json_response({
        "message": "broadcast processed",
        "saved_message": saved,
        "results": results,
    })


@app.route("/channels", methods=["GET", "POST"])
def channels(headers="guest", body="anonymous"):
    """List joined/available channels, and optionally create a channel by POST body."""
    data = parse_json_body(body)
    channel_name = str(data.get("channel") or "").strip()
    username = str(data.get("username") or data.get("peer_id") or "").strip()

    if channel_name:
        channel = get_channel(channel_name)
        if username:
            channel["members"].add(username)

    return json_response({
        "message": "channel list",
        "channels": [serialize_channel(channel) for channel in CHANNELS.values()],
    })


@app.route("/messages", methods=["GET", "POST"])
def messages(headers="guest", body="anonymous"):
    """Return messages in a channel. POST can also append a new message."""
    data = parse_json_body(body)
    channel_name = str(data.get("channel") or DEFAULT_CHANNEL).strip()
    sender = str(data.get("sender") or "anonymous").strip()
    text = str(data.get("message") or data.get("text") or "").strip()

    if text:
        save_message(channel_name, sender, text)

    channel = get_channel(channel_name)
    return json_response({
        "message": "message list",
        "channel": channel_name,
        "messages": channel["messages"],
    })


@app.route("/echo", methods=["POST"])
def echo(headers="guest", body="anonymous"):
    """Simple test endpoint that returns the request body."""
    return json_response({"received": parse_json_body(body)})


@app.route("/hello", methods=["PUT"])
async def hello(headers="guest", body="anonymous"):
    """Simple asynchronous test endpoint."""
    data = parse_json_body(body)
    return json_response({
        "message": "Hello from AsynapRous",
        "received": data,
    })


def create_sampleapp(ip, port):
    # Prepare and launch the RESTful application
    app.prepare_address(ip, port)
    app.run()

