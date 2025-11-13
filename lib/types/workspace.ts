export type WorkspaceType = 'personal' | 'business' | 'agency' | 'developer';

export interface Workspace {
  id: string;
  ownerId: string;
  type: WorkspaceType;
  name: string;
  createdAt: string;
  isActive: boolean;
}
