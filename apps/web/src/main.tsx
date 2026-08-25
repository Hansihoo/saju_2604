import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles.css";
import { installResultOverflowAuditObserver } from "./shared/overflowAudit";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

if (import.meta.env.DEV) {
  installResultOverflowAuditObserver(document.body);
}
