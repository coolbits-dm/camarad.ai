import { useEffect, useState } from 'react';

export interface User {
  id: string;
  email: string;
  displayName: string;
  avatar: string;
  role: 'user' | 'admin' | 'dev' | 'beta-tester';
  lastLogin: string;
  activeSession: boolean;
  createdAt: string;
}

export interface UserPreferences {
  theme: 'light' | 'dark' | 'auto';
  accentColor: string;
  personalityTone: 'neutral' | 'technical' | 'conversational';
  timezone: string;
  locale: string;
  notifications: {
    systemUpdates: boolean;
    billingNotifications: boolean;
    aiActivitySummaries: boolean;
    emailPreferences: string[];
  };
}

interface UseUserReturn {
  user: User | null;
  preferences: UserPreferences | null;
  isLoading: boolean;
  error: string | null;
  updateProfile: (data: Partial<User>) => Promise<void>;
  updatePreferences: (data: Partial<UserPreferences>) => Promise<void>;
  refreshUser: () => Promise<void>;
}

const API_BASE = '/api';

export function useUser(): UseUserReturn {
  const [user, setUser] = useState<User | null>(null);
  const [preferences, setPreferences] = useState<UserPreferences | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchUser = async () => {
    try {
      const res = await fetch(`${API_BASE}/user`);
      if (!res.ok) throw new Error('Failed to fetch user');
      const data = await res.json();
      setUser(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    }
  };

  const fetchPreferences = async () => {
    try {
      const res = await fetch(`${API_BASE}/user/preferences`);
      if (!res.ok) throw new Error('Failed to fetch preferences');
      const data = await res.json();
      setPreferences(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    }
  };

  const refreshUser = async () => {
    setIsLoading(true);
    setError(null);
    await Promise.all([fetchUser(), fetchPreferences()]);
    setIsLoading(false);
  };

  const updateProfile = async (data: Partial<User>) => {
    try {
      const res = await fetch(`${API_BASE}/user`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      if (!res.ok) throw new Error('Failed to update profile');
      const result = await res.json();
      const updated = result.user || result; // Handle {user: ...} or direct user object
      setUser(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      throw err;
    }
  };

  const updatePreferences = async (data: Partial<UserPreferences>) => {
    try {
      const res = await fetch(`${API_BASE}/user/preferences`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      if (!res.ok) throw new Error('Failed to update preferences');
      const result = await res.json();
      const updated = result.preferences || result; // Handle {preferences: ...} or direct preferences
      setPreferences(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      throw err;
    }
  };

  useEffect(() => {
    refreshUser();
  }, []);

  return {
    user,
    preferences,
    isLoading,
    error,
    updateProfile,
    updatePreferences,
    refreshUser,
  };
}
