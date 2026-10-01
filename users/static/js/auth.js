(function () {
  "use strict";
  const form = document.querySelector("[data-auth-form]");
  const message = document.querySelector("[data-auth-message]");
  const submit = form?.querySelector("button[type='submit']");
  const setMessage = (text, type) => { if (!message) return; message.textContent = text || ""; message.className = `auth-message${type ? ` is-${type}` : ""}`; };
  const setBusy = (busy, label) => { if (!submit) return; submit.disabled = busy; submit.textContent = busy ? "Please wait..." : label; };
  const jsonRequest = async (url, options) => { const response = await fetch(url, options); let data = {}; try { data = await response.json(); } catch (_) {} if (!response.ok) throw new Error(data.detail || data.message || data.error || "Request failed."); return data; };
  const fieldError = (name, text) => { const field = document.getElementById(name); const error = document.getElementById(`${name}_error`) || document.getElementById(`${name}-error`); field?.classList.toggle("error", Boolean(text)); if (error) error.textContent = text || ""; };

  if (!form) return;
  const kind = form.dataset.authForm;
  if (kind === "login") {
    form.addEventListener("submit", async (event) => {
      event.preventDefault(); setMessage(""); fieldError("username", ""); fieldError("password", "");
      const username = form.username.value.trim(); const password = form.password.value;
      if (username.length < 4) fieldError("username", "Enter at least 4 characters.");
      if (password.length < 8) fieldError("password", "Enter at least 8 characters.");
      if (username.length < 4 || password.length < 8) { setMessage("Please correct the highlighted fields.", "error"); return; }
      setBusy(true, "Log in");
      try {
        const data = await jsonRequest("/api/login/", { method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" }, body: JSON.stringify({ username, password }) });
        localStorage.setItem("access_token", data.token.access); localStorage.setItem("refresh_token", data.token.refresh); localStorage.setItem("user", JSON.stringify(data.user));
        setMessage("Login successful. Opening your workspace...", "success"); window.setTimeout(() => { window.location.href = data.dashboard_url || "/"; }, 450);
      } catch (error) { setMessage(error.message || "Unable to log in. Check your details and try again.", "error"); setBusy(false, "Log in"); }
    });
  }

  if (kind === "register") {
    form.addEventListener("submit", async (event) => {
      event.preventDefault(); setMessage("");
      const data = Object.fromEntries(new FormData(form).entries());
      const password = form.password.value; const confirmation = form.confirm_password.value;
      if (password !== confirmation) { fieldError("confirm_password", "Passwords do not match."); setMessage("Please correct the highlighted fields.", "error"); return; }
      if (!form.checkbox.checked) { fieldError("checkbox", "Accept the terms to continue."); setMessage("Please accept the terms and conditions.", "error"); return; }
      setBusy(true, "Create account");
      try { await jsonRequest("/api/register/", { method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" }, body: JSON.stringify(data) }); setMessage("Account created. Redirecting to login...", "success"); window.setTimeout(() => { window.location.href = "/login-template/"; }, 900); }
      catch (error) { setMessage(error.message || "Registration failed. Please review your details.", "error"); setBusy(false, "Create account"); }
    });
  }

  if (kind === "reset") {
    const modal = document.getElementById("otpModal"); const passwordModal = document.getElementById("newPasswordModal");
    const open = (element) => element?.classList.add("is-open"); const close = (element) => element?.classList.remove("is-open");
    document.getElementById("sendResetLinkBtn")?.addEventListener("click", async () => {
      const email = document.getElementById("email").value.trim(); setMessage("");
      if (!email) { setMessage("Enter the email address associated with your account.", "error"); return; }
      try { await jsonRequest("/password-reset/", { method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" }, body: JSON.stringify({ email }) }); localStorage.setItem("reset_email", email); setMessage("Verification code sent. Check your email.", "success"); open(modal); }
      catch (error) { setMessage(error.message || "We could not send a verification code.", "error"); }
    });
    document.getElementById("otpVerificationForm")?.addEventListener("submit", async (event) => { event.preventDefault(); const error = document.getElementById("otp-error-message"); error.textContent = ""; try { await jsonRequest("/api/verify-otp/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email: localStorage.getItem("reset_email"), otp: document.getElementById("otp").value.trim() }) }); localStorage.setItem("reset_otp", document.getElementById("otp").value.trim()); close(modal); open(passwordModal); } catch (err) { error.textContent = err.message; } });
    document.getElementById("resetPasswordForm")?.addEventListener("submit", async (event) => { event.preventDefault(); const error = document.getElementById("password-error-message"); error.textContent = ""; const password = document.getElementById("new-password").value; const confirm = document.getElementById("confirm-password").value; if (password !== confirm) { error.textContent = "Passwords do not match."; return; } try { await jsonRequest("/api/reset-password-with-otp/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ otp: localStorage.getItem("reset_otp"), new_password: password }) }); close(passwordModal); setMessage("Password updated. Redirecting to login...", "success"); localStorage.removeItem("reset_email"); localStorage.removeItem("reset_otp"); window.setTimeout(() => { window.location.href = "/login-template/"; }, 900); } catch (err) { error.textContent = err.message; } });
    document.querySelectorAll("[data-close-modal]").forEach((button) => button.addEventListener("click", () => close(document.getElementById(button.dataset.closeModal))));
  }
})();
