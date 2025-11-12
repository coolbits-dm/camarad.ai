import type { PanelKey } from '@/lib/panels';

export type MessageRole = 'user' | 'assistant' | 'system' | 'context' | 'note';

export interface MessageMetadata {
  hidden?: boolean;
  forwardedTo?: string[];
  memory?: boolean;
  source?: string;
  contextId?: string;
  councilMemberId?: string;
  councilMemberName?: string;
  tags?: string[];
  streamingState?: 'queued' | 'streaming' | 'completed' | 'fallback' | 'error';
  traceId?: string;
  tokensUsed?: number;
  retrieved?: RagMatch[];
  error?: string;
}

export type MessageDeliveryState = 'idle' | 'pending' | 'error';

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  createdAt: string;
  delivery?: MessageDeliveryState;
  metadata?: MessageMetadata;
}

export interface ChatSession {
  id: string;
  panel: PanelKey;
  title: string;
  createdAt: string;
  updatedAt: string;
  messages: ChatMessage[];
  memoryCount?: number;
  summary?: string;
}

export interface RagMatch {
  id: string;
  content: string;
  score: number;
  source?: string;
}

export interface CouncilMember {
  id: string;
  name: string;
  handle: string;
  specialty?: string;
  panel: PanelKey;
}
