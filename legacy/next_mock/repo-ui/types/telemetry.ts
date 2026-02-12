export interface TelemetryEvent {
  id?: string;
  scope?: string;
  type: string;
  status?: string;
  enqueued_at?: string;
  updated_at?: string;
  [key: string]: unknown;
}

export interface PanelBalances {
  [panel: string]: number;
}

export interface TelemetryMetrics {
  panel_balances?: PanelBalances;
  [key: string]: unknown;
}

export interface TelemetryLedger {
  metrics?: TelemetryMetrics;
  [key: string]: unknown;
}

export interface TelemetryHealth {
  status?: string;
  services?: Record<string, string>;
  [key: string]: unknown;
}

export interface TelemetrySnapshot {
  ledger?: TelemetryLedger;
  events?: TelemetryEvent[];
  log_tail?: string[] | string;
  health?: TelemetryHealth;
  [key: string]: unknown;
}
