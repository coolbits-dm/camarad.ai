import * as SwitchPrimitive from '@radix-ui/react-switch';
import { MoonStar, SunMedium } from 'lucide-react';
import { useTheme } from 'next-themes';
import { type CSSProperties, useEffect, useState } from 'react';

import { useAccent } from '@/components/providers';

function useIsMounted() {
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
  }, []);
  return mounted;
}

interface ThemeAccentToggleProps {
  collapsed?: boolean;
}

export function ThemeAccentToggle({ collapsed = false }: ThemeAccentToggleProps) {
  const mounted = useIsMounted();
  const { setTheme, resolvedTheme } = useTheme();
  const { accent, options, setAccent } = useAccent();

  if (!mounted) {
    return (
      <div className="flex flex-col gap-3 rounded-xl bg-surface/40 p-2 shadow-lg">
        {!collapsed && (
          <>
            <div className="flex items-center justify-between gap-2 text-sm text-muted-foreground">
              <span>Theme</span>
              <div className="h-7 w-12 rounded-full bg-muted/60" />
            </div>
            <div className="flex items-center justify-between gap-2 text-sm text-muted-foreground">
              <span>Accent</span>
              <div className="flex gap-1">
                {options.map((option) => (
                  <div key={option.id} className="h-4 w-4 rounded-full bg-muted/60" />
                ))}
              </div>
            </div>
          </>
        )}
        {collapsed && <div className="h-7 w-12 rounded-full bg-muted/60 mx-auto" />}
      </div>
    );
  }

  const isDark = resolvedTheme === 'dark';

  if (collapsed) {
    return (
      <div className="flex flex-col gap-2 rounded-xl bg-surface/40 p-2 shadow-lg">
        <div className="flex items-center justify-center">
          <SwitchPrimitive.Root
            className="relative inline-flex h-7 w-12 shrink-0 cursor-pointer items-center rounded-full bg-muted transition-colors data-[state=checked]:bg-foreground/10 shadow-lg"
            checked={isDark}
            onCheckedChange={(checked) => setTheme(checked ? 'dark' : 'light')}
            aria-label="Toggle dark mode"
          >
            <SwitchPrimitive.Thumb className="pointer-events-none inline-flex h-5 w-5 translate-x-1 items-center justify-center rounded-full bg-background text-foreground shadow transition-transform data-[state=checked]:translate-x-[26px]">
              {isDark ? <MoonStar className="h-3 w-3" aria-hidden /> : <SunMedium className="h-3 w-3" aria-hidden />}
            </SwitchPrimitive.Thumb>
          </SwitchPrimitive.Root>
        </div>
        <div className="flex flex-wrap justify-center gap-1.5">
          {options.map((option) => {
            const isActive = accent === option.id;
            return (
              <button
                key={option.id}
                type="button"
                onClick={() => setAccent(option.id)}
                className="group relative inline-flex h-6 w-6 items-center justify-center rounded-full transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
                style={{ color: `rgb(${option.rgb})` }}
                aria-pressed={isActive}
                aria-label={`Use ${option.label} accent`}
              >
                <span
                  className="h-6 w-6 rounded-full bg-[rgb(var(--accent-color))] shadow-lg transition-all group-hover:scale-105 group-focus-visible:scale-105"
                  style={
                    {
                      '--accent-color': option.rgb,
                    } as CSSProperties
                  }
                />
                {isActive && (
                  <span className="absolute inset-0 rounded-full ring-2 ring-[rgb(var(--accent-color))] shadow-[0_0_8px_rgba(var(--accent-color),0.4)] transition-all" />
                )}
              </button>
            );
          })}
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3 rounded-xl bg-surface/40 p-2 shadow-lg">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 text-[11px] font-medium text-muted-foreground">
          <SunMedium className="h-3.5 w-3.5" aria-hidden />
          <span>Theme</span>
        </div>
        <SwitchPrimitive.Root
          className="relative inline-flex h-7 w-14 shrink-0 cursor-pointer items-center rounded-full bg-muted transition-colors data-[state=checked]:bg-foreground/10 shadow-lg"
          checked={isDark}
          onCheckedChange={(checked) => setTheme(checked ? 'dark' : 'light')}
          aria-label="Toggle dark mode"
        >
          <SwitchPrimitive.Thumb className="pointer-events-none inline-flex h-5 w-5 translate-x-1.5 items-center justify-center rounded-full bg-background text-foreground shadow transition-transform data-[state=checked]:translate-x-[30px]">
            {isDark ? <MoonStar className="h-3 w-3" aria-hidden /> : <SunMedium className="h-3 w-3" aria-hidden />}
          </SwitchPrimitive.Thumb>
        </SwitchPrimitive.Root>
      </div>

      <div>
        <div className="flex items-center gap-1.5 text-[11px] font-medium text-muted-foreground mb-2">
          <span>Accent</span>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {options.map((option) => {
            const isActive = accent === option.id;
            return (
              <button
                key={option.id}
                type="button"
                onClick={() => setAccent(option.id)}
                className="group relative inline-flex h-7 w-7 items-center justify-center rounded-full transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
                style={{ color: `rgb(${option.rgb})` }}
                aria-pressed={isActive}
                aria-label={`Use ${option.label} accent`}
              >
                <span
                  className="h-7 w-7 rounded-full bg-[rgb(var(--accent-color))] shadow-lg transition-all group-hover:scale-105 group-focus-visible:scale-105"
                  style={
                    {
                      '--accent-color': option.rgb,
                    } as CSSProperties
                  }
                />
                {isActive && (
                  <span className="absolute inset-0 rounded-full ring-2 ring-[rgb(var(--accent-color))] shadow-[0_0_8px_rgba(var(--accent-color),0.4)] transition-all" />
                )}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
