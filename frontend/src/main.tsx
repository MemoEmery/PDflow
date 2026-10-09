import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import "@fontsource-variable/dm-sans";  // texto, UI e título principal (peso 500)
import "@fontsource-variable/geist";    // títulos de seção (a partir de 24px)
import App from "./App";
import "./styles.css";
createRoot(document.getElementById("root")!).render(<BrowserRouter><App /></BrowserRouter>);
