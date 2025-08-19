// src/components/AnomaliesPanel.jsx
import React, { useEffect, useState, useMemo } from "react";
import {
  Box, Typography, CircularProgress, Alert, Chip, Stack, Divider,
  List, ListItem, ListItemText
} from "@mui/material";
import axios from "axios";

const API_BASE = process.env.REACT_APP_API_BASE || "http://127.0.0.1:8000";

const monthNameFR = (d=new Date()) =>
  ["janvier","fevrier","mars","avril","mai","juin","juillet","aout","septembre","octobre","novembre","decembre"][d.getMonth()];

export default function AnomaliesPanel({ mois = monthNameFR(), annee = new Date().getFullYear() }) {
  const [loading, setLoading] = useState(true);
  const [items, setItems]   = useState([]);
  const [error, setError]   = useState("");

  useEffect(() => {
    let alive = true;
    (async () => {
      setLoading(true); setError(""); 
      try {
        const token = localStorage.getItem("token");
        const { data } = await axios.get(`${API_BASE}/ai/anomalies`, {
          params: { mois, annee },
          headers: { Authorization: token ? `Bearer ${token}` : "" },
        });
        if (alive) setItems(Array.isArray(data) ? data : []);
      } catch (e) {
        if (alive) setError(e?.response?.data?.detail || e?.message || "Erreur chargement anomalies.");
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false; };
  }, [mois, annee]);

  const groups = useMemo(() => {
    const g = { critical: [], warning: [], info: [] };
    for (const it of items) {
      const key = String(it.severity || "").toLowerCase();
      if (g[key]) g[key].push(it);
    }
    return g;
  }, [items]);

  if (loading) {
    return <Stack direction="row" alignItems="center" spacing={1}><CircularProgress size={18}/><Typography>Chargement…</Typography></Stack>;
  }
  if (error) return <Alert severity="error">{error}</Alert>;
  if (!items.length) return <Alert severity="success">Aucune anomalie détectée pour {mois} {annee}.</Alert>;

  const SevChip = ({ s }) => {
    const label = s === "critical" ? "CRITIQUE" : s === "warning" ? "AVERT." : "INFO";
    const color = s === "critical" ? "error" : s === "warning" ? "warning" : "info";
    return <Chip size="small" color={color} label={label} />;
  };

  const Block = ({ title, list, sev }) => (
    !!list.length && (
      <Box sx={{ mb: 2 }}>
        <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 0.5 }}>
          <SevChip s={sev} />
          <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>{title}</Typography>
        </Stack>
        <List dense sx={{ bgcolor: "#fff", borderRadius: 1, border: "1px solid #eee" }}>
          {list.map((a) => (
            <React.Fragment key={`an-${a.id}`}>
              <ListItem alignItems="flex-start">
                <ListItemText
                  primary={`${a.object_name || a.object_type || a.type} — ${a.type?.toUpperCase?.() || a.type}`}
                  secondary={
                    <>
                      <Typography component="span" variant="body2">{a.message}</Typography>
                      {a.metric && (
                        <Typography component="span" variant="caption" sx={{ display: "block", color: "text.secondary" }}>
                          {a.metric}: {a.value ?? "-"} (seuil {a.threshold ?? "-"})
                        </Typography>
                      )}
                    </>
                  }
                />
              </ListItem>
              <Divider component="li" />
            </React.Fragment>
          ))}
        </List>
      </Box>
    )
  );

  return (
    <Box>
      <Block title="Anomalies critiques" list={groups.critical} sev="critical" />
      <Block title="Anomalies importantes" list={groups.warning} sev="warning" />
      <Block title="Informations" list={groups.info} sev="info" />
    </Box>
  );
}
