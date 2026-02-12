import { ThemeProvider } from 'next-themes';
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import { ACCENT_OPTIONS, ACCENT_STORAGE_KEY, DEFAULT_ACCENT, type AccentId } from '@/lib/theme';
import { readJSON, writeJSON } from '@/lib/storage';

interface AccentContextValue {
  accent: AccentId;
  setAccent: (accent: AccentId) => void;
  options: typeof ACCENT_OPTIONS;
}

const AccentContext = createContext<AccentContextValue | undefined>(undefined);

const isBrowser = typeof window !== 'undefined';

export function AppearanceProvider({ children }: { children: React.ReactNode }) {
  const [accent, setAccentState] = useState<AccentId>(() => {
    if (!isBrowser) {
      return DEFAULT_ACCENT;
    }
    return readJSON<AccentId>(ACCENT_STORAGE_KEY, DEFAULT_ACCENT);
  });

  useEffect(() => {
    if (!isBrowser) return;
    writeJSON(ACCENT_STORAGE_KEY, accent);
    document.documentElement.dataset.accent = accent;
  }, [accent]);

  const setAccent = useCallback((next: AccentId) => {
    setAccentState(next);
  }, []);

  const value = useMemo(
    () => ({
      accent,
      setAccent,
      options: ACCENT_OPTIONS,
    }),
    [accent, setAccent],
  );

  return (
    <ThemeProvider attribute="class" defaultTheme="dark" enableSystem={false}>
      <AccentContext.Provider value={value}>{children}</AccentContext.Provider>
    </ThemeProvider>
  );
}

export function useAccent() {
  const context = useContext(AccentContext);
  if (!context) {
    throw new Error('useAccent must be used within AppearanceProvider');
  }
  return context;
}
