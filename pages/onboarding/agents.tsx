import { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import * as Icons from 'lucide-react';
import { isAuthenticated } from '@/lib/auth/session';
import { useOnboarding } from '@/lib/state/onboarding';
import { getMaxAgents } from '@/lib/limits';
import {
  PERSONAL_AGENT_PRESETS,
  BUSINESS_AGENT_PRESETS,
  AGENCY_AGENT_PRESETS,
  DEVELOPER_AGENT_PRESETS,
} from '@/lib/config/agents';
import type { AgentPreset } from '@/lib/types/agent';

export default function OnboardingAgentsPage() {
  const router = useRouter();
  const [mounted, setMounted] = useState(false);
  const { planId, workspace, selectedAgentPresetIds, setSelectedAgentPresetIds } = useOnboarding();
  const [selected, setSelected] = useState<string[]>(selectedAgentPresetIds || []);

  useEffect(() => {
    setMounted(true);
    if (!isAuthenticated()) {
      router.replace('/login');
      return;
    }
    if (!planId || !workspace) {
      router.replace('/onboarding/plan');
    }
  }, [router, planId, workspace]);

  if (!mounted || !isAuthenticated() || !planId || !workspace) return null;

  // Get agent presets based on workspace type
  const getPresetsForWorkspace = (): AgentPreset[] => {
    switch (workspace.type) {
      case 'personal':
        return PERSONAL_AGENT_PRESETS;
      case 'business':
        return BUSINESS_AGENT_PRESETS;
      case 'agency':
        return AGENCY_AGENT_PRESETS;
      case 'developer':
        return DEVELOPER_AGENT_PRESETS;
      default:
        return PERSONAL_AGENT_PRESETS;
    }
  };

  const availablePresets = getPresetsForWorkspace();
  const maxAgents = getMaxAgents(planId);
  const maxSelection = typeof maxAgents === 'number' ? maxAgents : availablePresets.length;

  const toggleAgent = (presetId: string) => {
    setSelected((prev) => {
      if (prev.includes(presetId)) {
        return prev.filter((id) => id !== presetId);
      } else if (prev.length < maxSelection) {
        return [...prev, presetId];
      }
      return prev;
    });
  };

  const handleContinue = () => {
    if (selected.length === 0) return;
    
    setSelectedAgentPresetIds(selected);
    router.push('/onboarding/preferences');
  };

  const handleBack = () => {
    router.back();
  };

  const canContinue = selected.length > 0;

  return (
    <div className="min-h-screen bg-background text-foreground px-6 py-12">
      <div className="max-w-4xl mx-auto">
        {/* Progress */}
        <div className="flex items-center justify-center gap-2 mb-12">
          <div className="w-2 h-2 rounded-full bg-accent"></div>
          <div className="w-2 h-2 rounded-full bg-accent"></div>
          <div className="w-2 h-2 rounded-full bg-accent"></div>
          <div className="w-2 h-2 rounded-full bg-muted"></div>
          <div className="w-2 h-2 rounded-full bg-muted"></div>
        </div>

        {/* Title */}
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold mb-3">Choose your AI agents</h1>
          <p className="text-muted-foreground text-lg">
            Select up to {maxSelection} agents for {workspace.name}
          </p>
          <p className="text-sm text-muted-foreground mt-2">
            {selected.length} of {maxSelection} selected
          </p>
        </div>

        {/* Agent Presets */}
        <div className="grid md:grid-cols-2 gap-4 mb-12">
          {availablePresets.map((preset) => {
            const isSelected = selected.includes(preset.id);
            const IconComponent = (Icons as any)[preset.icon.split('-').map((w: string) => 
              w.charAt(0).toUpperCase() + w.slice(1)
            ).join('')] || Icons.Circle;
            
            return (
              <button
                key={preset.id}
                onClick={() => toggleAgent(preset.id)}
                className={`relative rounded-2xl border-2 p-6 text-left transition-all ${
                  isSelected
                    ? 'border-accent bg-accent/5'
                    : 'border-border bg-surface/40 hover:border-border/60'
                }`}
              >
                <div className="flex items-start gap-4">
                  <div className={`w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0 ${
                    isSelected
                      ? 'bg-accent text-white'
                      : 'bg-muted text-muted-foreground'
                  }`}>
                    <IconComponent className="w-6 h-6" />
                  </div>
                  
                  <div className="flex-1 min-w-0">
                    <h3 className="text-lg font-bold mb-1">{preset.name}</h3>
                    <p className="text-sm text-muted-foreground">{preset.description}</p>
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
