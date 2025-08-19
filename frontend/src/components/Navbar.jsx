// src/components/Navbar.jsx
import React from "react";
import { AppBar, Toolbar, Typography, Button, Box } from "@mui/material";
import { useNavigate } from "react-router-dom";

const Navbar = () => {
  const navigate = useNavigate();

  let role = "";
  let email = "";
  try {
    const u = JSON.parse(localStorage.getItem("user") || "null");
    role = u?.role || "";
    email = u?.email || "";
  } catch {}

  const handleLogout = () => {
    localStorage.clear();
    navigate("/");
  };

  return (
    <AppBar position="static" sx={{ backgroundColor: "#1565c0" }}>
      <Toolbar sx={{ display: "flex", justifyContent: "space-between" }}>
        <Typography variant="h6" sx={{ fontWeight: "bold" }}>
          YENDE SARL IA
        </Typography>
        <Box display="flex" alignItems="center" gap={2}>
          <Typography variant="body2">
            {email} {role ? `(${role})` : ""}
          </Typography>
          <Button
            variant="contained" color="secondary" onClick={handleLogout}
            sx={{ backgroundColor: "white", color: "#1565c0", "&:hover": { backgroundColor: "#e0e0e0" } }}
          >
            Déconnexion
          </Button>
        </Box>
      </Toolbar>
    </AppBar>
  );
};

export default Navbar;
