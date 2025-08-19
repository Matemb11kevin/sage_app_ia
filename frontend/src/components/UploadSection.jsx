// src/components/UploadSection.jsx 
import React, { useState, useCallback } from "react";
import {
  Box,
  Typography,
  Button,
  MenuItem,
  TextField,
  Stack,
  Alert,
  Chip,
  Paper,
  Divider,
  Collapse,
  Menu,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  CircularProgress,
  List,
  ListItem,
  ListItemText,
} from "@mui/material";
import axios from "axios";

const API_BASE = process.env.REACT_APP_API_BASE || "http://127.0.0.1:8000";

/** Libellés côté UI (valeurs backend inchangées) */
const TYPES = [
  { value: "depenses_mensuelles", label: "Les dépenses mensuelles" },
  { value: "ventes_journalieres", label: "Ventes des différents produits par jours" },
  { value: "achats_journaliers", label: "Achats de produits par jours" },
  { value: "situation_clients_mensuelle", label: "Situation des clients par mois" },
  { value: "marge_produits_mensuelle", label: "Marge de gain de chaque produits par mois" },
  { value: "stock_journalier", label: "État de stock par jours" },
  { value: "transactions_bancaires_mensuelles", label: "Transaction bancaire par mois" },
  { value: "solde_caisse_mensuelle", label: "Solde caisse par mois" },
];

const TYPE_GUIDE = {
  depenses_mensuelles: {
    titre: "Catégories (par mois)",
    chips: [
      "transport et logistique",
      "entretien équipements",
      "frais de personnel",
      "autres achats",
      "services extérieures",
      "droit timbre-enregistrement",
      "manquant + perte coulage",
    ],
    colonnesMin: ["Catégorie", "Montant"],
  },
  ventes_journalieres: {
    titre: "Produits (par jour)",
    chips: ["Super", "Gasoil", "pétrole", "Gaz butane", "lubrifiants", "Gaz bouteille"],
    colonnesMin: ["Date", "Produit", "Quantité", "(Prix unitaire ou CA)"],
  },
  achats_journaliers: {
    titre: "Produits (par jour)",
    chips: ["Super", "Gasoil", "pétrole", "Gaz butane", "lubrifiants", "Gaz bouteille"],
    colonnesMin: ["Date", "Produit", "Quantité", "(Coût unitaire ou Coût total)"],
  },
  situation_clients_mensuelle: {
    titre: "Clients livrés (par mois)",
    chips: ["(dépend de vos clients livrés)"],
    colonnesMin: ["Client", "Encours début", "Facture", "Réglé", "Encours fin"],
  },
  marge_produits_mensuelle: {
    titre: "Produits (par mois)",
    chips: ["Super", "Gasoil", "pétrole", "Gaz butane", "lubrifiants", "Gaz bouteille"],
    colonnesMin: ["Produit", "CA", "COGS/Coût", "Marge", "(Marge %)"],
  },
  stock_journalier: {
    titre: "Stock par jour (par produit)",
    chips: ["Super", "Gasoil", "pétrole", "Gaz butane", "lubrifiants", "Gaz bouteille"],
    colonnesMin: [
      "Date",
      "Produit",
      "Stock initial",
      "Réception",
      "Vente",
      "Pertes",
      "Regul scdp",
      "Stock Final",
    ],
  },
  transactions_bancaires_mensuelles: {
    titre: "Banque (par mois)",
    chips: ["(par banque)"],
    colonnesMin: ["Solde début", "Encaissements", "Décaissements", "Solde fin"],
  },
  solde_caisse_mensuelle: {
    titre: "Caisse (par mois)",
    chips: ["(par caisse/site)"],
    colonnesMin: ["Solde début", "Encaissements", "Décaissements", "Solde fin"],
  },
};

const MOIS = [
  "janvier","fevrier","mars","avril","mai","juin",
  "juillet","aout","septembre","octobre","novembre","decembre",
];

const anneesAutour = () => {
  const y = new Date().getFullYear();
  const years = [];
  for (let k = y - 5; k <= y + 2; k++) years.push(k);
  return years;
};

const UploadSection = () => {
  const [files, setFiles] = useState([]);
  const [typeFichier, setTypeFichier] = useState("");
  const [mois, setMois] = useState("");
  const [annee, setAnnee] = useState(new Date().getFullYear());
  const [successMessage, setSuccessMessage] = useState("");
  const [error, setError] = useState("");

  // menu suppression
  const [deleteAnchor, setDeleteAnchor] = useState(null);
  const [deleteList, setDeleteList] = useState([]);
  const deleteMenuOpen = Boolean(deleteAnchor);

  // confirmation
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  const onFileInputChange = (e) => {
    const selected = Array.from(e.target.files || []);
    setFiles(selected);
  };

  const onDrop = useCallback((e) => {
    e.preventDefault();
    const dropped = Array.from(e.dataTransfer.files || []);
    setFiles(dropped);
  }, []);

  const onDragOver = (e) => e.preventDefault();

  /** 1) Clic sur "Uploader" -> validation -> ouvrir confirmation */
  const handleUploadClick = () => {
    setSuccessMessage("");
    setError("");
    if (!typeFichier || !mois || !annee) {
      setError("Veuillez sélectionner le type de fichier, le mois et l’année.");
      return;
    }
    if (!files.length) {
      setError("Veuillez sélectionner au moins un fichier .xlsx.");
      return;
    }
    const invalid = files.find((f) => !f.name.toLowerCase().endsWith(".xlsx"));
    if (invalid) {
      setError(`Seuls les fichiers .xlsx sont autorisés (fichier invalide : ${invalid.name})`);
      return;
    }
    setConfirmOpen(true);
  };

  /** 2) Chaîne complète : Upload -> ETL (qui lance l’IA en backend) */
  const performUploadAndAnalyze = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem("token");

      // 2.1 Upload
      const form = new FormData();
      form.append("type_fichier", typeFichier);
      form.append("mois", mois);
      form.append("annee", String(annee));
      files.forEach((f) => form.append("files", f));

      await axios.post(`${API_BASE}/upload-excel`, form, {
        headers: {
          Authorization: token ? `Bearer ${token}` : "",
          "Content-Type": "multipart/form-data",
        },
      });

      // 2.2 ETL + Analyse (déclenchée côté backend)
      const { data } = await axios.post(
        `${API_BASE}/etl/load-month`,
        { mois, annee, type_fichier: typeFichier },
        { headers: { Authorization: token ? `Bearer ${token}` : "" } }
      );

      const rows = data?.etl_summary?.rows_loaded || {};
      const ana = data?.analysis || {};
      const anomalies = ana?.inserted_anomalies ?? ana?.count ?? 0;
      const crit = ana?.critical ?? 0;

      setSuccessMessage(
        `✅ Chargement terminé. ` +
        `Ventes:${rows.ventes||0} Achats:${rows.achats||0} Stock:${rows.stock||0} ` +
        `Dépenses:${rows.depenses||0} Marge:${rows.marge||0} Banque:${rows.banque||0} ` +
        `Caisse:${rows.caisse||0} Clients:${rows.clients||0}. ` +
        `Analyse IA: ${anomalies} anomalie(s), dont ${crit} critique(s).`
      );

      // >>> AJOUT — mémoriser la période et notifier le dashboard (Alerts/Anomalies)
      localStorage.setItem("analysisMonth", mois);
      localStorage.setItem("analysisYear", String(annee));
      window.dispatchEvent(new CustomEvent("analysis-period-changed", { detail: { mois, annee } }));

      setFiles([]);
    } catch (err) {
      const msg =
        err?.response?.data?.detail ||
        err?.message ||
        "Erreur durant l’opération (upload/ETL/IA).";
      setError(String(msg));
    } finally {
      setLoading(false);
      setConfirmOpen(false);
    }
  };

  // Suppression (menu)
  const openDeleteMenu = async (e) => {
    setDeleteAnchor(e.currentTarget);
    setError("");
    setSuccessMessage("");

    try {
      const token = localStorage.getItem("token");
      const params = {
        mine: true,
        type_fichier: typeFichier || undefined,
        mois: mois || undefined,
        annee: annee || undefined,
      };
      const { data } = await axios.get(`${API_BASE}/excel-files`, {
        params,
        headers: { Authorization: token ? `Bearer ${token}` : "" },
      });
      setDeleteList(Array.isArray(data) ? data : []);
    } catch (err) {
      const msg = err?.response?.data?.detail || err?.message || "Erreur de récupération des fichiers.";
      setError(String(msg));
      setDeleteList([]);
    }
  };

  const closeDeleteMenu = () => setDeleteAnchor(null);

  const handleDelete = async (file) => {
    const ok = window.confirm(`Supprimer définitivement « ${file.filename} » ?`);
    if (!ok) return;
    try {
      const token = localStorage.getItem("token");
      await axios.delete(`${API_BASE}/delete-excel/${file.id}`, {
        headers: { Authorization: token ? `Bearer ${token}` : "" },
      });
      setSuccessMessage(`🗑️ Fichier « ${file.filename} » supprimé avec succès.`);
      setDeleteList((prev) => prev.filter((f) => f.id !== file.id));
    } catch (err) {
      const msg =
        err?.response?.data?.detail ||
        "Suppression refusée ou erreur serveur.";
      setError(String(msg));
    }
  };

  const guide = TYPE_GUIDE[typeFichier];

  return (
    <Box
      mt={4}
      sx={{
        border: "2px dashed #aaa",
        borderRadius: 4,
        p: 4,
        backgroundColor: "#f0f4ff",
      }}
      onDrop={onDrop}
      onDragOver={onDragOver}
    >
      <Typography variant="h6" gutterBottom color="primary">
        Section Comptable : Téléchargement de Fichiers Excel
      </Typography>
      <Typography variant="body2" gutterBottom>
        Choisissez le <b>type</b>, le <b>mois</b> et l’<b>année</b>, puis glissez-déposez vos fichiers
        <b> .xlsx</b> ou cliquez pour sélectionner.
      </Typography>

      <Stack direction={{ xs: "column", sm: "row" }} spacing={2} sx={{ mt: 2 }}>
        <TextField
          select
          fullWidth
          label="Type de fichier"
          value={typeFichier}
          onChange={(e) => setTypeFichier(e.target.value)}
        >
          {TYPES.map((t) => (
            <MenuItem key={t.value} value={t.value}>
              {t.label}
            </MenuItem>
          ))}
        </TextField>

        <TextField
          select
          fullWidth
          label="Mois"
          value={mois}
          onChange={(e) => setMois(e.target.value)}
        >
          {MOIS.map((m) => (
            <MenuItem key={m} value={m}>{m}</MenuItem>
          ))}
        </TextField>

        <TextField
          select
          fullWidth
          label="Année"
          value={annee}
          onChange={(e) => setAnnee(Number(e.target.value))}
        >
          {anneesAutour().map((y) => (
            <MenuItem key={y} value={y}>{y}</MenuItem>
          ))}
        </TextField>
      </Stack>

      {/* Panneau d'aide contextuel */}
      <Collapse in={Boolean(guide)}>
        {guide && (
          <Paper elevation={0} sx={{ mt: 2, p: 2, bgcolor: "#e9f3ff", borderRadius: 2 }}>
            <Typography variant="subtitle2" color="primary" sx={{ fontWeight: 700 }}>
              {guide.titre}
            </Typography>
            <Box sx={{ mt: 1, display: "flex", flexWrap: "wrap", gap: 1 }}>
              {guide.chips.map((c) => (
                <Chip key={c} size="small" label={c} />
              ))}
            </Box>
            <Divider sx={{ my: 1.5 }} />
            <Typography variant="caption" sx={{ color: "text.secondary" }}>
              Colonnes minimales : {guide.colonnesMin.join(" · ")}
            </Typography>
          </Paper>
        )}
      </Collapse>

      <Box
        sx={{
          mt: 3,
          border: "2px dashed #90caf9",
          borderRadius: 2,
          p: 3,
          background: "#e3f2fd",
          textAlign: "center",
          cursor: "pointer",
        }}
        onClick={() => document.getElementById("excel-input")?.click()}
      >
        <Typography variant="body2">
          Glissez-déposez vos fichiers ici ou cliquez pour sélectionner
        </Typography>

        <input
          id="excel-input"
          type="file"
          accept=".xlsx"
          multiple
          onChange={onFileInputChange}
          style={{ display: "none" }}
        />

        {!!files.length && (
          <Typography variant="caption" display="block" sx={{ mt: 1 }}>
            {files.length} fichier(s) sélectionné(s) :{" "}
            {files.map((f) => f.name).join(", ")}
          </Typography>
        )}
      </Box>

      <Stack direction="row" spacing={2} sx={{ mt: 2 }}>
        <Button
          variant="contained"
          color="success"
          onClick={handleUploadClick}
          disabled={files.length === 0 || !typeFichier || !mois || !annee || loading}
          startIcon={loading ? <CircularProgress size={16} /> : null}
        >
          {loading ? "EN COURS..." : "UPLOADER LES FICHIERS"}
        </Button>

        {/* Bouton de suppression (avec menu déroulant) */}
        <Button
          variant="outlined"
          color="error"
          onClick={openDeleteMenu}
        >
          SUPPRIMER UN FICHIER
        </Button>

        <Menu
          anchorEl={deleteAnchor}
          open={deleteMenuOpen}
          onClose={closeDeleteMenu}
          PaperProps={{ sx: { maxHeight: 360, minWidth: 360 } }}
        >
          {deleteList.length === 0 && (
            <MenuItem disabled>Aucun fichier trouvé pour ces filtres.</MenuItem>
          )}
          {deleteList.map((f) => (
            <MenuItem
              key={f.id}
              onClick={() => handleDelete(f)}
              title={`Type: ${f.type_fichier} • Mois: ${f.mois} • Année: ${f.annee}`}
            >
              {f.filename} — {f.mois}/{f.annee}
            </MenuItem>
          ))}
        </Menu>
      </Stack>

      {successMessage && (
        <Alert sx={{ mt: 2 }} severity="success">
          {successMessage}
        </Alert>
      )}
      {error && (
        <Alert sx={{ mt: 2 }} severity="error">
          {error}
        </Alert>
      )}

      {/* Boîte de dialogue de confirmation */}
      <Dialog open={confirmOpen} onClose={() => (!loading && setConfirmOpen(false))} fullWidth maxWidth="sm">
        <DialogTitle>Confirmer le chargement & l’analyse</DialogTitle>
        <DialogContent dividers>
          <DialogContentText sx={{ mb: 1 }}>
            Vous allez charger et analyser :
          </DialogContentText>
          <List dense>
            <ListItem>
              <ListItemText primary={`Type : ${TYPES.find(t => t.value === typeFichier)?.label || typeFichier}`} />
            </ListItem>
            <ListItem>
              <ListItemText primary={`Mois / Année : ${mois} / ${annee}`} />
            </ListItem>
            <ListItem>
              <ListItemText
                primary={`Fichiers (${files.length})`}
                secondary={files.map(f => f.name).join(", ")}
              />
            </ListItem>
          </List>
          <Typography variant="caption" sx={{ color: "text.secondary" }}>
            Après l’upload, l’ETL chargera les données et l’IA s’exécutera automatiquement.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmOpen(false)} disabled={loading}>Annuler</Button>
          <Button variant="contained" onClick={performUploadAndAnalyze} disabled={loading}>
            {loading ? <CircularProgress size={20} /> : "Oui, lancer"}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default UploadSection;
