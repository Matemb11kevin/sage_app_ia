// src/pages/Dashboard.jsx
import React, { useEffect, useState } from "react";
import { Box, Typography, Alert, Divider, Button, Stack } from "@mui/material";
import UploadSection from "../components/UploadSection";
import AnomaliesPanel from "../components/AnomaliesPanel";
import AlertsPanel from "../components/AlertsPanel";
import AnalyticsSummary from "../components/AnalyticsSummary"; // <-- ✅

function getRole() {
  try {
    const stored = localStorage.getItem("role") || localStorage.getItem("userRole");
    if (stored) return String(stored).toLowerCase();
    const token = localStorage.getItem("token");
    if (token && token.split(".").length === 3) {
      const payload = JSON.parse(atob(token.split(".")[1]));
      if (payload?.role) return String(payload.role).toLowerCase();
    }
  } catch (_) {}
  return "";
}
function getEmail() {
  try {
    const stored = localStorage.getItem("email");
    if (stored) return stored;
    const token = localStorage.getItem("token");
    if (token && token.split(".").length === 3) {
      const payload = JSON.parse(atob(token.split(".")[1]));
      return payload?.sub || payload?.email || "";
    }
  } catch (_) {}
  return "";
}
const monthNameFR = (d = new Date()) =>
  ["janvier","fevrier","mars","avril","mai","juin","juillet","aout","septembre","octobre","novembre","decembre"][d.getMonth()];

export default function Dashboard() {
  const role = getRole();
  const email = getEmail();

  const isComptable = role === "comptable";
  const canSeeAnalysis = ["comptable","dg","membre","utilisateur","user","admin"].includes(role);

  const handleLogout = () => {
    try {
      localStorage.removeItem("token");
      localStorage.removeItem("role");
      localStorage.removeItem("userRole");
      localStorage.removeItem("email");
    } finally {
      window.location.replace("/"); // retour à l’écran de connexion
    }
  };

  // --------- Période affichée = dernière période analysée ou mois courant ----------
  const currentMonth = monthNameFR();
  const currentYear  = new Date().getFullYear();

  const [period, setPeriod] = useState(() => ({
    mois:  localStorage.getItem("analysisMonth") || currentMonth,
    annee: Number(localStorage.getItem("analysisYear")) || currentYear,
  }));

  // Se synchronise quand UploadSection a fini (évènement custom)
  useEffect(() => {
    const onPeriod = (e) => {
      const m = e?.detail?.mois;
      const y = e?.detail?.annee;
      if (m && y) setPeriod({ mois: m, annee: Number(y) });
    };
    window.addEventListener("analysis-period-changed", onPeriod);
    return () => window.removeEventListener("analysis-period-changed", onPeriod);
  }, []);

  return (
    <Box sx={{ p: 3 }}>
      {/* Bandeau titre + email/role + Déconnexion */}
      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 2 }}>
        <Typography variant="h4">Tableau de bord</Typography>
        <Stack direction="row" spacing={1} alignItems="center">
          {!!email && (
            <Typography variant="body2" sx={{ color: "text.secondary" }}>
              {email} ({role ? role.toUpperCase() : "INVITÉ"})
            </Typography>
          )}
          <Button variant="contained" color="primary" onClick={handleLogout}>
            DÉCONNEXION
          </Button>
        </Stack>
      </Stack>

      {/* Section Upload : uniquement pour COMPTABLE */}
      {isComptable && (
        <Box sx={{ mt: 3 }}>
          <UploadSection />
        </Box>
      )}

      {/* Section Analyse & Rapports : structure identique à ta capture (403) */}
      {canSeeAnalysis ? (
        <Box sx={{ mt: 4 }}>
          <Typography variant="h5" gutterBottom>Section Analyse et Rapports</Typography>
          <Typography variant="body2" sx={{ mb: 2 }}>
            Contenu pour le DG, les comptables et les utilisateurs privilégiés :
          </Typography>

          <Box sx={{ p: 2, borderRadius: 2, bgcolor: "#e8f2ff" }}>
            {/* Période affichée */}
            <Typography variant="caption" sx={{ color: "text.secondary", display: "block", mb: 1 }}>
              Période analysée : <b>{period.mois} {period.annee}</b>
            </Typography>

            {/* Bloc 1 — Détection d’anomalies */}
            <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 0.5 }}>
              📌 Détection d’anomalies
            </Typography>
            <Typography variant="body2" sx={{ mb: 1.5 }}>
              Cette section affiche les anomalies détectées à partir des fichiers chargés.
            </Typography>
            <AnomaliesPanel mois={period.mois} annee={period.annee} />

            <Divider sx={{ my: 2 }} />

            {/* Bloc 2 — Résumés automatiques */}
            <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 0.5 }}>
              🧾 Résumés automatiques
            </Typography>
            <Typography variant="body2" sx={{ mb: 1 }}>
              Résumés financiers, graphiques et alertes IA.
            </Typography>
            {/* KPI + Tops */}
            <AnalyticsSummary />
            {/* Alertes IA (ouvertes) */}
            <Box sx={{ mt: 2 }}>
              <AlertsPanel mois={period.mois} annee={period.annee} />
            </Box>
          </Box>
        </Box>
      ) : (
        <Alert sx={{ mt: 4 }} severity="warning">
          Accès réservé. Contactez l’administrateur pour obtenir un rôle valide.
        </Alert>
      )}
    </Box>
  );
}
