document.getElementById("loginForm").addEventListener("submit", function (event) {
  event.preventDefault();
  login();
});

async function login() {
  const username = document.getElementById("username").value.trim();
  const password = document.getElementById("password").value.trim();
  const error = document.getElementById("error");

  error.textContent = "";

  try {
    const response = await fetch("/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password })
    });

    const result = await response.json();

    if (response.ok && result.success) {
      localStorage.setItem("currentUser", result.username);
      window.location.href = "/home-chat.html";
    } else {
      error.textContent = result.message || "Sai username hoặc password";
    }
  } catch (err) {
    error.textContent = "Không kết nối được server";
  }
}
