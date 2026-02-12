import * as Dialog from '@radix-ui/react-dialog';
import * as SwitchPrimitive from '@radix-ui/react-switch';
import { Bell, Check, Globe, Loader2, MoonStar, Palette, SunMedium, X } from 'lucide-react';
import { useTheme } from 'next-themes';
import { useState, useEffect, type CSSProperties } from 'react';
import { useAccent } from '@/components/providers';
import { ACCENT_OPTIONS } from '@/lib/theme';
import type { UserPreferences } from '@/lib/hooks/useUser';

interface UserSettingsModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  preferences: UserPreferences | null;
  onSave: (prefs: Partial<UserPreferences>) => Promise<void>;
}

type TabId = 'appearance' | 'notifications' | 'region';

export function UserSettingsModal({ open, onOpenChange, preferences, onSave }: UserSettingsModalProps) {
  const [activeTab, setActiveTab] = useState<TabId>('appearance');
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const { setTheme, resolvedTheme } = useTheme();
  const { accent, setAccent } = useAccent();
  
  const [localPrefs, setLocalPrefs] = useState<Partial<UserPreferences>>({});

  useEffect(() => {
    if (preferences) {
      setLocalPrefs({
        theme: preferences.theme,
        accentColor: preferences.accentColor,
        notifications: preferences.notifications,
        timezone: preferences.timezone,
        locale: preferences.locale
      });
    }
  }, [preferences]);

  const handleSave = async () => {
    setIsSaving(true);
    setSaveSuccess(false);
    try {
      await onSave(localPrefs);
      setSaveSuccess(true);
      setTimeout(() => {
        setSaveSuccess(false);
        onOpenChange(false);
      }, 1500);
    } catch (error) {
      console.error('Failed to save preferences:', error);
    } finally {
      setIsSaving(false);
    }
  };

  const tabs = [
    { id: 'appearance' as const, label: 'Appearance', icon: Palette },
    { id: 'notifications' as const, label: 'Notifications', icon: Bell },
    { id: 'region' as const, label: 'Region', icon: Globe }
  ];

  if (!preferences) return null;

  const isDark = resolvedTheme === 'dark';

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
        <Dialog.Content className="fixed left-[50%] top-[50%] z-50 w-full max-w-2xl translate-x-[-50%] translate-y-[-50%] rounded-2xl border border-border bg-background shadow-2xl duration-200 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[state=closed]:slide-out-to-left-1/2 data-[state=closed]:slide-out-to-top-[48%] data-[state=open]:slide-in-from-left-1/2 data-[state=open]:slide-in-from-top-[48%]">
          <div className="flex items-center justify-between border-b border-border px-6 py-4">
            <Dialog.Title className="text-lg font-semibold text-foreground">
              Settings
            </Dialog.Title>
            <Dialog.Close className="rounded-lg p-1.5 text-muted-foreground transition hover:bg-surface-muted/80 hover:text-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2">
              <X className="h-4 w-4" />
              <span className="sr-only">Close</span>
            </Dialog.Close>
          </div>

          <div className="flex">
            {/* Tabs Sidebar */}
            <div className="w-48 border-r border-border p-4">
              <nav className="space-y-1">
                {tabs.map((tab) => {
                  const Icon = tab.icon;
                  const isActive = activeTab === tab.id;
                  return (
                    <button
                      key={tab.id}
                      type="button"
                      onClick={() => setActiveTab(tab.id)}
                      className={`flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 ${
                        isActive
                          ? 'bg-accent/10 text-accent'
                          : 'text-muted-foreground hover:bg-surface-muted/80 hover:text-foreground'
                      }`}
                    >
                      <Icon className="h-4 w-4" />
                      {tab.label}
                    </button>
                  );
                })}
              </nav>
            </div>

            {/* Content Area */}
            <div className="flex-1 p-6">
              {activeTab === 'appearance' && (
                <div className="space-y-6">
                  <div>
                    <h3 className="text-sm font-semibold text-foreground mb-1">Theme</h3>
                    <p className="text-xs text-muted-foreground mb-3">Choose your interface theme</p>
                    <div className="flex items-center justify-between rounded-lg border border-border bg-surface/40 p-4">
                      <div className="flex items-center gap-3">
                        {isDark ? (
                          <MoonStar className="h-5 w-5 text-foreground" />
                        ) : (
                          <SunMedium className="h-5 w-5 text-foreground" />
                        )}
                        <span className="text-sm font-medium text-foreground">
                          {isDark ? 'Dark mode' : 'Light mode'}
                        </span>
                      </div>
                      <SwitchPrimitive.Root
                        className="relative inline-flex h-7 w-12 shrink-0 cursor-pointer items-center rounded-full bg-muted transition-colors data-[state=checked]:bg-accent/20 shadow-sm"
                        checked={isDark}
                        onCheckedChange={(checked) => {
                          const theme = checked ? 'dark' : 'light';
                          setTheme(theme);
                          setLocalPrefs({ ...localPrefs, theme });
                        }}
                        aria-label="Toggle dark mode"
                      >
                        <SwitchPrimitive.Thumb className="pointer-events-none inline-flex h-5 w-5 translate-x-1 items-center justify-center rounded-full bg-background text-foreground shadow transition-transform data-[state=checked]:translate-x-[26px]">
                          {isDark ? <MoonStar className="h-3 w-3" /> : <SunMedium className="h-3 w-3" />}
                        </SwitchPrimitive.Thumb>
                      </SwitchPrimitive.Root>
                    </div>
                  </div>

                  <div>
                    <h3 className="text-sm font-semibold text-foreground mb-1">Accent color</h3>
                    <p className="text-xs text-muted-foreground mb-3">Customize your accent color</p>
                    <div className="flex flex-wrap gap-2">
                      {ACCENT_OPTIONS.map((option) => {
                        const isActive = accent === option.id;
                        return (
                          <button
                            key={option.id}
                            type="button"
                            onClick={() => {
                              setAccent(option.id);
                              setLocalPrefs({ ...localPrefs, accentColor: option.id });
                              // Apply CSS variable immediately
                              document.documentElement.style.setProperty('--accent-rgb', option.rgb);
                            }}
                            className="group relative inline-flex flex-col items-center gap-1.5 rounded-lg border border-border bg-surface/40 p-3 transition hover:bg-surface-muted/80 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
                            aria-pressed={isActive}
                            aria-label={`Use ${option.label} accent`}
                          >
                            <span
                              className="h-8 w-8 rounded-full shadow-lg transition-all group-hover:scale-105"
                              style={{
                                backgroundColor: `rgb(${option.rgb})`
                              }}
                            />
                            <span className="text-xs font-medium text-muted-foreground">{option.label}</span>
                            {isActive && (
                              <Check className="absolute -right-1 -top-1 h-4 w-4 rounded-full bg-accent text-white p-0.5" />
                            )}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                </div>
              )}

              {activeTab === 'notifications' && (
                <div className="space-y-4">
                  <div>
                    <h3 className="text-sm font-semibold text-foreground mb-1">Notification preferences</h3>
                    <p className="text-xs text-muted-foreground mb-4">Manage how you receive notifications</p>
                  </div>
                  <div className="space-y-3">
                    {(Object.entries(preferences.notifications || {}) as [string, boolean][]).map(([key, value]) => (
                      <div key={key} className="flex items-center justify-between rounded-lg border border-border bg-surface/40 p-4">
                        <span className="text-sm font-medium text-foreground capitalize">
                          {key.replace(/([A-Z])/g, ' $1').trim()}
                        </span>
                        <SwitchPrimitive.Root
                          className="relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full bg-muted transition-colors data-[state=checked]:bg-accent/20 shadow-sm"
                          checked={value}
                          onCheckedChange={(checked) => {
                            setLocalPrefs({
                              ...localPrefs,
                              notifications: {
                                ...(localPrefs.notifications || preferences.notifications),
                                [key]: checked
                              }
                            });
                          }}
                        >
                          <SwitchPrimitive.Thumb className="pointer-events-none h-4 w-4 translate-x-1 rounded-full bg-background shadow transition-transform data-[state=checked]:translate-x-[22px]" />
                        </SwitchPrimitive.Root>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {activeTab === 'region' && (
                <div className="space-y-4">
                  <div>
                    <h3 className="text-sm font-semibold text-foreground mb-1">Region & Language</h3>
                    <p className="text-xs text-muted-foreground mb-4">Configure your regional settings</p>
                  </div>
                  <div className="space-y-4">
                    <div>
                      <label className="text-sm font-medium text-foreground mb-2 block">Timezone</label>
                      <input
                        type="text"
                        value={localPrefs.timezone || preferences.timezone}
                        onChange={(e) => setLocalPrefs({ ...localPrefs, timezone: e.target.value })}
                        className="w-full rounded-lg border border-border bg-surface/40 px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-accent"
                      />
                    </div>
                    <div>
                      <label className="text-sm font-medium text-foreground mb-2 block">Locale</label>
                      <input
                        type="text"
                        value={localPrefs.locale || preferences.locale}
                        onChange={(e) => setLocalPrefs({ ...localPrefs, locale: e.target.value })}
                        className="w-full rounded-lg border border-border bg-surface/40 px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-accent"
                      />
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Footer Actions */}
          <div className="flex items-center justify-between border-t border-border px-6 py-4">
            <div className="flex items-center gap-2">
              {saveSuccess && (
                <span className="flex items-center gap-1.5 text-sm font-medium text-emerald-500">
                  <Check className="h-4 w-4" />
                  Settings saved
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => onOpenChange(false)}
                className="rounded-lg px-4 py-2 text-sm font-medium text-muted-foreground transition hover:bg-surface-muted/80 hover:text-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
                disabled={isSaving}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleSave}
                disabled={isSaving}
                className="flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition hover:bg-accent/90 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isSaving && <Loader2 className="h-4 w-4 animate-spin" />}
                Save changes
              </button>
            </div>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
