
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { MutableRefObject } from 'react';
import { nanoid } from 'nanoid';

import { CouncilPicker } from '@/components/council/CouncilPicker';
import { Composer } from '@/components/chat/Composer';
import { Message } from '@/components/chat/Message';
import { TelemetryStrip } from '@/components/layout/TelemetryStrip';
import { usePanelChats } from '@/components/providers';
import fetcher, { FetcherError, CouncilRequest } from '@/lib/fetcher';
import type { PanelKey } from '@/lib/panels';
import type { CouncilMember, ChatMessage, RagMatch, MessageMetadata } from '@/types/chat';
import type { TelemetrySnapshot } from '@/types/telemetry';
import { sleep } from '@/lib/utils';

interface ChatWindowProps {
  panel: PanelKey;
  onMemoryCountChange?: (count: number) => void;
  telemetry: TelemetrySnapshot | null;
  lastTelemetryUpdate: number | null;
}

interface CouncilResponse {
  reply?: string;
  message?: string;
  content?: string;
}

interface RagSearchResponse {
  matches?: RagMatch[];
}

interface StreamQueueItem {
  content: string;
  placeholderId: string;
}

const STREAM_LIMIT = 3;

function formatStatusSuffix(error: FetcherError | null) {
  if (!error) {
    return '';
  }
  return ` (status ${error.status})`;
}

export function ChatWindow({ panel, onMemoryCountChange, telemetry, lastTelemetryUpdate }: ChatWindowProps) {
  const { activeChat, activeChatId, chats, createChat, selectChat, updateChat, hasHydrated } = usePanelChats();
  const [isSending, setIsSending] = useState(false);
  const [forwardingMessage, setForwardingMessage] = useState<ChatMessage | null>(null);
  const [forwardPickerOpen, setForwardPickerOpen] = useState(false);
  const [contextMatches, setContextMatches] = useState<RagMatch[]>([]);
  const [contextLoading, setContextLoading] = useState(false);
  const contextCacheRef = useRef(new Map<string, RagMatch[]>());
  const bottomAnchorRef = useRef<HTMLDivElement | null>(null);
  const [activeStreams, setActiveStreams] = useState(0);
  const streamQueueRef = useRef<StreamQueueItem[]>([]);
  const streamingFallbackRef = useRef(false);
  const sessionIdRef = useRef<string>(nanoid());

  useEffect(() => {
    if (activeChatId) {
      sessionIdRef.current = activeChatId;
    }
  }, [activeChatId]);

  useEffect(() => {
    if (activeStreams === 0 && streamQueueRef.current.length === 0) {
      setIsSending(false);
    } else {
      setIsSending(true);
    }
  }, [activeStreams]);

  useEffect(() => {
    if (!hasHydrated) {
      return;
    }
    if (!activeChat && chats.length === 0) {
      const chat = createChat();
      selectChat(chat.id);
    }
  }, [hasHydrated, activeChat, chats.length, createChat, selectChat]);

  useEffect(() => {
    const chatId = activeChatId;
    if (!chatId) {
      setContextMatches([]);
      onMemoryCountChange?.(0);
      return;
    }
    const cached = contextCacheRef.current.get(chatId);
    if (cached) {
      setContextMatches(cached);
      onMemoryCountChange?.(cached.length);
      updateChat(
        chatId,
        (chat) => ({
          ...chat,
          memoryCount: cached.length,
        }),
        { touch: false },
      );
      return;
    }
    let cancelled = false;
    setContextLoading(true);
    fetcher
      .json<RagSearchResponse>('/relay/api/rag/search', {
        method: 'POST',
        body: { panel, query: 'context', k: 5 },
      })
      .then((response) => {
        if (cancelled || !chatId) return;
        const matches = Array.isArray(response)
          ? (response as RagMatch[])
          : response.matches ?? [];
        contextCacheRef.current.set(chatId, matches);
        setContextMatches(matches);
        onMemoryCountChange?.(matches.length);
        updateChat(
          chatId,
          (chat) => ({
            ...chat,
            memoryCount: matches.length,
          }),
          { touch: false },
        );
      })
      .catch(() => {
        if (cancelled) return;
        setContextMatches([]);
        onMemoryCountChange?.(0);
      })
      .finally(() => {
        if (!cancelled) {
          setContextLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [activeChatId, panel, onMemoryCountChange, updateChat]);

  useEffect(() => {
    bottomAnchorRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [activeChat?.messages.length, isSending, contextMatches.length]);

  const appendMessages = useCallback(
    (messages: ChatMessage[], options?: { touch?: boolean }) => {
      if (!activeChatId) return;
      updateChat(
        activeChatId,
        (chat) => ({
          ...chat,
          messages: [...chat.messages, ...messages],
        }),
        options,
      );
    },
    [activeChatId, updateChat],
  );

  const patchMessage = useCallback(
    (messageId: string, patch: Partial<ChatMessage>, options?: { touch?: boolean }) => {
      if (!activeChatId) return;
      updateChat(
        activeChatId,
        (chat) => ({
          ...chat,
          messages: chat.messages.map((message) => {
            if (message.id !== messageId) return message;
            return {
              ...message,
              ...patch,
              metadata: patch.metadata
                ? { ...message.metadata, ...patch.metadata }
                : message.metadata,
            };
          }),
        }),
        options,
      );
    },
    [activeChatId, updateChat],
  );

  const updateMessageMetadata = useCallback(
    (messageId: string, updater: (metadata: MessageMetadata | undefined) => MessageMetadata, options?: { touch?: boolean }) => {
      if (!activeChatId) return;
      updateChat(
        activeChatId,
        (chat) => ({
          ...chat,
          messages: chat.messages.map((message) => {
            if (message.id !== messageId) return message;
            return {
              ...message,
              metadata: updater(message.metadata),
            };
          }),
        }),
        options,
      );
    },
    [activeChatId, updateChat],
  );

  const visibleMessages = useMemo(() => {
    if (!activeChat) return [];
    return activeChat.messages.filter((message) => !message.metadata?.hidden);
  }, [activeChat]);

  const contextPayload = useMemo(() => contextMatches.map((match) => match.content), [contextMatches]);

  const councilRequestFor = useCallback(
    (input: string, targetPanel: PanelKey = panel): CouncilRequest => {
      const normalizedText = typeof input === 'string' ? input.trim() : '';
      if (!normalizedText) {
        console.warn('[council] Empty text payload');
      }

      const sessionId =
        (activeChatId && activeChatId.trim()) ||
        sessionIdRef.current ||
        (targetPanel ? `${targetPanel}-default` : 'personal');

      sessionIdRef.current = sessionId;

      const metadata: Record<string, unknown> = {};
      if (targetPanel) {
        metadata.panel = targetPanel;
      }
      if (contextPayload.length > 0) {
        metadata.context = contextPayload;
      }

      return {
        text: normalizedText,
        sessionId,
        metadata,
      };
    },
    [activeChatId, contextPayload, panel],
  );

  const requestCouncilFallback = useCallback(
    async (messageContent: string, targetPanel: PanelKey) => {
      const request = councilRequestFor(messageContent, targetPanel);
      return fetcher.councilRequest<CouncilResponse>('/relay/api/council', request);
    },
    [councilRequestFor],
  );

  const startStreamingReply = useCallback(
    ({ content, placeholderId }: { content: string; placeholderId: string }) => {
      let replyAccumulator = '';
      let doneReceived = false;
      let traceId: string | undefined;
      let retrievedFromStream: RagMatch[] | undefined;

      updateMessageMetadata(
        placeholderId,
        (metadata) => ({
          ...(metadata ?? {}),
          streamingState: 'streaming',
        }),
        { touch: false },
      );

      setActiveStreams((count) => count + 1);

      const handleChunk = (chunk: unknown) => {
        if (!chunk || typeof chunk !== 'object') {
          return;
        }
        const payload = chunk as Record<string, unknown>;
        const type = payload.type;
        if (type === 'context') {
          const retrieved = payload.retrieved;
          if (Array.isArray(retrieved)) {
            retrievedFromStream = retrieved as RagMatch[];
            if (activeChatId) {
              contextCacheRef.current.set(activeChatId, retrievedFromStream);
            }
            setContextMatches(retrievedFromStream);
            onMemoryCountChange?.(retrievedFromStream.length);
          }
          return;
        }
        if (type === 'delta') {
          traceId = (payload.trace_id as string) ?? traceId;
          const token = typeof payload.token === 'string' ? payload.token : '';
          if (token) {
            replyAccumulator += token;
            patchMessage(
              placeholderId,
              {
                content: replyAccumulator,
              },
              { touch: true },
            );
            updateMessageMetadata(
              placeholderId,
              (metadata) => ({
                ...(metadata ?? {}),
                streamingState: 'streaming',
                traceId: traceId ?? (metadata?.traceId as string | undefined),
                retrieved: (retrievedFromStream ?? metadata?.retrieved) as RagMatch[] | undefined,
              }),
            );
          }
          return;
        }
        if (type === 'done') {
          doneReceived = true;
          traceId = (payload.trace_id as string) ?? traceId;
          replyAccumulator = typeof payload.reply === 'string' && payload.reply ? (payload.reply as string) : replyAccumulator;
          const tokensUsed = (payload.tokens_used as number) ?? 0;
          const finalRetrieved = (payload.retrieved as RagMatch[]) ?? retrievedFromStream;
          patchMessage(
            placeholderId,
            {
              content: replyAccumulator,
              delivery: 'idle',
            },
            { touch: true },
          );
          updateMessageMetadata(
            placeholderId,
            (metadata) => ({
              ...(metadata ?? {}),
              streamingState: 'completed',
              traceId,
              tokensUsed,
              retrieved: finalRetrieved ?? metadata?.retrieved,
            }),
          );
          void fetcher
            .json('/relay/api/rag/store', {
              method: 'POST',
              body: { panel, chunk: `${content}
---
${replyAccumulator}` },
            })
            .catch(() => undefined);
          return;
        }
        if (type === 'error') {
          patchMessage(
            placeholderId,
            {
              content: 'Council stream interrupted. Retrying…',
              delivery: 'error',
            },
            { touch: true },
          );
          updateMessageMetadata(
            placeholderId,
            (metadata) => ({
              ...(metadata ?? {}),
              streamingState: 'error',
              error: typeof payload.message === 'string' ? payload.message : undefined,
            }),
          );
        }
      };

      const streamRequest = councilRequestFor(content);

      fetcher
        .councilStream('/relay/api/council/stream', streamRequest, handleChunk)
        .catch(async (error: unknown) => {
          if (error instanceof FetcherError) {
            const fetchError = error as FetcherError;
            if (fetchError.status === 501) {
              streamingFallbackRef.current = true;
            }
          }
          if (doneReceived) {
            return;
          }
          try {
            const response = await requestCouncilFallback(content, panel);
            const reply =
              response.reply ?? response.message ?? response.content ?? 'Ready to help with that.';
            replyAccumulator = reply;
            patchMessage(
              placeholderId,
              {
                content: reply,
                delivery: 'idle',
              },
              { touch: true },
            );
            updateMessageMetadata(
              placeholderId,
              (metadata) => ({
                ...(metadata ?? {}),
                streamingState: streamingFallbackRef.current ? 'fallback' : 'completed',
              }),
            );
            void fetcher
              .json('/relay/api/rag/store', {
                method: 'POST',
                body: { panel, chunk: `${content}
---
${reply}` },
              })
              .catch(() => undefined);
          } catch (fallbackError: unknown) {
            const fetchError = fallbackError instanceof FetcherError ? (fallbackError as FetcherError) : null;
            const showBusy = fetchError !== null && fetchError.status >= 400;
            const statusInfo = formatStatusSuffix(fetchError);
            patchMessage(
              placeholderId,
              {
                content: showBusy
                  ? `Council is busy${statusInfo}. Try again in a few moments.`
                  : `Council stream interrupted${statusInfo}. Try again in a few moments.`,
                delivery: 'error',
              },
              { touch: true },
            );
            updateMessageMetadata(
              placeholderId,
              (metadata) => ({
                ...(metadata ?? {}),
                streamingState: 'error',
                error:
                  fallbackError instanceof Error
                    ? fallbackError.message
                    : undefined,
              }),
            );
          }
        })
        .finally(() => {
          setActiveStreams((count) => Math.max(0, count - 1));
        });
    },
    [activeChatId, contextCacheRef, onMemoryCountChange, panel, patchMessage, councilRequestFor, requestCouncilFallback, setContextMatches, updateMessageMetadata],
  );

  useEffect(() => {
    if (streamingFallbackRef.current && streamQueueRef.current.length > 0) {
      const queued = [...streamQueueRef.current];
      streamQueueRef.current.length = 0;
      setIsSending(true);
      queued.forEach((item) => {
        (async () => {
          try {
            const response = await requestCouncilFallback(item.content, panel);
            const reply =
              response.reply ?? response.message ?? response.content ?? 'Ready to help with that.';
            patchMessage(
              item.placeholderId,
              {
                content: reply,
                delivery: 'idle',
              },
              { touch: true },
            );
            updateMessageMetadata(
              item.placeholderId,
              (metadata) => ({
                ...(metadata ?? {}),
                streamingState: 'fallback',
              }),
            );
            void fetcher
              .json('/relay/api/rag/store', {
                method: 'POST',
                body: { panel, chunk: `${item.content}
---
${reply}` },
              })
              .catch(() => undefined);
          } catch (error: unknown) {
            const fetchError = error instanceof FetcherError ? (error as FetcherError) : null;
            const statusInfo = formatStatusSuffix(fetchError);
            patchMessage(
              item.placeholderId,
              {
                content:
                  fetchError !== null && fetchError.status >= 400
                    ? `Council is busy${statusInfo}. Try again in a few moments.`
                    : `Council stream interrupted${statusInfo}. Try again in a few moments.`,
                delivery: 'error',
              },
              { touch: true },
            );
            updateMessageMetadata(
              item.placeholderId,
              (metadata) => ({
                ...(metadata ?? {}),
                streamingState: 'error',
                error: fetchError?.message,
              }),
            );
          } finally {
            if (streamQueueRef.current.length === 0 && activeStreams === 0) {
              setIsSending(false);
            }
          }
        })();
      });
      return;
    }
    if (activeStreams >= STREAM_LIMIT) {
      return;
    }
    const next = streamQueueRef.current.shift();
    if (next) {
      startStreamingReply(next);
    }
  }, [activeStreams, panel, patchMessage, requestCouncilFallback, startStreamingReply, updateMessageMetadata]);

  const forwardToMembers = useCallback(
    async (baseContent: string, members: CouncilMember[], originMessageId?: string) => {
      if (!members.length) return;
      const names = members.map((member) => member.name);
      if (originMessageId) {
        updateMessageMetadata(
          originMessageId,
          (metadata) => ({
            ...(metadata ?? {}),
            forwardedTo: Array.from(new Set([...(metadata?.forwardedTo ?? []), ...names])),
          }),
          { touch: false },
        );
      }
      for (const member of members) {
        const placeholderId = nanoid();
        const placeholder: ChatMessage = {
          id: placeholderId,
          role: 'assistant',
          content: `Forwarding to ${member.name}…`,
          createdAt: new Date().toISOString(),
          delivery: 'pending',
          metadata: {
            forwardedTo: [member.name],
            councilMemberId: member.id,
            councilMemberName: member.name,
          },
        };
        appendMessages([placeholder]);
        try {
          const response = await requestCouncilFallback(baseContent, member.panel);
          const reply =
            response.reply ?? response.message ?? response.content ?? `Shared with ${member.name}.`;
          patchMessage(
            placeholderId,
            {
              content: reply,
              delivery: 'idle',
              metadata: {
                forwardedTo: [member.name],
                councilMemberId: member.id,
                councilMemberName: member.name,
              },
            },
            { touch: true },
          );
        } catch {
          patchMessage(
            placeholderId,
            {
              content: `Unable to reach ${member.name}.`,
              delivery: 'error',
            },
            { touch: true },
          );
        }
        await sleep(180);
      }
    },
    [appendMessages, patchMessage, requestCouncilFallback, updateMessageMetadata],
  );

  const handleSend = useCallback(
    async (content: string, options?: { targets?: CouncilMember[] }) => {
      if (!activeChatId) return;
      const now = new Date().toISOString();

      if (options?.targets && options.targets.length > 0) {
        const userMessage: ChatMessage = {
          id: nanoid(),
          role: 'user',
          content,
          createdAt: now,
          metadata: { forwardedTo: options.targets.map((member) => member.name) },
        };
        appendMessages([userMessage]);
        setIsSending(true);
        try {
          await forwardToMembers(content, options.targets, userMessage.id);
        } finally {
          setIsSending(false);
        }
        return;
      }

      const userMessage: ChatMessage = {
        id: nanoid(),
        role: 'user',
        content,
        createdAt: now,
      };
      const assistantPlaceholderId = nanoid();
      const assistantPlaceholder: ChatMessage = {
        id: assistantPlaceholderId,
        role: 'assistant',
        content: '',
        createdAt: now,
        delivery: 'pending',
        metadata: {},
      };
      appendMessages([userMessage, assistantPlaceholder]);

      if (streamingFallbackRef.current) {
        setIsSending(true);
        try {
          const response = await requestCouncilFallback(content, panel);
          const reply =
            response.reply ?? response.message ?? response.content ?? 'Ready to help with that.';
          patchMessage(
            assistantPlaceholderId,
            {
              content: reply,
              delivery: 'idle',
            },
            { touch: true },
          );
          updateMessageMetadata(
            assistantPlaceholderId,
            (metadata) => ({
              ...(metadata ?? {}),
              streamingState: 'fallback',
            }),
          );
          void fetcher
            .json('/relay/api/rag/store', {
              method: 'POST',
              body: { panel, chunk: `${content}
---
${reply}` },
            })
            .catch(() => undefined);
        } catch (error: unknown) {
          const fetchError = error instanceof FetcherError ? (error as FetcherError) : null;
          const statusInfo = formatStatusSuffix(fetchError);
          patchMessage(
            assistantPlaceholderId,
            {
              content:
                fetchError !== null && fetchError.status >= 400
                  ? `Council is busy${statusInfo}. Try again in a few moments.`
                  : `Council stream interrupted${statusInfo}. Try again in a few moments.`,
              delivery: 'error',
            },
            { touch: true },
          );
          updateMessageMetadata(
            assistantPlaceholderId,
            (metadata) => ({
              ...(metadata ?? {}),
              streamingState: 'error',
              error: fetchError?.message,
            }),
          );
        } finally {
          setIsSending(false);
        }
        return;
      }

      if (activeStreams >= STREAM_LIMIT) {
        streamQueueRef.current.push({
          content,
          placeholderId: assistantPlaceholderId,
        });
        updateMessageMetadata(
          assistantPlaceholderId,
          (metadata) => ({
            ...(metadata ?? {}),
            streamingState: 'queued',
          }),
        );
        setIsSending(true);
        return;
      }

      startStreamingReply({ content, placeholderId: assistantPlaceholderId });
    },
    [
      activeChatId,
      activeStreams,
      appendMessages,
      forwardToMembers,
      panel,
      patchMessage,
      requestCouncilFallback,
      startStreamingReply,
      updateMessageMetadata,
    ],
  );

  const handleForward = useCallback(
    async (members: CouncilMember[]) => {
      if (!forwardingMessage) return;
      await forwardToMembers(forwardingMessage.content, members, forwardingMessage.id);
      setForwardingMessage(null);
    },
    [forwardToMembers, forwardingMessage],
  );

  return (
    <section className="flex h-full min-h-0 flex-col">
      <CouncilPicker
        panel={panel}
        open={forwardPickerOpen}
        onOpenChange={(open) => {
          setForwardPickerOpen(open);
          if (!open) {
            setForwardingMessage(null);
          }
        }}
        onConfirm={handleForward}
        title="Forward message"
        description="Select council members to forward this message."
      />
      
      {/* Scrollable message area */}
      <div className="flex-1 min-h-0 overflow-y-auto scroll-smooth scrollbar-thin scrollbar-thumb-accent/40 scrollbar-track-transparent">
        <div className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-10 sm:px-6">
          <div className="text-center">
            <p className="text-xs uppercase tracking-[0.5em] text-muted-foreground/70">Canvas</p>
            <h2 className="mt-2 text-2xl font-semibold text-foreground">Conversation hub</h2>
          </div>
          {contextLoading && (
            <div className="animate-pulse rounded-3xl bg-surface-muted/40 px-5 py-4 text-sm text-muted-foreground shadow-lg">
              Loading panel memory…
            </div>
          )}
          {!contextLoading && contextMatches.length > 0 && (
            <div className="rounded-3xl bg-accent/10 px-5 py-4 text-sm text-accent shadow-lg">
              <div className="flex items-center justify-between">
                <p className="font-semibold">Memory: {contextMatches.length}</p>
              </div>
              <ul className="mt-3 space-y-2 text-left text-xs text-accent/80">
                {contextMatches.slice(0, 3).map((match) => (
                  <li key={match.id} className="leading-snug">
                    • {match.content.slice(0, 160)}
                    {match.content.length > 160 ? '…' : ''}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {visibleMessages.length === 0 && (
            <div className="rounded-3xl bg-surface-muted/40 px-6 py-12 text-center text-sm text-muted-foreground shadow-lg">
              <p>Start a conversation to brief the council and capture fresh context.</p>
            </div>
          )}
          {visibleMessages.map((message) => (
            <Message
              key={message.id}
              message={message}
              onForward={(msg) => {
                setForwardingMessage(msg);
                setForwardPickerOpen(true);
              }}
            />
          ))}
          <div ref={bottomAnchorRef} />
        </div>
      </div>
      
      {/* Fixed composer at bottom */}
      <div className="bg-background/95 backdrop-blur-sm px-4 py-2 sm:px-6 shadow-lg">
        <div className="mx-auto w-full max-w-3xl">
          <Composer
            panel={panel}
            disabled={!activeChatId}
            busy={streamingFallbackRef.current ? isSending : false}
            onSend={handleSend}
          />
          <p className="mt-1 text-center text-xs text-muted-foreground/70">
            Conversations stay in this panel. Switch panels from the sidebar for domain-specific context.
          </p>
        </div>
      </div>
      
      {/* Fixed telemetry footer */}
      <TelemetryStrip panel={panel} telemetry={telemetry} lastUpdatedAt={lastTelemetryUpdate} />
    </section>
  );
}
