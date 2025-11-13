import { useState } from 'react';
import { useUser } from '@/lib/hooks/useUser';
import { User2, Settings, CreditCard, Activity, Shield, Bell, Palette, Globe, Trash2 } from 'lucide-react';

export default function UserPanel() {
  const { user, preferences, isLoading, updateProfile, updatePreferences } = useUser();
  const [activeTab, setActiveTab] = useState<'overview' | 'preferences' | 'security' | 'billing' | 'usage'>('overview');

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-muted">Loading...</div>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-muted">Failed to load user data</div>
      </div>
    );
  }

  const tabs = [
    { id: 'overview', label: 'Overview', icon: User2 },
    { id: 'preferences', label: 'Preferences', icon: Settings },
    { id: 'security', label: 'Security', icon: Shield },
    { id: 'billing', label: 'Billing', icon: CreditCard },
    { id: 'usage', label: 'Usage', icon: Activity },
  ] as const;

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="border-b border-border/40 bg-surface/50 px-6 py-4">
        <h1 className="text-2xl font-bold">Account Settings</h1>
        <p className="mt-1 text-sm text-muted">{user.email}</p>
      </div>

      {/* Tabs */}
      <div className="border-b border-border/40 bg-background px-6">
        <div className="flex gap-6">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const active = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 border-b-2 px-1 py-3 text-sm font-medium transition-colors ${
                  active
                    ? 'border-accent text-accent'
                    : 'border-transparent text-muted hover:text-foreground'
                }`}
              >
                <Icon className="h-4 w-4" />
                {tab.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {activeTab === 'overview' && <OverviewSection user={user} />}
        {activeTab === 'preferences' && <PreferencesSection preferences={preferences} updatePreferences={updatePreferences} />}
        {activeTab === 'security' && <SecuritySection />}
        {activeTab === 'billing' && <BillingSection />}
        {activeTab === 'usage' && <UsageSection />}
      </div>
    </div>
  );
}

// Overview Section
function OverviewSection({ user }: { user: any }) {
  return (
    <div className="max-w-2xl space-y-6">
      <div className="rounded-lg border border-border/40 bg-surface/30 p-6 shadow-lg">
        <h2 className="mb-4 text-lg font-semibold">Profile</h2>
        <div className="flex items-start gap-4">
          <div className="h-20 w-20 rounded-full bg-accent/10 flex items-center justify-center">
            <User2 className="h-10 w-10 text-accent" />
          </div>
          <div className="flex-1 space-y-3">
            <div>
              <label className="text-xs text-muted">Display Name</label>
              <div className="text-base font-medium">{user.displayName}</div>
            </div>
            <div>
              <label className="text-xs text-muted">Email</label>
              <div className="text-sm">{user.email}</div>
            </div>
            <div className="flex gap-4">
              <div>
                <label className="text-xs text-muted">Role</label>
                <div className="inline-block rounded bg-accent/10 px-2 py-0.5 text-xs font-medium text-accent">
                  {user.role}
                </div>
              </div>
              <div>
                <label className="text-xs text-muted">Last Login</label>
                <div className="text-xs">{new Date(user.lastLogin).toLocaleString()}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// Preferences Section
function PreferencesSection({ preferences, updatePreferences }: { preferences: any; updatePreferences: any }) {
  if (!preferences) return <div>Loading preferences...</div>;

  const handleThemeChange = async (theme: string) => {
    await updatePreferences({ theme });
  };

  const handleAccentChange = async (color: string) => {
    await updatePreferences({ accentColor: color });
  };

  const colors = ['cyan', 'blue', 'purple', 'green', 'orange', 'red'];

  return (
    <div className="max-w-2xl space-y-6">
      {/* Theme */}
      <div className="rounded-lg border border-border/40 bg-surface/30 p-6 shadow-lg">
        <div className="mb-4 flex items-center gap-2">
          <Palette className="h-5 w-5 text-accent" />
          <h2 className="text-lg font-semibold">Appearance</h2>
        </div>
        <div className="space-y-4">
          <div>
            <label className="mb-2 block text-sm font-medium">Theme</label>
            <div className="flex gap-2">
              {['light', 'dark', 'auto'].map((theme) => (
                <button
                  key={theme}
                  onClick={() => handleThemeChange(theme)}
                  className={`rounded-lg border px-4 py-2 text-sm font-medium transition-colors ${
                    preferences.theme === theme
                      ? 'border-accent bg-accent/10 text-accent'
                      : 'border-border/40 hover:border-accent/50'
                  }`}
                >
                  {theme.charAt(0).toUpperCase() + theme.slice(1)}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium">Accent Color</label>
            <div className="flex gap-2">
              {colors.map((color) => (
                <button
                  key={color}
                  onClick={() => handleAccentChange(color)}
                  className={`h-10 w-10 rounded-lg border-2 transition-all ${
                    preferences.accentColor === color
                      ? 'border-white scale-110 shadow-lg'
                      : 'border-transparent hover:scale-105'
                  }`}
                  style={{ backgroundColor: `var(--${color})` }}
                  title={color}
                />
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Notifications */}
      <div className="rounded-lg border border-border/40 bg-surface/30 p-6 shadow-lg">
        <div className="mb-4 flex items-center gap-2">
          <Bell className="h-5 w-5 text-accent" />
          <h2 className="text-lg font-semibold">Notifications</h2>
        </div>
        <div className="space-y-3">
          {Object.entries(preferences.notifications || {}).map(([key, value]) => (
            <label key={key} className="flex items-center justify-between">
              <span className="text-sm">{key.replace(/([A-Z])/g, ' $1').trim()}</span>
              <input
                type="checkbox"
                checked={!!value}
                onChange={(e) => {
                  updatePreferences({
                    notifications: { ...preferences.notifications, [key]: e.target.checked },
                  });
                }}
                className="h-4 w-4 rounded border-border/40 bg-surface text-accent focus:ring-accent"
              />
            </label>
          ))}
        </div>
      </div>

      {/* Locale */}
      <div className="rounded-lg border border-border/40 bg-surface/30 p-6 shadow-lg">
        <div className="mb-4 flex items-center gap-2">
          <Globe className="h-5 w-5 text-accent" />
          <h2 className="text-lg font-semibold">Region</h2>
        </div>
        <div className="space-y-3">
          <div>
            <label className="mb-1 block text-sm font-medium">Timezone</label>
            <div className="text-sm text-muted">{preferences.timezone}</div>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">Locale</label>
            <div className="text-sm text-muted">{preferences.locale}</div>
          </div>
        </div>
      </div>
    </div>
  );
}

// Security Section (placeholder)
function SecuritySection() {
  return (
    <div className="max-w-2xl space-y-6">
      <div className="rounded-lg border border-border/40 bg-surface/30 p-6 shadow-lg">
        <div className="mb-4 flex items-center gap-2">
          <Shield className="h-5 w-5 text-accent" />
          <h2 className="text-lg font-semibold">Security Settings</h2>
        </div>
        <p className="text-sm text-muted">API keys, sessions, and 2FA management coming soon...</p>
      </div>
    </div>
  );
}

// Billing Section (placeholder)
function BillingSection() {
  return (
    <div className="max-w-2xl space-y-6">
      <div className="rounded-lg border border-border/40 bg-surface/30 p-6 shadow-lg">
        <div className="mb-4 flex items-center gap-2">
          <CreditCard className="h-5 w-5 text-accent" />
          <h2 className="text-lg font-semibold">Billing & Plans</h2>
        </div>
        <p className="text-sm text-muted">Subscription management and invoices coming soon...</p>
      </div>
    </div>
  );
}

// Usage Section (placeholder)
function UsageSection() {
  return (
    <div className="max-w-2xl space-y-6">
      <div className="rounded-lg border border-border/40 bg-surface/30 p-6 shadow-lg">
        <div className="mb-4 flex items-center gap-2">
          <Activity className="h-5 w-5 text-accent" />
          <h2 className="text-lg font-semibold">Usage & Tokens</h2>
        </div>
        <p className="text-sm text-muted">cbT tracking and analytics coming soon...</p>
      </div>
    </div>
  );
}
