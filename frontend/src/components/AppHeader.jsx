import React from "react";
import { Moon, Sun } from "lucide-react";
import { useTheme } from "../context/ThemeProvider";
import { TrustRadarLogo } from "./TrustRadarLogo";

export function AppHeader() {
  const { theme, toggleTheme } = useTheme();

  return (
    <section className="topbar">
      <div className="brand">
        <TrustRadarLogo />
      </div>
      <div className="top-actions">
        <button className="theme-toggle icon-only" type="button" onClick={toggleTheme} aria-label="Toggle theme">
          {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
        </button>
      </div>
    </section>
  );
}
