// src/services/aiService.js
import axios from "axios";

const API_BASE = process.env.REACT_APP_API_BASE || "http://127.0.0.1:8000";

export async function getMonthSummary({ mois, annee }) {
  const token = localStorage.getItem("token");
  const { data } = await axios.get(`${API_BASE}/ai/summary`, {
    params: { mois, annee },
    headers: { Authorization: token ? `Bearer ${token}` : "" },
  });
  return data;
}
