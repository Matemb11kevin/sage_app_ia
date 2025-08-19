// src/pages/Login.jsx
import React, { useState } from "react";
import {
  Container, Typography, TextField, Button, MenuItem, Box, Paper,
} from "@mui/material";
import { toast } from "react-toastify";
import { useNavigate } from "react-router-dom";
import { loginUser } from "../services/authService";
import logo from "../assets/logo-yende.png";

const roles = ["DG", "Comptable", "Membre"]; // purement informatif

const Login = () => {
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState(""); // décoratif
  const navigate = useNavigate();

  const handleLogin = async (e) => {
    e.preventDefault();
    try {
      const user = await loginUser(identifier, password);
      if (!user?.role) {
        toast.error("Rôle manquant dans la réponse serveur.");
        return;
      }
      toast.success("Connexion réussie !");
      navigate("/dashboard", { replace: true });
    } catch (err) {
      toast.error(String(err.message || err));
    }
  };

  return (
    <Container maxWidth="sm" sx={{ mt: 8 }}>
      <Paper elevation={4} sx={{ p: 4, backgroundColor: "#e3f2fd", textAlign: "center", borderRadius: "16px" }}>
        <Box sx={{ mb: 2 }}>
          <img src={logo} alt="Logo Yende" style={{ width: 100, height: 100, objectFit: "contain" }} />
        </Box>

        <Typography variant="h5" gutterBottom sx={{ fontWeight: "bold" }}>
          YENDE SARL IA - Connexion
        </Typography>

        <Box component="form" onSubmit={handleLogin} sx={{ mt: 3 }}>
          <TextField
            fullWidth label="Nom d'utilisateur ou Email" type="text" margin="normal"
            value={identifier} onChange={(e) => setIdentifier(e.target.value)} required
          />
          <TextField
            fullWidth label="Mot de passe" type="password" margin="normal"
            value={password} onChange={(e) => setPassword(e.target.value)} required
          />
          <TextField
            select fullWidth label="Rôle (déterminé par le serveur)" margin="normal"
            value={role} onChange={(e) => setRole(e.target.value)}
            helperText="Le rôle effectif vient de votre compte — ce champ est informatif." disabled
          >
            {roles.map((r) => (<MenuItem key={r} value={r}>{r}</MenuItem>))}
          </TextField>

          <Button fullWidth type="submit" variant="contained" sx={{ mt: 3, backgroundColor: "#1565c0" }}>
            Connexion
          </Button>

          <Typography
            variant="body2" align="center"
            sx={{ mt: 2, cursor: "pointer", color: "blue", textDecoration: "underline" }}
            onClick={() => navigate("/reset-password")}
          >
            Mot de passe oublié ?
          </Typography>
        </Box>
      </Paper>
    </Container>
  );
};

export default Login;
