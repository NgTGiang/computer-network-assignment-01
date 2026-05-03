# Computer Network Assignment - AsynapRous Framework

## 📋 Project Overview

This is a **RESTful TCP WebApp Framework** called **AsynapRous** - a lightweight Python-based server architecture for building custom HTTP services with support for:
- Routing and request handling
- Multiple concurrency modes (threading, callback, async/await)
- Proxy server capabilities
- Custom HTTP adapter

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   AsynapRous Framework                  │
├─────────────────────────────────────────────────────────┤
│                                                         │
│          ┌──────────────┐      ┌──────────────┐         │
│          │  Frontend    │      │   Proxy      │         │
│          │  (Client)    │◄────►│   Server     │         │
│          └──────────────┘      └──────────────┘         │
│                 ▲                     ▲                 │
│                 │                     │                 │
│                 └─────────────────────┘                 │
│                         │                               │
│                  ┌──────▼──────┐                        │
│                  │   Backend   │                        │
│                  │   Server    │                        │
│                  └──────┬──────┘                        │
│                         │                               │
│                 ┌───────▼────────┐                      │
│                 │  HttpAdapter   │                      │
│                 │  - Routing     │                      │
│                 │  - Requests    │                      │
│                 │  - Responses   │                      │
│                 └────────────────┘                      │
│                         │                               │
│                 ┌───────▼─────────┐                     │
│                 │  Route Handlers │                     │
│                 │  (User App)     │                     │
│                 └─────────────────┘                     │
└─────────────────────────────────────────────────────────┘
```

---

## 📁 Project Structure

```
computer-network-assignment-01/
├── daemon/                          # Core server framework
│   ├── __init__.py                  # Package initialization
│   ├── backend.py                   # Main server (socket/threading/async)
│   ├── httpadapter.py               # HTTP request/response handler
│   ├── request.py                   # Request parser
│   ├── response.py                  # Response builder
│   ├── asynaprous.py                # Decorator-based routing framework
│   ├── dictionary.py                # Case-insensitive dict for headers
│   ├── proxy.py                     # Proxy server
│   └── utils.py                     # Utility functions
│
├── apps/                            # User applications
│   ├── __init__.py
│   └── sampleapp.py                 # Example RESTful app
│
├── static/                          # Static assets
│   ├── css/styles.css
│   └── images/
│
├── www/                             # HTML pages
│   ├── index.html
│   ├── login.html
│   └── form.html
│
├── config/                          # Configuration files
│   └── proxy.conf                   # Proxy routing config
│
├── start_backend.py                 # Entry point: Backend server
├── start_proxy.py                   # Entry point: Proxy server
├── start_sampleapp.py               # Entry point: Sample app
├── .venv/                           # Python virtual environment
└── README.md                        # This file
```

---

## 🚀 Quick Start Guide

### Prerequisites
```bash
# Ensure Python 3.10+ is installed
python --version

# Create virtual environment
python -m venv .venv

# Activate it
# On Windows:
.venv\Scripts\activate
# On Linux/Mac:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 1️⃣ Run the Backend Server

```bash
# Start backend on default port 9000
python start_backend.py

# Or specify custom IP/port
python start_backend.py --server-ip 127.0.0.1 --server-port 9000
```

**Output:**
```
[Backend] run_backend with routes={}
[Backend] Listening on port 9000
```

---

### 2️⃣ Run the Sample Application

The sample app defines three RESTful endpoints:

```bash
python start_sampleapp.py --server-ip 0.0.0.0 --server-port 2026
```

**Registered Routes:**
- `POST /login` - User login handler
- `POST /echo` - Echo incoming JSON message
- `PUT /hello` - Async greeting endpoint

---

### 3️⃣ Run the Proxy Server

```bash
python start_proxy.py --server-ip 0.0.0.0 --server-port 8080
```

Routes requests based on `config/proxy.conf`:
- `192.168.56.114:8080` → `192.168.56.114:9000`
- `app1.local` → `192.168.56.114:9001`
- `app2.local` → `192.168.56.114:9002`

---

## 💻 Core Components

### 1. **AsynapRous - Routing Framework**
```python
from daemon import AsynapRous

app = AsynapRous()

@app.route('/login', methods=['POST'])
def login(headers="guest", body="anonymous"):
    return {"message": "Welcome"}

app.prepare_address("127.0.0.1", 2026)
app.run()
```

### 2. **Backend Server Modes**

Set `mode_async` in `daemon/backend.py`:

```python
# Threading mode (recommended)
mode_async = "threading"

# Callback/Event-driven mode
mode_async = "callback"

# Async/await coroutine mode
mode_async = "coroutine"
```

### 3. **Request/Response Cycle**

```
Client Socket Connection
        │
        ▼
┌─────────────────────┐
│  HttpAdapter        │
│  handle_client()    │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Request.prepare()  │  (Parse HTTP headers/body)
│  Extract route      │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Route Handler      │  (User-defined function)
│  (get hook from     │
│   route mapping)    │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│ Response.build()    │  (Build HTTP response)
│ Send back to client │
└─────────────────────┘
```

---

## 📝 Creating a Custom App

```python
# custom_app.py
from daemon import AsynapRous
import json

app = AsynapRous()

@app.route('/api/users', methods=['GET'])
def get_users(headers="", body=""):
    users = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
    return json.dumps(users).encode('utf-8')

@app.route('/api/users', methods=['POST'])
def create_user(headers="", body=""):
    data = json.loads(body)
    return json.dumps({"created": data}).encode('utf-8')

@app.route('/api/status', methods=['GET'])
async def status(headers="", body=""):
    # Async handler
    return json.dumps({"status": "running"}).encode('utf-8')

if __name__ == "__main__":
    app.prepare_address("0.0.0.0", 5000)
    app.run()
```

---

## 🔌 Testing the API

### Using cURL

```bash
# Test login endpoint
curl -X POST http://127.0.0.1:2026/login \
  -H "Content-Type: application/json" \
  -d '{"user":"admin","pass":"secret"}'

# Test echo endpoint
curl -X POST http://127.0.0.1:2026/echo \
  -H "Content-Type: application/json" \
  -d '{"message":"Hello Server"}'

# Test hello endpoint
curl -X PUT http://127.0.0.1:2026/hello \
  -H "Content-Type: application/json" \
  -d '{"greeting":"Hi"}'
```

### Using HTML Form (form.html)
1. Start the sample app
2. Open `www/form.html` in browser
3. Submit messages through the interface

---

## ⚙️ Configuration

### Backend Modes (daemon/backend.py)

```python
mode_async = "threading"     # Best for multiple clients
mode_async = "callback"      # Event-driven, non-blocking
mode_async = "coroutine"     # Full async/await support
```

### Proxy Routes (config/proxy.conf)

```nginx
host "app1.local" {
    proxy_pass http://192.168.56.114:9001;
}

host "app2.local" {
    proxy_pass http://192.168.56.114:9002;
    dist_policy round-robin
}
```

---

## 🐛 Known Issues & TODOs

| Component | Issue | Status |
|-----------|-------|--------|
| `backend.py` | Threading implementation incomplete | ⚠️ TODO |
| `request.py` | Cookie parsing incomplete | ⚠️ TODO |
| `response.py` | Full response building needs completion | ⚠️ TODO |
| `httpadapter.py` | Hook execution logic incomplete | ⚠️ TODO |
| `proxy.py` | Multi-pass policy handling | ⚠️ TODO |

---

## 📊 Data Flow Example

**POST /echo request:**

```
Client: POST /echo HTTP/1.1
        Content-Type: application/json
        {"message":"test"}
        │
        ▼
[Backend] Accepts connection
        │
        ▼
[Request] Parses: method=POST, path=/echo, body={"message":"test"}
        │
        ▼
[Router] Finds hook: echo() function
        │
        ▼
[Handler] echo(body='{"message":"test"}')
        │
        ▼
[Response] Returns: {"received":{"message":"test"}}
        │
        ▼
Client: HTTP/1.1 200 OK
        Content-Type: application/json
        Content-Length: XX
        
        {"received":{"message":"test"}}
```

---

## 🎯 Next Steps

1. **Complete threading implementation** in `backend.py`
2. **Implement cookie handling** in `request.py`
3. **Finish response building** in `response.py`
4. **Add authentication middleware**
5. **Deploy with WSGI/production server**

---

## 📄 License & Attribution

**Framework Version:** AsynapRous Release  
**Python Version:** 3.10+  
**License:** MIT (CO3093/CO3094 Course)  
**Copyright © 2026** pdnguyen of HCMC University of Technology VNU-HCM

All rights reserved. This file is part of the CO3093/CO3094 course, and is released under the "MIT License Agreement".
