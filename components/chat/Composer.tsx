import { useTheme } from 'next-themes';
import { type ChangeEvent, type KeyboardEvent, useCallback, useEffect, useRef, useState } from 'react';
import { ArrowUp, LucidePlus, Mic } from 'lucide-react';
import clsx from 'clsx';

import { CouncilPicker } from '@/components/council/CouncilPicker';
import type { PanelKey } from '@/lib/panels';
import type { CouncilMember } from '@/types/chat';

interface ComposerProps {
  panel: PanelKey;
  disabled?: boolean;
  busy?: boolean;
  onSend: (content: string, options?: { targets?: CouncilMember[] }) => Promise<void> | void;
}

export function Composer({ panel, disabled = false, busy = false, onSend }: ComposerProps) {
  const [value, setValue] = useState('');
  const [pickerOpen, setPickerOpen] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const { resolvedTheme } = useTheme();

  const resetHeight = useCallback(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = 'auto';
    textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
  }, []);

  useEffect(() => {
    resetHeight();
  }, [value, resetHeight]);

  const handleChange = (event: ChangeEvent<HTMLTextAreaElement>) => {
    setValue(event.target.value);
  };

  const performSend = async (targets?: CouncilMember[]) => {
    if (busy || disabled) return;
    const trimmed = value.trim();
    if (trimmed.length === 0) return;
    await onSend(trimmed, targets ? { targets } : undefined);
    setValue('');
  };

  const handleKeyDown = async (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      await performSend();
    }
  };

  const paletteGradient =
    resolvedTheme === 'dark'
      ? 'from-accent/20 via-accent/10 to-transparent'
      : 'from-accent/15 via-accent/5 to-transparent';

  return (
    <div className="relative">
      <CouncilPicker
        panel={panel}
        open={pickerOpen}
        onOpenChange={setPickerOpen}
        onConfirm={(members) => performSend(members)}
      />
      <div className="pointer-events-none absolute inset-0 rounded-3xl bg-gradient-to-br opacity-40 blur-xl" aria-hidden />
      <div className={clsx('relative rounded-3xl bg-surface-muted p-2.5 shadow-xl')}>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setPickerOpen(true)}
            disabled={disabled || busy}
            className="group flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-surface-muted/80 text-muted-foreground transition hover:text-accent focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 shadow-lg"
            aria-label="Open council actions"
          >
            <LucidePlus className="h-4 w-4 transition-transform group-hover:rotate-90" aria-hidden />
          </button>
          <textarea
            ref={textareaRef}
            value={value}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            placeholder="Enter to send · Shift+Enter for new line · + opens actions"
            rows={1}
            disabled={disabled || busy}
            className="max-h-[200px] flex-1 resize-none bg-transparent text-sm text-foreground placeholder:text-muted-foreground/40 focus:outline-none py-2"
          />
          <div className="flex shrink-0 items-center gap-2">
            <div className="relative inline-flex h-10 w-10 items-center justify-center">
              <span className="absolute h-9 w-9 rounded-full bg-accent/10" aria-hidden />
              <span className="mic-pulse absolute h-9 w-9 rounded-full" aria-hidden />
              <span className="relative flex h-9 w-9 items-center justify-center rounded-full bg-accent text-accent-foreground shadow-lg">
                <Mic className="h-3.5 w-3.5" aria-hidden />
              </span>
            </div>
            <button
              type="button"
              onClick={() => performSend()}
              disabled={disabled || busy || value.trim().length === 0}
              className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent text-accent-foreground shadow-lg transition hover:bg-accent/85 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
              aria-label="Send message"
            >
              <ArrowUp className="h-4 w-4" aria-hidden />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
