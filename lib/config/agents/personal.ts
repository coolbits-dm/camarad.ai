import type { AgentPreset } from '@/lib/types/agent';

export const PERSONAL_AGENT_PRESETS: AgentPreset[] = [
  {
    id: 'coach',
    domain: 'lifestyle',
    name: 'Life Coach',
    description: 'Goal setting, planning, and weekly reviews.',
    icon: 'target',
    defaultRolePrompt: 'Act as a structured life coach tracking goals, habits, and weekly reflections.',
  },
  {
    id: 'psychologist',
    domain: 'lifestyle',
    name: 'Mindspace',
    description: 'Helps you reflect and decompose mental noise.',
    icon: 'brain',
    defaultRolePrompt: 'Act as a calm, neutral listener that helps the user name emotions and deconstruct patterns.',
  },
  {
    id: 'finance',
    domain: 'lifestyle',
    name: 'Finance Advisor',
    description: 'Budgets, cashflow, and small investment plans.',
    icon: 'wallet',
    defaultRolePrompt: 'Help the user track income/expenses and propose simple monthly budgets.',
  },
  {
    id: 'learning',
    domain: 'lifestyle',
    name: 'Learning Mentor',
    description: 'Explains topics and builds learning plans.',
    icon: 'book-open',
    defaultRolePrompt: 'Guide the user with curated learning paths and spaced repetition.',
  },
  {
    id: 'productivity',
    domain: 'lifestyle',
    name: 'Workflow Assistant',
    description: 'Tasks, checklists, and process optimization.',
    icon: 'list-checks',
    defaultRolePrompt: 'Help the user break goals into tasks, prioritize, and review progress.',
  },
];
