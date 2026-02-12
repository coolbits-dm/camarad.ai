import type { WorkspaceType } from '@/lib/types/workspace';

export interface WorkspaceTemplate {
  type: WorkspaceType;
  label: string;
  description: string;
  recommendedFor: string[];
}

export const WORKSPACE_TEMPLATES: WorkspaceTemplate[] = [
  {
    type: 'personal',
    label: 'Personal',
    description: 'For your own projects, learning, and planning.',
    recommendedFor: ['Creators', 'Freelancers', 'Students'],
  },
  {
    type: 'business',
    label: 'Business',
    description: 'For one company or product line.',
    recommendedFor: ['Startups', 'Small businesses'],
  },
  {
    type: 'agency',
    label: 'Agency',
    description: 'For managing multiple client accounts.',
    recommendedFor: ['Marketing agencies', 'Consultants'],
  },
  {
    type: 'developer',
    label: 'Developer',
    description: 'For technical workflows and automation.',
    recommendedFor: ['Engineers', 'Tech leads'],
  },
];
