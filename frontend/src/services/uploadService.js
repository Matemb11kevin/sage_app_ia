// src/services/uploadService.js
import axios from "axios";

const API_BASE = process.env.REACT_APP_API_BASE || "http://127.0.0.1:8000";

export async function uploadExcels({ type_fichier, mois, annee, files }) {
  if (!type_fichier || !mois || !annee) {
    throw new Error("Type, mois et année sont obligatoires.");
  }
  if (!files || files.length === 0) {
    throw new Error("Veuillez sélectionner au moins un fichier .xlsx.");
  }

  const token = localStorage.getItem("token");
  if (!token) throw new Error("Token invalide ou expiré");

  const form = new FormData();
  form.append("type_fichier", type_fichier);
  form.append("mois", mois);
  form.append("annee", String(annee));
  Array.from(files).forEach((f) => form.append("files", f));

  const { data } = await axios.post(`${API_BASE}/upload-excel`, form, {
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "multipart/form-data",
    },
  });

  return data; // { message: "..." }
}
