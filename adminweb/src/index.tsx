import { StrictMode } from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { BRAND_CONNECT } from "./lib/brand";

document.title = BRAND_CONNECT;

// Render the app
const rootElement = document.getElementById("app")!;
if (!rootElement.innerHTML) {
  const root = ReactDOM.createRoot(rootElement);
  root.render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}
