// src/routes/ProtectedRoute.jsx
import React from "react";
import { Navigate } from "react-router-dom";

const ProtectedRoute = ({ children }) => {
  const isAuthenticated = !!localStorage.getItem("token");
  // Si non authentifié -> retour à la racine "/" (écran de connexion)
  return isAuthenticated ? children : <Navigate to="/" replace />;
};

export default ProtectedRoute;
