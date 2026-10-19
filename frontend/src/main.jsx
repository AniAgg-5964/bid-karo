import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import "./index.css";
import "./i18n";
import App from "./App";
import { AuthProvider } from "./contexts/AuthContext";
import { ThemeProvider } from "./contexts/ThemeContext";
import { ToastProvider } from "./contexts/ToastContext";
import { ErrorBoundary } from "./components/ui/ErrorBoundary";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <ThemeProvider>
      <AuthProvider>
        <ToastProvider>
          <BrowserRouter>
            <ErrorBoundary>
              <App />
            </ErrorBoundary>
          </BrowserRouter>
        </ToastProvider>
      </AuthProvider>
    </ThemeProvider>
  </StrictMode>,
);
