// src/services/filesService.js
import axios from "axios";

const API_BASE = process.env.REACT_APP_API_BASE || "http://127.0.0.1:8000";

export async function listFiles(params = {}) {
  const token = localStorage.getItem("token");
  const { data } = await axios.get(`${API_BASE}/excel-files`, {
    params,
    headers: { Authorization: `Bearer ${token}` },
  });
  return data; // tableau d'objets ExcelFileResponse
}

export async function deleteFile(id) {
  const token = localStorage.getItem("token");
  const { data } = await axios.delete(`${API_BASE}/delete-excel/${id}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return data; // { message: ... }
}
