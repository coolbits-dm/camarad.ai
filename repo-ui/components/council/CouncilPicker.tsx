import * as Dialog from '@radix-ui/react-dialog';
import { Check, Search, Users } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import clsx from 'clsx';

import { getCouncilMembers, searchCouncilMembers } from '@/lib/council';
import type { PanelKey } from '@/lib/panels';
import type { CouncilMember } from '@/types/chat';

interface CouncilPickerProps {
  panel?: PanelKey;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: (members: CouncilMember[]) => void;
  title?: string;
  description?: string;
}

export function CouncilPicker({
  panel,
  open,
  onOpenChange,
  onConfirm,
  title = 'Forward to council',
  description = 'Select one or more council members to forward this message.',
}: CouncilPickerProps) {
  const [search, setSearch] = useState('');
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!open) {
      setSearch('');
      setSelectedIds(new Set());
    }
  }, [open]);

  const members = useMemo(() => {
    if (search.trim().length > 0) {
      return searchCouncilMembers(search, panel);
    }
    return getCouncilMembers(panel);
  }, [search, panel]);

  const toggleMember = (memberId: string) => {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(memberId)) {
        next.delete(memberId);
      } else {
        next.add(memberId);
      }
      return next;
    });
  };

  const handleConfirm = () => {
    if (selectedIds.size === 0) {
      onOpenChange(false);
      return;
    }
    const selectedMembers = members.filter((member) => selectedIds.has(member.id));
    onConfirm(selectedMembers);
    onOpenChange(false);
  };

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-background/70 backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=open]:fade-in-0 data-[state=closed]:fade-out-0" />
        <Dialog.Content className="fixed inset-0 z-50 flex items-center justify-center p-4 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=open]:zoom-in-95 data-[state=closed]:zoom-out-95">
          <div className="w-full max-w-lg rounded-2xl border border-border/60 bg-surface shadow-2xl">
            <header className="flex items-start gap-3 border-b border-border/40 px-6 py-5">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-accent/15 text-accent">
                <Users className="h-5 w-5" aria-hidden />
              </div>
              <div>
                <Dialog.Title className="text-lg font-semibold text-foreground">{title}</Dialog.Title>
                <Dialog.Description className="mt-1 text-sm text-muted-foreground">{description}</Dialog.Description>
              </div>
            </header>
            <div className="max-h-[420px] overflow-y-auto px-6 py-6">
              <label className="flex items-center gap-2 rounded-xl border border-border/60 bg-background/70 px-3 py-2 text-sm text-muted-foreground focus-within:border-accent/60 focus-within:text-accent">
                <Search className="h-4 w-4 shrink-0" aria-hidden />
                <input
                  type="search"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search council"
                  className="w-full bg-transparent text-sm text-foreground placeholder:text-muted-foreground focus:outline-none"
                />
              </label>

              <ul className="mt-4 space-y-2">
                {members.map((member) => {
                  const isSelected = selectedIds.has(member.id);
                  return (
                    <li key={member.id}>
                      <button
                        type="button"
                        onClick={() => toggleMember(member.id)}
                        className={clsx(
                          'group flex w-full items-center gap-3 rounded-xl border border-border/40 px-3 py-3 text-left transition focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2',
                          isSelected ? 'bg-accent/10 text-accent border-accent/40' : 'hover:bg-surface-muted/60',
                        )}
                      >
                        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-surface-muted text-sm font-semibold uppercase text-muted-foreground/80">
                          {member.name
                            .split(' ')
                            .map((segment) => segment[0])
                            .join('')
                            .slice(0, 2)}
                        </div>
                        <div className="flex-1">
                          <p className="font-medium text-foreground">{member.name}</p>
                          <p className="text-xs text-muted-foreground">
                            {member.handle} · {member.specialty ?? 'Multidisciplinary'}
                          </p>
                        </div>
                        <div
                          className={clsx(
                            'flex h-6 w-6 items-center justify-center rounded-full border border-border/60 transition',
                            isSelected ? 'bg-accent text-accent-foreground border-accent/50' : 'text-transparent',
                          )}
                          aria-hidden
                        >
                          <Check className="h-4 w-4" />
                        </div>
                      </button>
                    </li>
                  );
                })}
                {members.length === 0 && (
                  <li className="rounded-xl border border-dashed border-border/60 bg-surface-muted/40 px-4 py-6 text-center text-sm text-muted-foreground">
                    No council members match “{search}”.
                  </li>
                )}
              </ul>
            </div>
            <footer className="flex items-center justify-between gap-3 border-t border-border/40 px-6 py-4">
              <p className="text-xs text-muted-foreground">
                {selectedIds.size === 0
                  ? 'Select members to forward the message.'
                  : `${selectedIds.size} member${selectedIds.size > 1 ? 's' : ''} selected.`}
              </p>
              <div className="flex items-center gap-2">
                <Dialog.Close
                  className="rounded-full px-4 py-2 text-sm font-medium text-muted-foreground hover:bg-surface-muted/60 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
                  type="button"
                >
                  Cancel
                </Dialog.Close>
                <button
                  type="button"
                  onClick={handleConfirm}
                  className="rounded-full bg-accent px-4 py-2 text-sm font-semibold text-accent-foreground shadow hover:bg-accent/90 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                  disabled={selectedIds.size === 0}
                >
                  Forward
                </button>
              </div>
            </footer>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
