# 📌 File Relationship Diagram - Non-blocking HTTP Server Assignment

## 🧠 System Overview

This system follows a **Client → Proxy → Backend/WebApp** architecture:

- Proxy acts as a gateway
- Backend handles HTTP processing
- WebApp (AsynapRous) handles RESTful logic
- Static files serve UI content

---

## 🏗️ Architecture Diagram

```text
Client / Browser
      |
      v
start_proxy.py
      |
      | reads config
      v
proxy.conf
      |
      v
daemon/proxy.py
      |
      | forwards HTTP request
      v
Backend / WebApp process
      |
      +--------------------------+
      |                          |
      v                          v
start_backend.py           start_sampleapp.py
      |                          |
      v                          v
daemon/backend.py          apps/sampleapp.py
      |                          |
      |                          v
      |                    daemon/asynaprous.py
      |                          |
      +-------------> daemon/backend.py
                         |
                         v
                  daemon/httpadapter.py
                         |
              +----------+----------+
              v                     v
       daemon/request.py      daemon/response.py
              |                     |
              v                     v
     parse HTTP request      build HTTP response
                                    |
                    +---------------+---------------+
                    v                               v
              www/*.html                     static/css/*.css
        index.html, login.html, form.html    styles.css
```

