import { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import { User, Briefcase, Users, Code } from 'lucide-react';
import { isAuthenticated } from '@/lib/auth/session';
import { WORKSPACE_TEMPLATES } from '@/lib/config/workspaces';
import { useOnboarding } from '@/lib/state/onboarding';
import type { WorkspaceType } from '@/lib/types/workspace';

const iconMap = {
  personal: User,
  business: Briefcase,
  agency: Users,
  developer: Code,
};

export default function OnboardingWorkspacePage() {
  const router = useRouter();
  const [mounted, setMounted] = useState(false);
  const { setWorkspace } = useOnboarding();
  const [selectedType, setSelectedType] = useState<WorkspaceType>('personal');
  const [workspaceName, setWorkspaceName] = useState('');

  useEffect(() => {
    setMounted(true);
    if (!isAuthenticated()) {
      router.replace('/login');
    }
  }, [router]);

  if (!mounted || !isAuthenticated()) return null;

  const handleContinue = () => {
    if (!workspaceName.trim()) return;
    
    setWorkspace({
      name: workspaceName.trim(),
      type: selectedType,
    });
    
    router.push('/onboarding/agents');
  };

  const handleBack = () => {
    router.back();
  };

  const canContinue = workspaceName.trim().length > 0;

  return (
    <div className="min-h-screen bg-background text-foreground px-6 py-12">
      <div className="max-w-3xl mx-auto">
        {/* Progress */}
        <div className="flex items-center justify-center gap-2 mb-12">
          <div className="w-2 h-2 rounded-full bg-accent"></div>
          <div className="w-2 h-2 rounded-full bg-accent"></div>
          <div className="w-2 h-2 rounded-full bg-muted"></div>
          <div className="w-2 h-2 rounded-full bg-muted"></div>
          <div className="w-2 h-2 rounded-full bg-muted"></div>
        </div>

        {/* Title */}
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold mb-3">Create your first workspace</h1>
          <p className="text-muted-foreground text-lg">
            Give it a name and choose a type
          </p>
        </div>

        {/* Workspace Name */}
        <div className="mb-8">
          <label htmlFor="workspace-name" className="block text-sm font-medium mb-2">
            Workspace name
          </label>
          <input
            id="workspace-name"
            type="text"
            value={workspaceName}
            onChange={(e) => setWorkspaceName(e.target.value)}
            className="w-full rounded-lg border border-border bg-background px-4 py-3 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-accent"
            placeholder="My Workspace"
            autoFocus
          />
        </div>

        {/* Workspace Type */}
        <div className="mb-12">
          <label className="block text-sm font-medium mb-4">Workspace type</label>
          <div className="grid md:grid-cols-2 gap-4">
            {WORKSPACE_TEMPLATES.map((template) => {
              const Icon = iconMap[template.type];
              const isSelected = selectedType === template.type;
              
              return (
                <button
                  key={template.type}
                  onClick={() => setSelectedType(template.type)}
                  className={`relative rounded-2xl border-2 p-6 text-left transition-all ${
                    isSelected
                      ? 'border-accent bg-accent/5'
                      : 'border-border bg-surface/40 hover:border-border/60'
                  }`}
                >
                  <div className="flex items-start gap-4">
                    <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${
                      isSelected
                        ? 'bg-accent text-white'
                        : 'bg-muted text-muted-foreground'
                    }`}>
                      <Icon className="w-6 h-6" />
                    </div>
                    
                    <div className="flex-1">
                      <h3 className="text-lg font-bold mb-1">{template.label}</h3>
                      <p className="text-sm text-muted-foreground mb-2">{template.description}</p>
                      <div className="flex flex-wrap gap-1">
                        {template.recommendedFor.map((tag, i) => (
                          <span key={i} className="text-xs px-2 py-0.5 rounded bg-muted/40 text-muted-foreground">
                            {tag}
                          </span>
                        ))}
                      </div>
                    </div>

                    {isSelected && (
                      <div className="w-5 h-5 rounded-full bg-accent flex items-center justify-center flex-shrink-0">
                        <div className="w-2 h-2 rounded-full bg-white"></div>
                      </div>
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center justify-center gap-4">
          <button
            onClick={handleBack}
            className="rounded-lg border border-border px-8 py-3 font-semibold hover:bg-surface/60 transition-colors"
          >
            Back
          </button>
          <button
            onClick={handleContinue}
            disabled={!canContinue}
            className="rounded-lg bg-accent px-8 py-3 font-semibold text-white hover:bg-accent/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Continue
          </button>
        </div>
      </div>
    </div>
  );
}
