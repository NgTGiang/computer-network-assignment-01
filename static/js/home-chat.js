let currentUser = localStorage.getItem("currentUser");
let selectedUser = null;
let selectedPeer = null;
let lastSeenTimestamp = 0;
let unreadCounts = {};

if (!currentUser) {
  window.location.href = "/login.html";
}

document.getElementById("sendBtn").addEventListener("click", sendMessage);
document.getElementById("refreshBtn").addEventListener("click", loadUsers);
document.getElementById("broadcastBtn").addEventListener("click", broadcastMessage);
document.getElementById("logoutBtn").addEventListener("click", logout);
document.getElementById("messageInput").addEventListener("keydown", function (event) {
  if (event.key === "Enter") sendMessage();
});

document.getElementById("currentUserText").textContent = "Current user: " + currentUser;

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.message || "Request failed");
  }
  return data;
}

async function loadUsers() {
  try {
    const users = await requestJson("/users");
    const userList = document.getElementById("userList");
    userList.innerHTML = "";

    users.forEach(user => {
      if (user.username === currentUser) return;

      const div = document.createElement("div");
      div.className = "chat-item";
      const unread = unreadCounts[user.username] || 0;

      div.innerHTML = `
        <img src="/static/images/${user.username}.jpg" onerror="this.style.display='none'">

        <div class="peer-info">
          <h4>${user.username}</h4>
          <p>${user.ip}:${user.port}</p>
        </div>

        <span class="unread-badge ${unread === 0 ? "hidden" : ""}">
          ${unread}
        </span>
      `;

      div.onclick = () => selectUser(user, div);
      userList.appendChild(div);
    });

    if (!userList.innerHTML) {
      userList.innerHTML = `<p class="empty-list">No online peers</p>`;
    }
  } catch (err) {
    document.getElementById("userList").innerHTML = `<p class="empty-list">${err.message}</p>`;
  }
}

async function loadChannels() {
  try {
    const result = await requestJson("/channels");
    const channelList = document.getElementById("channelList");
    channelList.innerHTML = "";

    result.channels.forEach(channel => {
      const div = document.createElement("div");
      div.className = "channel-item";
      div.textContent = "# " + channel.name;
      channelList.appendChild(div);
    });
  } catch (err) {
    document.getElementById("channelList").innerHTML = `<p class="empty-list">No channels</p>`;
  }
}

async function selectUser(user, element) {
  selectedUser = user.username;
  selectedPeer = user;

  unreadCounts[selectedUser] = 0;
  loadUsers();

  document.querySelectorAll(".chat-item").forEach(item => item.classList.remove("active"));
  element.classList.add("active");

  document.getElementById("chatTitle").textContent = "Chat with " + user.username;
  document.getElementById("profileName").textContent = user.username;
  document.getElementById("profileStatus").textContent = "● " + user.status;
  document.getElementById("peerAddress").textContent = `Peer address: ${user.ip}:${user.port}`;

  await requestJson("/connect-peer", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ to: selectedUser })
  });

  loadMessages();
}

async function loadMessages() {
  if (!selectedUser) return;

  try {
    const messages = await requestJson(`/messages?to=${encodeURIComponent(selectedUser)}`);
    const chatBody = document.getElementById("chatBody");
    chatBody.innerHTML = "";

    messages.forEach(msg => {
      const div = document.createElement("div");
      div.className = msg.from === currentUser ? "message right" : "message left";
      div.innerHTML = `<p>${escapeHtml(msg.text)}</p><span>${new Date(msg.timestamp).toLocaleTimeString()}</span>`;
      chatBody.appendChild(div);
      lastSeenTimestamp = Math.max(lastSeenTimestamp, msg.timestamp);
    });

    if (!messages.length) {
      chatBody.innerHTML = `<div class="empty-state">No messages yet.</div>`;
    }

    chatBody.scrollTop = chatBody.scrollHeight;
  } catch (err) {
    document.getElementById("chatBody").innerHTML = `<div class="empty-state">${err.message}</div>`;
  }
}

async function sendMessage() {
  const input = document.getElementById("messageInput");
  const text = input.value.trim();

  if (!text || !selectedUser) return;

  try {
    await requestJson("/send-peer", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ to: selectedUser, text, channel: "general" })
    });

    input.value = "";
    loadMessages();
  } catch (err) {
    alert("Send failed: " + err.message);
  }
}

async function broadcastMessage() {
  const input = document.getElementById("messageInput");
  const text = input.value.trim();

  if (!text) {
    alert("Type a message before broadcasting.");
    return;
  }

  try {
    await requestJson("/broadcast-peer", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, channel: "general" })
    });
    input.value = "";
    alert("Broadcast sent.");
  } catch (err) {
    alert("Broadcast failed: " + err.message);
  }
}

async function checkNotifications() {
  try {
    const result = await requestJson(`/notifications?since=${lastSeenTimestamp}`);
    const text = result.count > 0 ? `${result.count} new message(s)` : "No new messages";
    document.getElementById("notificationText").textContent = text;
  } catch (err) {
    document.getElementById("notificationText").textContent = "Notification unavailable";
  }
}

async function logout() {
  try {
    await fetch("/logout", { method: "POST" });
  } finally {
    localStorage.removeItem("currentUser");
    window.location.href = "/login.html";
  }
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function initApp() {
  try {
    const auth = await requestJson("/check-auth");
    currentUser = auth.username;
    localStorage.setItem("currentUser", currentUser);
    document.getElementById("currentUserText").textContent = "Current user: " + currentUser;

    const host = window.location.hostname || "127.0.0.1";
    const port = window.location.port ? parseInt(window.location.port, 10) : 2026;
    await requestJson("/submit-info", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ip: host, port: port })
    });

    await loadUsers();
    await loadChannels();
  } catch (err) {
    localStorage.removeItem("currentUser");
    window.location.href = "/login.html";
  }
}

initApp();
setInterval(loadUsers, 5000);
setInterval(loadMessages, 1000);
setInterval(checkNotifications, 2000);
