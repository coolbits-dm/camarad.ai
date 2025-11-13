import type { PanelKey } from '@/lib/panels';
import type { ChatSession } from '@/types/chat';

const STORAGE_NAMESPACE = 'camarad:v1';

const isBrowser = typeof window !== 'undefined';

function namespaced(key: string) {
  return `${STORAGE_NAMESPACE}:${key}`;
}

function readRaw(key: string): string | null {
  if (!isBrowser) {
    return null;
  }
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeRaw(key: string, value: string) {
  if (!isBrowser) {
    return;
  }
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // ignore write errors (private mode, quota, etc.)
  }
}

export function readJSON<T>(key: string, fallback: T): T {
  const raw = readRaw(key);
  if (!raw) {
    return fallback;
  }
  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

export function writeJSON(key: string, value: unknown): void {
  try {
    writeRaw(key, JSON.stringify(value));
  } catch {
    // ignored
  }
}

export function remove(key: string): void {
  if (!isBrowser) return;
  try {
    window.localStorage.removeItem(key);
  } catch {
    // ignored
  }
}

export const STORAGE_KEYS = {
  accent: namespaced('accent'),
  sidebarCollapsed: namespaced('sidebar-collapsed'),
  panelChats: (panel: PanelKey) => namespaced(`panel:${panel}`),
  activeChat: (panel: PanelKey) => namespaced(`panel:${panel}:active`),
};

export function loadPanelChats(panel: PanelKey): ChatSession[] {
  return readJSON<ChatSession[]>(STORAGE_KEYS.panelChats(panel), []);
}

export function savePanelChats(panel: PanelKey, chats: ChatSession[]): void {
  writeJSON(STORAGE_KEYS.panelChats(panel), chats);
}

export function loadActiveChatId(panel: PanelKey): string | null {
  return readJSON<string | null>(STORAGE_KEYS.activeChat(panel), null);
}

export function saveActiveChatId(panel: PanelKey, chatId: string | null): void {
  if (chatId) {
    writeJSON(STORAGE_KEYS.activeChat(panel), chatId);
  } else {
    remove(STORAGE_KEYS.activeChat(panel));
  }
}
