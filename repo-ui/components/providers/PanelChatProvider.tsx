import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import { DEFAULT_PANEL, type PanelKey } from '@/lib/panels';
import { loadActiveChatId, loadPanelChats, saveActiveChatId, savePanelChats } from '@/lib/storage';
import type { ChatMessage, ChatSession } from '@/types/chat';
import { nanoid } from 'nanoid';

interface PanelChatContextValue {
  panel: PanelKey;
  chats: ChatSession[];
  activeChatId: string | null;
  activeChat: ChatSession | null;
  hasHydrated: boolean;
  selectChat: (chatId: string) => void;
  createChat: (options?: { title?: string; messages?: ChatMessage[] }) => ChatSession;
  updateChat: (chatId: string, updater: (chat: ChatSession) => ChatSession, options?: { touch?: boolean }) => void;
  removeChat: (chatId: string) => void;
  renameChat: (chatId: string, title: string) => void;
}

const PanelChatContext = createContext<PanelChatContextValue | undefined>(undefined);

function createEmptyChat(panel: PanelKey, title?: string, messages: ChatMessage[] = []): ChatSession {
  const timestamp = new Date().toISOString();
  return {
    id: nanoid(),
    panel,
    title:
      title ??
      new Intl.DateTimeFormat('en-US', {
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: 'numeric',
      }).format(new Date()),
    createdAt: timestamp,
    updatedAt: timestamp,
    messages,
    memoryCount: 0,
  };
}

export function PanelChatProvider({
  panel,
  children,
}: {
  panel: PanelKey;
  children: React.ReactNode;
}) {
  const [chats, setChats] = useState<ChatSession[]>([]);
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [hasHydrated, setHasHydrated] = useState(false);

  useEffect(() => {
    setHasHydrated(false);
    setChats(loadPanelChats(panel));
    setActiveChatId(loadActiveChatId(panel));
    setHasHydrated(true);
  }, [panel]);

  useEffect(() => {
    if (!hasHydrated) {
      return;
    }
    savePanelChats(panel, chats);
  }, [panel, chats, hasHydrated]);

  useEffect(() => {
    if (!hasHydrated) {
      return;
    }
    if (activeChatId) {
      saveActiveChatId(panel, activeChatId);
    } else {
      saveActiveChatId(panel, null);
    }
  }, [panel, activeChatId, hasHydrated]);

  useEffect(() => {
    if (!hasHydrated) {
      return;
    }
    if (!activeChatId && chats.length > 0) {
      setActiveChatId(chats[0].id);
    }
  }, [activeChatId, chats, hasHydrated]);

  const selectChat = useCallback((chatId: string) => {
    setActiveChatId(chatId);
  }, []);

  const updateChats = useCallback((updater: (current: ChatSession[]) => ChatSession[]) => {
    setChats((current) => {
      const next = updater(current);
      return next.slice().sort((a, b) => (a.updatedAt < b.updatedAt ? 1 : -1));
    });
  }, []);

  const createChat = useCallback(
    (options?: { title?: string; messages?: ChatMessage[] }) => {
      const chat = createEmptyChat(panel, options?.title, options?.messages);
      updateChats((current) => [chat, ...current]);
      setActiveChatId(chat.id);
      return chat;
    },
    [panel, updateChats],
  );

  const updateChat = useCallback(
    (chatId: string, updater: (chat: ChatSession) => ChatSession, options?: { touch?: boolean }) => {
      updateChats((current) =>
        current.map((chat) => {
          if (chat.id !== chatId) return chat;
          const updated = updater(chat);
          return {
            ...updated,
            updatedAt: options?.touch === false ? chat.updatedAt : new Date().toISOString(),
          };
        }),
      );
    },
    [updateChats],
  );

  const removeChat = useCallback(
    (chatId: string) => {
      updateChats((current) => current.filter((chat) => chat.id !== chatId));
      setActiveChatId((current) => {
        if (current === chatId) {
          return null;
        }
        return current;
      });
    },
    [updateChats],
  );

  const renameChat = useCallback(
    (chatId: string, title: string) => {
      updateChat(chatId, (chat) => ({ ...chat, title }));
    },
    [updateChat],
  );

  const value = useMemo<PanelChatContextValue>(() => {
    const activeChat = chats.find((chat) => chat.id === activeChatId) ?? null;
    return {
      panel,
      chats,
      activeChatId,
      activeChat,
      hasHydrated,
      selectChat,
      createChat,
      updateChat,
      removeChat,
      renameChat,
    };
  }, [panel, chats, activeChatId, hasHydrated, selectChat, createChat, updateChat, removeChat, renameChat]);

  return <PanelChatContext.Provider value={value}>{children}</PanelChatContext.Provider>;
}

export function usePanelChats() {
  const context = useContext(PanelChatContext);
  if (!context) {
    throw new Error('usePanelChats must be used within PanelChatProvider');
  }
  return context;
}

export function useActiveChat() {
  const context = usePanelChats();
  return context.activeChat ?? null;
}
