import Image from 'next/image';
import { useRouter } from 'next/router';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import clsx from 'clsx';
import {
  Bot,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  PlugZap,
  Workflow,
  User,
  Settings,
  MessageSquare,
} from 'lucide-react';

import { usePanelChats } from '@/components/providers';
import { ThemeAccentToggle } from '@/components/layout/ThemeAccentToggle';
import { PANEL_DEFINITIONS, type PanelKey } from '@/lib/panels';
import { readJSON, STORAGE_KEYS, writeJSON } from '@/lib/storage';

type SidebarView = 'chat' | 'bits';

interface SidebarProps {
  panel: PanelKey;
  activeView: SidebarView;
  onSelectView: (view: SidebarView) => void;
  onShowConnectors: () => void;
}

const SIDEBAR_BREAKPOINT = 1280;

export function Sidebar({ panel, activeView, onSelectView, onShowConnectors }: SidebarProps) {
  const router = useRouter();
  const { chats, activeChatId, selectChat, createChat } = usePanelChats();
  const [collapsed, setCollapsed] = useState(false);
  const [openMenu, setOpenMenu] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const stored = readJSON<boolean>(STORAGE_KEYS.sidebarCollapsed, false);
    setCollapsed(stored);
  }, []);

  useEffect(() => {
    writeJSON(STORAGE_KEYS.sidebarCollapsed, collapsed);
  }, [collapsed]);

  useEffect(() => {
    const listener = () => {
      if (typeof window === 'undefined') return;
      if (window.innerWidth < SIDEBAR_BREAKPOINT) {
        setCollapsed(true);
      }
    };
    listener();
    window.addEventListener('resize', listener);
    return () => window.removeEventListener('resize', listener);
  }, []);

  const containerClasses = clsx(
    'relative z-30 flex h-screen flex-col bg-surface/90 px-2 py-4 backdrop-blur-lg transition-all duration-300 ease-out-cubic',
    collapsed ? 'w-[72px]' : 'w-64',
  );

  const makePanelRoute = useMemo(
    () =>
      new Map<PanelKey, string>(
        PANEL_DEFINITIONS.map((definition) => [definition.key, `/p/${definition.key}`]),
      ),
    [],
  );

  const handlePanelSelect = (nextPanel: PanelKey) => {
    if (nextPanel === panel) {
      return;
    }
    onSelectView('chat');
    router.push(makePanelRoute.get(nextPanel) ?? `/p/${nextPanel}`);
  };

  const handleCreateChat = useCallback(() => {
    onSelectView('chat');
    const chat = createChat();
    selectChat(chat.id);
  }, [createChat, onSelectView, selectChat]);

  const handleLogoClick = () => {
    setCollapsed((value) => !value);
  };

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)) {
        return;
      }
      const isMeta = event.metaKey || event.ctrlKey;
      if (isMeta && !event.shiftKey && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        setCollapsed((value) => !value);
      }
      if (isMeta && event.shiftKey && event.key.toLowerCase() === 'n') {
        event.preventDefault();
        handleCreateChat();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [handleCreateChat]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setOpenMenu(false);
      }
    };

    if (openMenu) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [openMenu]);

  return (
    <aside className={containerClasses} data-collapsed={collapsed} aria-label="Workspace navigation">
      <div className="flex items-center justify-center py-2 px-2">
        <button
          type="button"
          onClick={handleLogoClick}
          className="group flex items-center justify-center rounded-lg p-1 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
        >
          <img
            src="/camarad.svg"
            alt="Camarad"
            className="h-7 w-7 transition-all duration-300"
            style={{ filter: 'invert(var(--invert-logo, 1))' }}
          />
        </button>
        {!collapsed && (
          <button
            type="button"
            onClick={() => setCollapsed(true)}
            className="ml-auto flex h-6 w-6 items-center justify-center rounded-full bg-surface-muted text-muted-foreground transition hover:text-accent focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 shadow-lg"
            aria-label="Collapse sidebar"
          >
            <PanelLeftClose className="h-3 w-3" />
          </button>
        )}
      </div>

      <div className="mt-2 px-2">
        <button
          type="button"
          onClick={handleCreateChat}
          className={clsx(
            'group flex w-full items-center gap-1.5 rounded-xl bg-accent/10 px-2 py-1.5 text-[12px] font-medium text-accent transition hover:bg-accent/15 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 shadow-lg',
            collapsed && 'justify-center px-0 text-accent',
          )}
          aria-label="New chat"
        >
          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-accent text-accent-foreground shadow-inner">
            <Plus className="h-3 w-3" aria-hidden />
          </span>
          {!collapsed && <span>New Chat</span>}
        </button>
      </div>

      <nav className="mt-3 flex-1 min-h-0 flex flex-col gap-2">
        <div className="px-2">
          {!collapsed && (
            <p className="px-2 mb-0.5 text-[10px] font-semibold uppercase tracking-[0.3em] text-muted-foreground/80">
              Panels
            </p>
          )}
          <ul className="space-y-0.5">
            {PANEL_DEFINITIONS.map((definition) => {
              const Icon = definition.icon;
              const isActive = panel === definition.key;
              return (
                <li key={definition.key}>
                  <button
                    type="button"
                    onClick={() => handlePanelSelect(definition.key)}
                    className={clsx(
                      'flex w-full items-center gap-1.5 rounded-lg px-2 py-1.5 text-[12px] font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2',
                      isActive
                        ? 'bg-accent/15 text-accent shadow-inner'
                        : 'text-muted-foreground hover:bg-surface-muted/80 hover:text-foreground',
                      collapsed && 'justify-center px-0',
                    )}
                    aria-label={collapsed ? definition.label : undefined}
                  >
                    <Icon className="h-4 w-4 shrink-0" aria-hidden />
                    {!collapsed && <span>{definition.label}</span>}
                  </button>
                </li>
              );
            })}
          </ul>
        </div>

        <div className="px-2">
          {!collapsed && (
            <p className="px-2 mb-0.5 text-[10px] font-semibold uppercase tracking-[0.3em] text-muted-foreground/80">
              Connectors
            </p>
          )}
          <button
            type="button"
            onClick={onShowConnectors}
            className={clsx(
              'flex w-full items-center gap-1.5 rounded-lg px-2 py-1.5 text-[12px] font-medium text-muted-foreground transition hover:bg-surface-muted/80 hover:text-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2',
              collapsed && 'justify-center px-0',
            )}
            aria-label={collapsed ? 'Manage connectors' : undefined}
          >
            <PlugZap className="h-4 w-4 shrink-0" aria-hidden />
            {!collapsed && <span>Manage Connectors</span>}
          </button>
        </div>

        <div className="px-2">
          {!collapsed && (
            <p className="px-2 mb-0.5 text-[10px] font-semibold uppercase tracking-[0.3em] text-muted-foreground/80">
              Workspace
            </p>
          )}
          <div className="space-y-0.5">
            <button
              type="button"
              onClick={() => onSelectView('chat')}
              className={clsx(
                'flex w-full items-center gap-1.5 rounded-lg px-2 py-1.5 text-[12px] font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2',
                activeView === 'chat'
                  ? 'bg-accent/15 text-accent shadow-inner'
                  : 'text-muted-foreground hover:bg-surface-muted/80 hover:text-foreground',
                collapsed && 'justify-center px-0',
              )}
              aria-label={collapsed ? 'Canvas' : undefined}
            >
              <Bot className="h-4 w-4 shrink-0" aria-hidden />
              {!collapsed && <span>Canvas</span>}
            </button>
            <button
              type="button"
              onClick={() => onSelectView('bits')}
              className={clsx(
                'flex w-full items-center gap-1.5 rounded-lg px-2 py-1.5 text-[12px] font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2',
                activeView === 'bits'
                  ? 'bg-accent/15 text-accent shadow-inner'
                  : 'text-muted-foreground hover:bg-surface-muted/80 hover:text-foreground',
                collapsed && 'justify-center px-0',
              )}
              aria-label={collapsed ? 'Bits orchestrator' : undefined}
            >
              <Workflow className="h-4 w-4 shrink-0" aria-hidden />
              {!collapsed && <span>Bits Orchestrator</span>}
            </button>
          </div>
        </div>

        <div className={clsx(
          'flex-1 min-h-0 overflow-y-auto scrollbar-thin scrollbar-thumb-accent/40 scrollbar-track-transparent px-2',
          collapsed && 'scrollbar-none'
        )}>
          {!collapsed && (
            <p className="px-2 mb-0.5 text-[10px] font-semibold uppercase tracking-[0.3em] text-muted-foreground/80">
              Chats
            </p>
          )}
          {chats.length === 0 ? (
            <div
              className={clsx(
                'mt-1 rounded-lg bg-surface-muted/40 px-2 py-3 text-center text-[11px] text-muted-foreground shadow-lg',
                collapsed && 'px-1',
              )}
            >
              {!collapsed ? (
                <p>Start your first conversation for this panel.</p>
              ) : (
                <Plus className="mx-auto h-3 w-3 opacity-70" aria-hidden />
              )}
            </div>
          ) : (
            <ul className="mt-0.5 space-y-0.5 pb-8">
              {chats.map((chat) => (
                <li key={chat.id}>
                  <button
                    type="button"
                    onClick={() => {
                      onSelectView('chat');
                      selectChat(chat.id);
                    }}
                    className={clsx(
                      'group flex w-full items-center gap-1.5 rounded-lg px-2 py-1.5 text-left text-[12px] transition focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2',
                      activeChatId === chat.id
                        ? 'bg-accent/15 text-accent shadow-inner'
                        : 'text-muted-foreground hover:bg-accent/10 hover:text-foreground',
                      collapsed && 'justify-center px-0',
                    )}
                  >
                    <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-surface-muted text-muted-foreground/70">
                      <MessageSquare className="h-3.5 w-3.5" aria-hidden />
                    </span>
                    {!collapsed && (
                      <div className="flex min-w-0 flex-1 flex-col">
                        <span className="truncate font-medium">{chat.title}</span>
                        <span className="truncate text-[10px] text-muted-foreground/70">
                          {new Intl.DateTimeFormat('en-US', {
                            hour: 'numeric',
                            minute: '2-digit',
                          }).format(new Date(chat.updatedAt))}
                        </span>
                      </div>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </nav>

      <div className="relative mt-auto" ref={menuRef}>
        <button
          type="button"
          onClick={() => setOpenMenu(!openMenu)}
          className="flex w-full items-center gap-1.5 rounded-xl bg-surface-muted/40 p-1.5 transition hover:bg-surface-muted/60 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 shadow-lg"
          aria-label="User menu"
          aria-expanded={openMenu}
        >
          <div className="h-7 w-7 rounded-full bg-gradient-to-br from-accent/60 to-accent/30 shadow-inner" />
          {!collapsed && (
            <div className="leading-tight text-left flex-1">
              <p className="text-[12px] font-semibold text-foreground">You</p>
              <p className="text-[10px] text-muted-foreground">Lead Implementer</p>
            </div>
          )}
        </button>

        {openMenu && (
          <div className="absolute bottom-full right-0 mb-2 w-full rounded-xl bg-surface backdrop-blur-lg shadow-xl">
            {!collapsed ? (
              <>
                <div className="p-1.5 space-y-0.5">
                  <button
                    type="button"
                    className="flex w-full items-center gap-1.5 rounded-lg px-2 py-1 text-[12px] font-medium text-muted-foreground transition hover:bg-surface-muted/80 hover:text-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
                  >
                    <User className="h-3.5 w-3.5 shrink-0" aria-hidden />
                    <span>Profile</span>
                  </button>
                  <button
                    type="button"
                    className="flex w-full items-center gap-1.5 rounded-lg px-2 py-1 text-[12px] font-medium text-muted-foreground transition hover:bg-surface-muted/80 hover:text-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
                  >
                    <Settings className="h-3.5 w-3.5 shrink-0" aria-hidden />
                    <span>Settings</span>
                  </button>
                </div>
              </>
            ) : (
              <div className="p-1.5 flex justify-center gap-2">
                <button
                  type="button"
                  className="flex h-7 w-7 items-center justify-center rounded-lg text-muted-foreground transition hover:bg-surface-muted/80 hover:text-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
                  aria-label="Profile"
                >
                  <User className="h-4 w-4 shrink-0" aria-hidden />
                </button>
                <button
                  type="button"
                  className="flex h-7 w-7 items-center justify-center rounded-lg text-muted-foreground transition hover:bg-surface-muted/80 hover:text-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
                  aria-label="Settings"
                >
                  <Settings className="h-4 w-4 shrink-0" aria-hidden />
                </button>
              </div>
            )}
            
            <div className="p-1.5">
              <ThemeAccentToggle collapsed={collapsed} />
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}
