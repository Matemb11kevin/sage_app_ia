// src/pages/ChangePasswordPopup.jsx
import React, { useState } from "react";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  TextField,
  Button,
  DialogActions,
} from "@mui/material";

const ChangePasswordPopup = ({ open, onClose, onSave }) => {
  const [newPassword, setNewPassword] = useState("");

  const handleSave = () => {
    if (newPassword.length < 8) {
      alert("Le mot de passe doit contenir au moins 8 caractères.");
      return;
    }
    onSave(newPassword);
  };

  return (
    <Dialog open={open} onClose={onClose}>
      <DialogTitle>Changer le mot de passe</DialogTitle>
      <DialogContent>
        <TextField
          autoFocus
          margin="dense"
          label="Nouveau mot de passe"
          type="password"
          fullWidth
          variant="standard"
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Annuler</Button>
        <Button onClick={handleSave}>Enregistrer</Button>
      </DialogActions>
    </Dialog>
  );
};

export default ChangePasswordPopup;
