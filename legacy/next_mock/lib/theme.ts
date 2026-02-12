export const ACCENT_STORAGE_KEY = 'camarad:v1:accent';

export const ACCENT_OPTIONS = [
  { id: 'violet', label: 'Violet', rgb: '139 92 246' },
  { id: 'cyan', label: 'Cyan', rgb: '34 211 238' },
  { id: 'emerald', label: 'Emerald', rgb: '16 185 129' },
  { id: 'amber', label: 'Amber', rgb: '245 158 11' },
  { id: 'rose', label: 'Rose', rgb: '244 63 94' }
] as const;

export type AccentId = (typeof ACCENT_OPTIONS)[number]['id'];

export const DEFAULT_ACCENT: AccentId = 'violet';

export const THEME_OPTIONS = ['light', 'dark'] as const;
export type ThemeId = (typeof THEME_OPTIONS)[number];
