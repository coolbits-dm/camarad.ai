import { CornerUpRight, User2 } from 'lucide-react';
import clsx from 'clsx';

import type { ChatMessage } from '@/types/chat';
import { formatTimeLabel } from '@/lib/utils';

interface MessageProps {
  message: ChatMessage;
  onForward?: (message: ChatMessage) => void;
}

function renderContent(content: string) {
  return content.split(/\n{2,}/).map((block, index) => (
    <p key={index} className="leading-relaxed text-sm text-foreground">
      {block}
    </p>
  ));
}

export function Message({ message, onForward }: MessageProps) {
  const isUser = message.role === 'user';
  const alignmentClass = isUser ? 'flex-row-reverse text-right' : 'flex-row text-left';
  const bubbleClasses = clsx(
    'relative w-full max-w-3xl rounded-3xl px-6 py-5 text-left shadow-lg transition',
    isUser
      ? 'bg-accent text-accent-foreground'
      : 'bg-surface-muted/70 text-foreground',
  );

  const metaTime = formatTimeLabel(message.createdAt);

  const forwardedLabel =
    message.metadata?.forwardedTo && message.metadata.forwardedTo.length > 0
      ? `Forwarded to ${message.metadata.forwardedTo.join(', ')}`
      : null;

  const streamingState = !isUser ? (message.metadata?.streamingState as string | undefined) : undefined;
  const streamingLabel =
    streamingState === 'queued'
      ? 'Streaming queued…'
      : streamingState === 'streaming'
        ? 'Streaming…'
        : streamingState === 'fallback'
          ? 'Streaming (fallback)'
          : streamingState === 'error'
            ? 'Streaming failed'
            : undefined;

  const deliveryState = message.delivery;

  return (
    <article className={clsx('group relative flex w-full items-start gap-4 py-5', alignmentClass)}>
      <div
        className={clsx(
          'flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-surface-muted text-foreground shadow-lg',
          isUser && 'bg-accent text-accent-foreground',
        )}
      >
        {isUser ? (
          <User2 className="h-5 w-5" aria-hidden />
        ) : (
          <div 
            className="h-5 w-5 bg-accent"
            style={{
              maskImage: 'url(/camarad.svg)',
              maskSize: 'contain',
              maskRepeat: 'no-repeat',
              maskPosition: 'center',
              WebkitMaskImage: 'url(/camarad.svg)',
              WebkitMaskSize: 'contain',
              WebkitMaskRepeat: 'no-repeat',
              WebkitMaskPosition: 'center',
            }}
            aria-label="Camarad"
          />
        )}
      </div>
      <div className="flex max-w-3xl flex-col gap-3">
        <div
          className={clsx(
            'flex items-center gap-3 text-xs uppercase tracking-[0.3em] text-muted-foreground/70',
            isUser ? 'justify-end' : 'justify-start',
          )}
        >
          <span>{isUser ? 'You' : 'Camarad'}</span>
          <span className="font-medium tracking-[0.2em] text-muted-foreground/50">•</span>
          <time dateTime={message.createdAt}>{metaTime}</time>
        </div>
        <div className={bubbleClasses}>
          <div className="space-y-3">{renderContent(message.content)}</div>
          {deliveryState === 'pending' && (
            <div className="mt-3 text-xs text-accent-foreground/80">Working on a reply…</div>
          )}
          {deliveryState === 'error' && (
            <div className="mt-3 text-xs text-danger">Unable to deliver message. Try again shortly.</div>
          )}
          {streamingLabel && (
            <div className="mt-3 text-xs text-muted-foreground/80">{streamingLabel}</div>
          )}
          {forwardedLabel && <div className="mt-4 text-xs text-muted-foreground/80">{forwardedLabel}</div>}
        </div>
      </div>
      {onForward && (
        <div className="absolute -top-4 flex w-full justify-center opacity-0 transition group-hover:opacity-100">
          <button
            type="button"
            onClick={() => onForward(message)}
            className="inline-flex items-center gap-2 rounded-full bg-background/95 px-3 py-1.5 text-xs font-semibold text-muted-foreground shadow-lg transition hover:text-accent focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
          >
            Forward to…
            <CornerUpRight className="h-3.5 w-3.5" aria-hidden />
          </button>
        </div>
      )}
    </article>
  );
}
