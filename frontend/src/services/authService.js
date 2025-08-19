// src/services/authService.js
import axios from "axios";

const API_BASE = process.env.REACT_APP_API_BASE || "http://127.0.0.1:8000";

export async function loginUser(identifier, password) {
  const form = new URLSearchParams();
  form.append("username", identifier); // username OU email
  form.append("password", password);

  try {
    const { data } = await axios.post(`${API_BASE}/auth/login`, form, {
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    });

    // Attendu : { access_token, token_type, user:{ id, username, email, role } }
    localStorage.setItem("token", data.access_token);
    localStorage.setItem("user", JSON.stringify(data.user));
    localStorage.removeItem("role"); // on ne garde que user.role venant du backend
    return data.user;
  } catch (err) {
    const msg = err?.response?.data?.detail || err?.message || "Erreur de connexion";
    throw new Error(msg);
  }
}

export function getToken() {
  return localStorage.getItem("token");
}

export function getCurrentUser() {
  const raw = localStorage.getItem("user");
  try { return raw ? JSON.parse(raw) : null; } catch { return null; }
}

export function logout() {
  localStorage.removeItem("token");
  localStorage.removeItem("user");
  localStorage.removeItem("role");
}
