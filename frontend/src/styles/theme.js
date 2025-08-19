// src/styles/theme.js
import { createTheme } from "@mui/material/styles";

const theme = createTheme({
  palette: {
    primary: {
      main: "#1565c0", // Bleu professionnel
    },
    secondary: {
      main: "#e3f2fd", // Bleu clair pour fond ou hover
    },
  },
  typography: {
    fontFamily: "Roboto, sans-serif",
  },
});

export default theme;
