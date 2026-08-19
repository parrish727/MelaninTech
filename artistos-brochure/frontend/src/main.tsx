import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { AgenticBrochure } from "./components/AgenticBrochure";
import "./index.css";
const root = document.getElementById("root");
if (!root) throw new Error("Root element not found");
createRoot(root).render(<StrictMode><AgenticBrochure /></StrictMode>);
