import { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import { Moon, Sun, Palette, Clock } from 'lucide-react';
import { isAuthenticated } from '@/lib/auth/session';

const themes = [
  { id: 'dark', name: 'Dark', icon: Moon },
  { id: 'light', name: 'Light', icon: Sun },
];

const accents = [
  { id: 'violet', name: 'Violet', color: 'bg-violet-500' },
  { id: 'blue', name: 'Blue', color: 'bg-blue-500' },
  { id: 'cyan', name: 'Cyan', color: 'bg-cyan-500' },
  { id: 'green', name: 'Green', color: 'bg-green-500' },
  { id: 'orange', name: 'Orange', color: 'bg-orange-500' },
  { id: 'red', name: 'Red', color: 'bg-red-500' },
];

const timezones = [
  'UTC',
  'America/New_York',
  'America/Chicago',
  'America/Los_Angeles',
  'Europe/London',
  'Europe/Paris',
  'Europe/Bucharest',
  'Asia/Tokyo',
  'Asia/Dubai',
  'Australia/Sydney',
];

export default function OnboardingPreferencesPage() {
  const router = useRouter();
  const [mounted, setMounted] = useState(false);
  const [theme, setTheme] = useState('dark');
  const [accent, setAccent] = useState('violet');
  const [timezone, setTimezone] = useState('UTC');

  useEffect(() => {
    setMounted(true);
    if (!isAuthenticated()) {
      router.replace('/login');
    }

    // Detect user timezone
    const userTz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    if (timezones.includes(userTz)) {
      setTimezone(userTz);
    }
  }, [router]);

  if (!mounted || !isAuthenticated()) return null;

  const handleContinue = () => {
    localStorage.setItem('onboarding_preferences', JSON.stringify({
      theme,
      accent,
      timezone,
    }));
    router.push('/onboarding/complete');
  };

  const handleBack = () => {
    router.back();
  };

  return (
    <div className="min-h-screen bg-background text-foreground px-6 py-12">
      <div className="max-w-2xl mx-auto">
        {/* Progress */}
        <div className="flex items-center justify-center gap-2 mb-12">
          <div className="w-2 h-2 rounded-full bg-accent"></div>
          <div className="w-2 h-2 rounded-full bg-accent"></div>
          <div className="w-2 h-2 rounded-full bg-accent"></div>
          <div className="w-2 h-2 rounded-full bg-muted"></div>
        </div>

        {/* Title */}
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold mb-3">Customize your workspace</h1>
          <p className="text-muted-foreground text-lg">
            Set your preferences
          </p>
        </div>

        <div className="space-y-8">
          {/* Theme */}
          <div>
            <div className="flex items-center gap-2 mb-4">
              <Moon className="w-5 h-5 text-muted-foreground" />
              <h3 className="text-lg font-semibold">Theme</h3>
            </div>
            <div className="grid grid-cols-2 gap-3">
              {themes.map((t) => {
                const Icon = t.icon;
                return (
                  <button
                    key={t.id}
                    onClick={() => setTheme(t.id)}
                    className={`rounded-xl border-2 p-4 flex items-center gap-3 transition-all ${
                      theme === t.id
                        ? 'border-accent bg-accent/5'
                        : 'border-border bg-surface/40 hover:border-border/60'
                    }`}
                  >
                    <Icon className="w-5 h-5" />
                    <span className="font-medium">{t.name}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Accent Color */}
          <div>
            <div className="flex items-center gap-2 mb-4">
              <Palette className="w-5 h-5 text-muted-foreground" />
              <h3 className="text-lg font-semibold">Accent color</h3>
            </div>
            <div className="grid grid-cols-3 sm:grid-cols-6 gap-3">
              {accents.map((a) => (
                <button
                  key={a.id}
                  onClick={() => setAccent(a.id)}
                  className={`rounded-xl border-2 p-3 flex flex-col items-center gap-2 transition-all ${
                    accent === a.id
                      ? 'border-accent'
                      : 'border-border hover:border-border/60'
                  }`}
                >
                  <div className={`w-8 h-8 rounded-lg ${a.color}`}></div>
                  <span className="text-xs font-medium">{a.name}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Timezone */}
          <div>
            <div className="flex items-center gap-2 mb-4">
              <Clock className="w-5 h-5 text-muted-foreground" />
              <h3 className="text-lg font-semibold">Timezone</h3>
            </div>
            <select
              value={timezone}
              onChange={(e) => setTimezone(e.target.value)}
              className="w-full rounded-lg border border-border bg-background px-4 py-3 text-foreground focus:outline-none focus:ring-2 focus:ring-accent"
            >
              {timezones.map((tz) => (
                <option key={tz} value={tz}>
                  {tz}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center justify-center gap-4 mt-12">
          <button
            onClick={handleBack}
            className="rounded-lg border border-border px-8 py-3 font-semibold hover:bg-surface/60 transition-colors"
          >
            Back
          </button>
          <button
            onClick={handleContinue}
            className="rounded-lg bg-accent px-8 py-3 font-semibold text-white hover:bg-accent/90 transition-colors"
          >
            Continue
          </button>
        </div>
      </div>
    </div>
  );
}
