import { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import { Check, Loader2 } from 'lucide-react';
import { isAuthenticated } from '@/lib/auth/session';
import { useOnboarding } from '@/lib/state/onboarding';

export default function OnboardingCompletePage() {
  const router = useRouter();
  const [mounted, setMounted] = useState(false);
  const [completing, setCompleting] = useState(true);
  const { planId, workspace, selectedAgentPresetIds, preferences, resetOnboarding } = useOnboarding();

  useEffect(() => {
    setMounted(true);
    if (!isAuthenticated()) {
      router.replace('/login');
      return;
    }

    // Submit onboarding data to backend
    const submitOnboarding = async () => {
      try {
        // TODO: Replace with real API call
        // await fetch('/api/onboarding/complete', {
        //   method: 'POST',
        //   body: JSON.stringify({ planId, workspace, selectedAgentPresetIds, preferences }),
        // });
        
        // Simulate API call
        await new Promise(resolve => setTimeout(resolve, 2000));
        
        setCompleting(false);
      } catch (error) {
        console.error('Failed to complete onboarding:', error);
        setCompleting(false);
      }
    };

    submitOnboarding();
  }, [router, planId, workspace, selectedAgentPresetIds, preferences]);

  if (!mounted || !isAuthenticated()) return null;

  const handleFinish = () => {
    // Clear onboarding state
    resetOnboarding();
    
    // Mark onboarding as complete
    localStorage.setItem('onboarding_complete', 'true');
    
    // Redirect to first workspace
    const workspaceType = workspace?.type || 'personal';
    router.push(`/p/${workspaceType}`);
  };

  return (
    <div className="min-h-screen bg-background text-foreground px-6 py-12 flex items-center justify-center">
      <div className="max-w-md w-full text-center">
        {completing ? (
          <>
            {/* Loading State */}
            <div className="mb-8">
              <div className="w-20 h-20 rounded-full bg-gradient-to-br from-cyan-500 to-violet-500 flex items-center justify-center mx-auto mb-6 animate-pulse">
                <Loader2 className="w-10 h-10 text-white animate-spin" />
              </div>
              <h1 className="text-3xl font-bold mb-3">Setting up your workspace</h1>
              <p className="text-muted-foreground">This will only take a moment...</p>
            </div>

            {/* Progress dots */}
            <div className="flex items-center justify-center gap-2">
              <div className="w-2 h-2 rounded-full bg-accent animate-pulse"></div>
              <div className="w-2 h-2 rounded-full bg-accent animate-pulse delay-75"></div>
              <div className="w-2 h-2 rounded-full bg-accent animate-pulse delay-150"></div>
            </div>
          </>
        ) : (
          <>
            {/* Success State */}
            <div className="mb-8">
              <div className="w-20 h-20 rounded-full bg-gradient-to-br from-cyan-500 to-violet-500 flex items-center justify-center mx-auto mb-6">
                <Check className="w-10 h-10 text-white" />
              </div>
              <h1 className="text-3xl font-bold mb-3">You&apos;re all set!</h1>
              <p className="text-muted-foreground mb-8">
                Your workspace is ready. Let&apos;s start building something amazing.
              </p>

              <button
                onClick={handleFinish}
                className="rounded-lg bg-accent px-8 py-3 font-semibold text-white hover:bg-accent/90 transition-colors"
              >
                Go to Dashboard
              </button>
            </div>

            {/* Features preview */}
            <div className="mt-12 space-y-3">
              <div className="flex items-center gap-3 text-sm">
                <div className="w-5 h-5 rounded-full bg-accent/20 flex items-center justify-center flex-shrink-0">
                  <Check className="w-3 h-3 text-accent" />
                </div>
                <span className="text-muted-foreground">Workspace created</span>
              </div>
              <div className="flex items-center gap-3 text-sm">
                <div className="w-5 h-5 rounded-full bg-accent/20 flex items-center justify-center flex-shrink-0">
                  <Check className="w-3 h-3 text-accent" />
                </div>
                <span className="text-muted-foreground">Preferences saved</span>
              </div>
              <div className="flex items-center gap-3 text-sm">
                <div className="w-5 h-5 rounded-full bg-accent/20 flex items-center justify-center flex-shrink-0">
                  <Check className="w-3 h-3 text-accent" />
                </div>
                <span className="text-muted-foreground">Ready to start</span>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
