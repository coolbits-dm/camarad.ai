export interface ConnectorProviderState {
  provider: string;
  displayName: string;
  status: 'connected' | 'disconnected' | 'error' | string;
  connected: boolean;
  lastSyncedAt?: string;
  accountName?: string;
  details?: Record<string, unknown>;
}

export interface ConnectorStatusResponse {
  providers: Array<
    {
      provider: string;
      display_name?: string;
      status?: string;
      connected?: boolean;
      last_synced_at?: string;
      account_name?: string;
      [key: string]: unknown;
    }
  >;
}
