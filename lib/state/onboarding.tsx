import { createContext, useContext, useState, useEffect } from 'react';
import type { ReactNode } from 'react';
import type { PlanId } from '@/lib/types/billing';
import type { WorkspaceType } from '@/lib/types/workspace';

interface OnboardingWorkspace {
  name: string;
  type: WorkspaceType;
}

interface OnboardingPreferences {
  theme: 'light' | 'dark' | 'system';
  accent: string;
  timezone: string;
}

interface OnboardingState {
  planId: PlanId | null;
  workspace: OnboardingWorkspace | null;
  selectedAgentPresetIds: string[];
  preferences: OnboardingPreferences | null;
}

interface OnboardingContextValue extends OnboardingState {
  setPlanId: (planId: PlanId) => void;
  setWorkspace: (workspace: OnboardingWorkspace) => void;
  setSelectedAgentPresetIds: (ids: string[]) => void;
  setPreferences: (preferences: OnboardingPreferences) => void;
  resetOnboarding: () => void;
}

const OnboardingContext = createContext<OnboardingContextValue | undefined>(undefined);

const STORAGE_KEY = 'camarad_onboarding';

function loadFromStorage(): OnboardingState {
  if (typeof window === 'undefined') {
    return {
      planId: null,
      workspace: null,
      selectedAgentPresetIds: [],
      preferences: null,
    };
  }

  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      return JSON.parse(stored);
    }
  } catch (e) {
    console.error('Failed to load onboarding state:', e);
  }

  return {
    planId: null,
    workspace: null,
    selectedAgentPresetIds: [],
    preferences: null,
  };
}

function saveToStorage(state: OnboardingState): void {
  if (typeof window === 'undefined') return;

  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch (e) {
    console.error('Failed to save onboarding state:', e);
  }
}

export function OnboardingProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<OnboardingState>(loadFromStorage);

  useEffect(() => {
    saveToStorage(state);
  }, [state]);

  const setPlanId = (planId: PlanId) => {
    setState((prev) => ({ ...prev, planId }));
  };

  const setWorkspace = (workspace: OnboardingWorkspace) => {
    setState((prev) => ({ ...prev, workspace }));
  };

  const setSelectedAgentPresetIds = (ids: string[]) => {
    setState((prev) => ({ ...prev, selectedAgentPresetIds: ids }));
  };

  const setPreferences = (preferences: OnboardingPreferences) => {
    setState((prev) => ({ ...prev, preferences }));
  };

  const resetOnboarding = () => {
    const initialState = {
      planId: null,
      workspace: null,
      selectedAgentPresetIds: [],
      preferences: null,
    };
    setState(initialState);
    if (typeof window !== 'undefined') {
      localStorage.removeItem(STORAGE_KEY);
    }
  };

  return (
    <OnboardingContext.Provider
      value={{
        ...state,
        setPlanId,
        setWorkspace,
        setSelectedAgentPresetIds,
        setPreferences,
        resetOnboarding,
      }}
    >
      {children}
    </OnboardingContext.Provider>
  );
}

export function useOnboarding() {
  const context = useContext(OnboardingContext);
  if (!context) {
    throw new Error('useOnboarding must be used within OnboardingProvider');
  }
  return context;
}
