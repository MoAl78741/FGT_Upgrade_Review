import { Shield, Sun, Moon } from "lucide-react";
import { Link } from "react-router-dom";
import { useTheme } from "../contexts/ThemeContext";
import SettingsModal from "./SettingsModal";

export default function Header() {
  const { theme, setTheme } = useTheme();
  const isDark = theme === "obsidian";

  function toggle() {
    setTheme(isDark ? "fortinet" : "obsidian");
  }

  return (
    <header className="bg-navy-800 border-b border-navy-700 sticky top-0 z-50">
      {/* Accent line at top */}
      <div
        className="h-0.5 w-full"
        style={{ background: "linear-gradient(90deg, rgb(var(--accent)) 0%, rgb(var(--accent-dark)) 60%, transparent 100%)" }}
      />
      <div className="max-w-screen-2xl mx-auto px-6 py-3 flex items-center gap-3">
        {/* Logo mark */}
        <div
          className="flex items-center justify-center w-8 h-8 rounded-lg shrink-0"
          style={{ background: "rgb(var(--accent) / 0.15)", border: "1px solid rgb(var(--accent) / 0.3)" }}
        >
          <Shield className="text-brand-500 w-4 h-4" />
        </div>

        <div className="flex items-center gap-2">
          <Link
            to="/"
            className="text-white font-semibold text-base tracking-tight hover:text-brand-500 transition-colors"
          >
            FortiGate Upgrade Dashboard
          </Link>
          <span
            className="text-xs px-1.5 py-0.5 rounded font-mono font-medium"
            style={{
              background: "rgb(var(--accent) / 0.12)",
              color: "rgb(var(--accent))",
              border: "1px solid rgb(var(--accent) / 0.25)",
            }}
          >
            v2
          </span>
        </div>

        {/* Divider */}
        <div className="h-4 w-px bg-gray-700 hidden sm:block" />
        <span className="text-xs text-gray-500 hidden sm:block tracking-wide uppercase font-medium">
          Release Notes Analyzer
        </span>

        {/* Right-side icon cluster */}
        <div className="ml-auto flex items-center gap-2">

        <SettingsModal />

        {/* Light / Dark toggle */}
        <div className="relative group">
          <button
            onClick={toggle}
            aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
            className="flex items-center justify-center w-8 h-8 rounded-lg transition-all duration-150 hover:scale-105"
            style={{
              background: "rgb(var(--accent) / 0.1)",
              border: "1px solid rgb(var(--accent) / 0.2)",
            }}
          >
            {isDark
              ? <Sun  className="w-4 h-4 text-brand-500" />
              : <Moon className="w-4 h-4 text-brand-500" />}
          </button>
          {/* Tooltip */}
          <span className="absolute top-full right-0 mt-2 px-2 py-1 text-xs bg-navy-900 text-white rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none border border-navy-700">
            {isDark ? "Light mode" : "Dark mode"}
          </span>
        </div>

        </div>{/* end icon cluster */}
      </div>
    </header>
  );
}
