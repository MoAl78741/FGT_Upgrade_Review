import { createContext, useContext, useState } from "react";

const DEFAULT_GRID = "http://10.0.10.221:4444";
const STORAGE_KEY = "fgt-settings";

interface Settings {
  selenium: boolean;
  gridUrl: string;
}

function load(): Settings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return { ...{ selenium: false, gridUrl: DEFAULT_GRID }, ...JSON.parse(raw) };
  } catch {}
  return { selenium: false, gridUrl: DEFAULT_GRID };
}

const SettingsContext = createContext<{
  settings: Settings;
  setSettings: (s: Partial<Settings>) => void;
}>({ settings: load(), setSettings: () => {} });

export function SettingsProvider({ children }: { children: React.ReactNode }) {
  const [settings, setSettingsState] = useState<Settings>(load);

  function setSettings(patch: Partial<Settings>) {
    setSettingsState((prev) => {
      const next = { ...prev, ...patch };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      return next;
    });
  }

  return (
    <SettingsContext.Provider value={{ settings, setSettings }}>
      {children}
    </SettingsContext.Provider>
  );
}

export const useSettings = () => useContext(SettingsContext);
