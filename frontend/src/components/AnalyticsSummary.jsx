// src/components/AnalyticsSummary.jsx
import React, { useEffect, useMemo, useState } from "react";
import {
  Box, Grid, Card, CardContent, Typography, Divider,
  TextField, MenuItem, Button, Alert, CircularProgress, List, ListItem, Stack
} from "@mui/material";
import { getMonthSummary } from "../services/aiService";

const MOIS = [
  "janvier","fevrier","mars","avril","mai","juin",
  "juillet","aout","septembre","octobre","novembre","decembre",
];

const yearsAround = () => {
  const y = new Date().getFullYear();
  const out = [];
  for (let k = y - 1; k <= y + 1; k++) out.push(k);
  return out;
};

function nf(num) {
  try {
    return new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 2 }).format(num ?? 0);
  } catch { return String(num ?? 0); }
}

export default function AnalyticsSummary() {
  // ➜ période : d’abord depuis localStorage, sinon défaut date système
  const now = new Date();
  const [mois, setMois] = useState(localStorage.getItem("analysisMonth") || MOIS[now.getMonth()]);
  const [annee, setAnnee] = useState(Number(localStorage.getItem("analysisYear") || now.getFullYear()));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [summary, setSummary] = useState(null);

  const hasData = useMemo(() => !!summary && summary.kpis, [summary]);

  const fetchSummary = async (m = mois, y = annee) => {
    setLoading(true);
    setError("");
    try {
      const data = await getMonthSummary({ mois: m, annee: y });
      setSummary(data);
    } catch (e) {
      const msg = e?.response?.data?.detail || e?.message || "Erreur lors du chargement du résumé.";
      setError(String(msg));
      setSummary(null);
    } finally {
      setLoading(false);
    }
  };

  // 1) initial + 2) écoute les changements de période déclenchés par UploadSection
  useEffect(() => {
    fetchSummary(mois, annee);
    const onChange = (ev) => {
      const m = ev?.detail?.mois;
      const y = ev?.detail?.annee;
      if (m && y) {
        setMois(m);
        setAnnee(Number(y));
        fetchSummary(m, Number(y));
      }
    };
    window.addEventListener("analysis-period-changed", onChange);
    return () => window.removeEventListener("analysis-period-changed", onChange);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const k = summary?.kpis || {};
  const topVentes = summary?.top?.ventes_par_produit || [];
  const topDep = summary?.top?.depenses_par_categorie || [];
  const highlights = summary?.highlights || [];

  if (loading) {
    return (
      <Stack direction="row" spacing={1} alignItems="center" sx={{ mt: 1 }}>
        <CircularProgress size={18} />
        <Typography>Chargement…</Typography>
      </Stack>
    );
  }

  return (
    <Box sx={{ mt: 2 }}>
      {/* Filtres simples (tu peux les masquer si tu veux forcer la période d'upload) */}
      <Box sx={{
        p: 2, borderRadius: 2, bgcolor: "#f6f9ff",
        display: "flex", gap: 2, alignItems: "center", flexWrap: "wrap"
      }}>
        <TextField
          select size="small" label="Mois" value={mois}
          onChange={(e) => setMois(e.target.value)}
        >
          {MOIS.map(m => <MenuItem key={m} value={m}>{m}</MenuItem>)}
        </TextField>

        <TextField
          select size="small" label="Année" value={annee}
          onChange={(e) => setAnnee(Number(e.target.value))}
        >
          {yearsAround().map(y => <MenuItem key={y} value={y}>{y}</MenuItem>)}
        </TextField>

        <Button variant="contained" onClick={() => fetchSummary(mois, annee)} disabled={loading}>
          {loading ? <CircularProgress size={18} /> : "Actualiser"}
        </Button>

        <Typography variant="caption" sx={{ color: "text.secondary" }}>
          Période: <b>{mois}</b> / <b>{annee}</b>
        </Typography>
      </Box>

      {error && <Alert sx={{ mt: 2 }} severity="error">{error}</Alert>}

      {/* KPI cards */}
      {hasData && (
        <Grid container spacing={2} sx={{ mt: 1 }}>
          <Grid item xs={12} sm={6} md={3}>
            <Card><CardContent>
              <Typography variant="overline">CA total</Typography>
              <Typography variant="h5">{nf(k.ca_total)} FCFA</Typography>
            </CardContent></Card>
          </Grid>

          <Grid item xs={12} sm={6} md={3}>
            <Card><CardContent>
              <Typography variant="overline">Dépenses</Typography>
              <Typography variant="h5">{nf(k.depenses_total)} FCFA</Typography>
            </CardContent></Card>
          </Grid>

          <Grid item xs={12} sm={6} md={3}>
            <Card><CardContent>
              <Typography variant="overline">Marge %</Typography>
              <Typography variant="h5">
                {k.marge_pct == null ? "—" : `${nf(k.marge_pct)} %`}
              </Typography>
            </CardContent></Card>
          </Grid>

          <Grid item xs={12} sm={6} md={3}>
            <Card><CardContent>
              <Typography variant="overline">Coverage stock</Typography>
              <Typography variant="h5">
                {k.stock_coverage_days == null ? "—" : `${nf(k.stock_coverage_days)} j`}
              </Typography>
            </CardContent></Card>
          </Grid>

          <Grid item xs={12} sm={4} md={4}>
            <Card><CardContent>
              <Typography variant="overline">Écart banque (total)</Typography>
              <Typography variant="h6">{nf(k.banque_ecart_total)} FCFA</Typography>
            </CardContent></Card>
          </Grid>
          <Grid item xs={12} sm={4} md={4}>
            <Card><CardContent>
              <Typography variant="overline">Écart caisse (total)</Typography>
              <Typography variant="h6">{nf(k.caisse_ecart_total)} FCFA</Typography>
            </CardContent></Card>
          </Grid>
          <Grid item xs={12} sm={4} md={4}>
            <Card><CardContent>
              <Typography variant="overline">Écart clients (total)</Typography>
              <Typography variant="h6">{nf(k.clients_ecart_total)} FCFA</Typography>
            </CardContent></Card>
          </Grid>
        </Grid>
      )}

      {/* Tops + Highlights */}
      {hasData && (
        <Grid container spacing={2} sx={{ mt: 1 }}>
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>Top produits par CA</Typography>
                <Divider sx={{ my: 1 }} />
                {topVentes.length === 0 ? (
                  <Typography variant="body2">Aucune vente trouvée pour ce mois.</Typography>
                ) : (
                  <List dense>
                    {topVentes.map((r, i) => (
                      <ListItem key={i} disableGutters
                        secondaryTypographyProps={{ component: "div" }}>
                        <Typography sx={{ width: 28 }}>{i + 1}.</Typography>
                        <Typography sx={{ flex: 1 }}>{r.produit}</Typography>
                        <Typography sx={{ fontWeight: 700 }}>{nf(r.ca)} FCFA</Typography>
                      </ListItem>
                    ))}
                  </List>
                )}
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>Top dépenses par catégorie</Typography>
                <Divider sx={{ my: 1 }} />
                {topDep.length === 0 ? (
                  <Typography variant="body2">Aucune dépense trouvée pour ce mois.</Typography>
                ) : (
                  <List dense>
                    {topDep.map((r, i) => (
                      <ListItem key={i} disableGutters>
                        <Typography sx={{ width: 28 }}>{i + 1}.</Typography>
                        <Typography sx={{ flex: 1 }}>{r.categorie}</Typography>
                        <Typography sx={{ fontWeight: 700 }}>{nf(r.montant)} FCFA</Typography>
                      </ListItem>
                    ))}
                  </List>
                )}
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>Messages IA (highlights)</Typography>
                <Divider sx={{ my: 1 }} />
                {highlights.length === 0 ? (
                  <Typography variant="body2">Aucun signalement pour ce mois.</Typography>
                ) : (
                  <List dense>
                    {highlights.map((h, idx) => (
                      <ListItem key={idx} disableGutters>
                        <Typography variant="body2">• {h}</Typography>
                      </ListItem>
                    ))}
                  </List>
                )}
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {!loading && !hasData && !error && (
        <Alert sx={{ mt: 2 }} severity="info">
          Aucun résumé pour ce mois. Charge d’abord des fichiers puis clique “Actualiser”.
        </Alert>
      )}
    </Box>
  );
}
