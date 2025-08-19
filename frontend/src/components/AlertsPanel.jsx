// src/components/AlertsPanel.jsx
import React, { useEffect, useState, useCallback, useMemo } from "react";
import {
  Typography, CircularProgress, Alert, Chip, Stack, Button,
  List, ListItem, ListItemText, Divider
} from "@mui/material";
import axios from "axios";

const API_BASE = process.env.REACT_APP_API_BASE || "http://127.0.0.1:8000";

const monthNameFR = (d = new Date()) =>
  ["janvier","fevrier","mars","avril","mai","juin","juillet","aout","septembre","octobre","novembre","decembre"][d.getMonth()];

function readStoredPeriod() {
  const m = localStorage.getItem("analysisMonth");
  const a = localStorage.getItem("analysisYear");
  return {
    mois: m || monthNameFR(),
    annee: a ? Number(a) : new Date().getFullYear(),
  };
}

export default function AlertsPanel() {
  // -> période pilotée par localStorage + évènement "analysis-period-changed"
  const [periode, setPeriode] = useState(readStoredPeriod());
  const { mois, annee } = periode;

  const [loading, setLoading] = useState(true);
  const [items, setItems]   = useState([]);
  const [error, setError]   = useState("");

  // Token + headers mémoïsés (évite les warnings ESLint)
  const token = localStorage.getItem("token") || "";
  const headers = useMemo(
    () => (token ? { Authorization: `Bearer ${token}` } : {}),
    [token]
  );

  const refresh = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const { data } = await axios.get(`${API_BASE}/ai/alerts`, {
        params: { mois, annee, status: "open" },
        headers,
      });
      setItems(Array.isArray(data) ? data : []);
    } catch (e) {
      setError(e?.response?.data?.detail || e?.message || "Erreur chargement alertes.");
    } finally {
      setLoading(false);
    }
  }, [mois, annee, headers]);

  // Charger à l’ouverture + quand la période change
  useEffect(() => { refresh(); }, [refresh]);

  // Écoute les changements de période poussés par UploadSection
  useEffect(() => {
    const handler = (e) => {
      const { mois, annee } = e.detail || {};
      if (mois && annee) setPeriode({ mois, annee: Number(annee) });
    };
    window.addEventListener("analysis-period-changed", handler);
    return () => window.removeEventListener("analysis-period-changed", handler);
  }, []);

  const action = async (id, kind) => {
    try {
      await axios.post(`${API_BASE}/ai/alerts/${id}/${kind}`, {}, { headers });
      await refresh();
    } catch (e) {
      setError(e?.response?.data?.detail || e?.message || "Action impossible.");
    }
  };

  const SeverityChip = ({ s }) => {
    const label = s === "critical" ? "CRITIQUE" : s === "warning" ? "AVERT." : "INFO";
    const color = s === "critical" ? "error" : s === "warning" ? "warning" : "info";
    return <Chip size="small" color={color} label={label} sx={{ mr: 1 }} />;
  };

  if (loading) {
    return (
      <Stack direction="row" alignItems="center" spacing={1}>
        <CircularProgress size={18} />
        <Typography>Chargement…</Typography>
      </Stack>
    );
  }
  if (error) return <Alert severity="error">{error}</Alert>;
  if (!items.length) return <Alert severity="info">Aucune alerte ouverte pour {mois} {annee}.</Alert>;

  return (
    <List dense sx={{ bgcolor: "#fff", borderRadius: 1, border: "1px solid #eee" }}>
      {items.map((a, i) => (
        <React.Fragment key={`al-${a.id}`}>
          <ListItem
            alignItems="flex-start"
            secondaryAction={
              <Stack direction="row" spacing={1}>
                <Button size="small" onClick={() => action(a.id, "ack")}>Marquer lu</Button>
                <Button size="small" color="success" onClick={() => action(a.id, "close")}>Clore</Button>
              </Stack>
            }
          >
            <ListItemText
              primary={
                <Stack direction="row" alignItems="center">
                  <SeverityChip s={String(a.severity).toLowerCase()} />
                  <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>{a.title}</Typography>
                </Stack>
              }
              secondary={
                <Typography variant="body2" sx={{ color: "text.secondary" }}>
                  {a.body}
                </Typography>
              }
            />
          </ListItem>
          {i < items.length - 1 && <Divider component="li" />}
        </React.Fragment>
      ))}
    </List>
  );
}
