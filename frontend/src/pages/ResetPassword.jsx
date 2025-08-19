// src/pages/ResetPassword.jsx
import React, { useMemo, useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import {
  Container,
  Paper,
  Box,
  Typography,
  TextField,
  Button,
} from "@mui/material";
import { toast } from "react-toastify";

const API = process.env.REACT_APP_API_BASE || "http://127.0.0.1:8000";

export default function ResetPassword() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const token = params.get("token");

  const [email, setEmail] = useState("");
  const [pwd1, setPwd1] = useState("");
  const [pwd2, setPwd2] = useState("");

  const withToken = useMemo(() => !!token, [token]);

  const requestLink = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch(`${API}/auth/request-reset`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.detail || "Échec de l’envoi");
      }
      toast.success("Email de réinitialisation envoyé. Vérifiez votre boîte !");
      navigate("/");
    } catch (err) {
      toast.error(String(err.message || err));
    }
  };

  const setNewPassword = async (e) => {
    e.preventDefault();
    if (pwd1 !== pwd2) {
      toast.error("Les mots de passe ne correspondent pas.");
      return;
    }
    try {
      const res = await fetch(`${API}/auth/confirm-reset`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, new_password: pwd1 }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.detail || "Échec de la réinitialisation");
      }
      toast.success("Mot de passe modifié. Vous pouvez vous connecter.");
      navigate("/");
    } catch (err) {
      toast.error(String(err.message || err));
    }
  };

  return (
    <Container maxWidth="sm" sx={{ mt: 8 }}>
      <Paper
        elevation={4}
        sx={{
          p: 4,
          borderRadius: "16px",
          textAlign: "center",
          backgroundColor: "#e3f2fd", // même fond que Login
        }}
      >
        <Typography variant="h5" gutterBottom sx={{ fontWeight: "bold" }}>
          {withToken ? "Définir un nouveau mot de passe" : "Mot de passe oublié"}
        </Typography>

        {!withToken ? (
          <Box component="form" onSubmit={requestLink} sx={{ mt: 3 }}>
            <TextField
              label="Votre email *"
              type="email"
              fullWidth
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
            <Box sx={{ mt: 2, display: "flex", gap: 2, justifyContent: "center" }}>
              <Button
                type="submit"
                variant="contained"
                sx={{ backgroundColor: "#1565c0" }} // même bleu que Login
              >
                Recevoir le lien
              </Button>
              <Button variant="text" onClick={() => navigate("/")}>
                Annuler
              </Button>
            </Box>
          </Box>
        ) : (
          <Box component="form" onSubmit={setNewPassword} sx={{ mt: 3 }}>
            <TextField
              label="Nouveau mot de passe"
              type="password"
              fullWidth
              value={pwd1}
              onChange={(e) => setPwd1(e.target.value)}
              required
            />
            <TextField
              label="Confirmer le mot de passe"
              type="password"
              fullWidth
              sx={{ mt: 2 }}
              value={pwd2}
              onChange={(e) => setPwd2(e.target.value)}
              required
            />
            <Box sx={{ mt: 2, display: "flex", gap: 2, justifyContent: "center" }}>
              <Button
                type="submit"
                variant="contained"
                sx={{ backgroundColor: "#1565c0" }}
              >
                Valider
              </Button>
              <Button variant="text" onClick={() => navigate("/")}>
                Annuler
              </Button>
            </Box>
          </Box>
        )}
      </Paper>
    </Container>
  );
}
