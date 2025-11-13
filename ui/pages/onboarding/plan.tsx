import { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import { Check } from 'lucide-react';
import { isAuthenticated } from '@/lib/auth/session';
import { PLANS } from '@/lib/config/plans';
import { useOnboarding } from '@/lib/state/onboarding';

export default function OnboardingPlanPage() {
  const router = useRouter();
  const [mounted, setMounted] = useState(false);
  const { setPlanId } = useOnboarding();
  const [selectedPlan, setSelectedPlan] = useState('business');

  useEffect(() => {
    setMounted(true);
    if (!isAuthenticated()) {
      router.replace('/login');
    }
  }, [router]);

  if (!mounted || !isAuthenticated()) return null;

  const handleContinue = () => {
    setPlanId(selectedPlan as any);
    router.push('/onboarding/workspace');
  };

  return (
    <div className="min-h-screen bg-background text-foreground px-6 py-12">
      <div className="max-w-6xl mx-auto">
        {/* Progress */}
        <div className="flex items-center justify-center gap-2 mb-12">
          <div className="w-2 h-2 rounded-full bg-accent"></div>
          <div className="w-2 h-2 rounded-full bg-muted"></div>
          <div className="w-2 h-2 rounded-full bg-muted"></div>
          <div className="w-2 h-2 rounded-full bg-muted"></div>
          <div className="w-2 h-2 rounded-full bg-muted"></div>
        </div>

        {/* Title */}
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold mb-3">Choose your plan</h1>
          <p className="text-muted-foreground text-lg">
            All plans include a 15-day free trial
          </p>
        </div>

        {/* Plans */}
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6 mb-12">
          {PLANS.map((plan) => {
            const isPopular = plan.id === 'business';
            const priceDisplay = typeof plan.pricePerMonth === 'number' 
              ? `$${plan.pricePerMonth}` 
              : 'Contact us';
            
            return (
              <button
                key={plan.id}
                onClick={() => setSelectedPlan(plan.id)}
                className={`relative rounded-2xl border-2 p-6 text-left transition-all ${
                  selectedPlan === plan.id
                    ? 'border-accent bg-accent/5'
                    : 'border-border bg-surface/40 hover:border-border/60'
                }`}
              >
                {isPopular && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full bg-gradient-to-r from-cyan-500 to-violet-500 text-xs font-semibold text-white">
                    Popular
                  </div>
                )}
                
                <div className="mb-4">
                  <h3 className="text-xl font-bold mb-1">{plan.name}</h3>
                  <div className="flex items-baseline gap-1 mb-2">
                    <span className="text-3xl font-bold">{priceDisplay}</span>
                    {typeof plan.pricePerMonth === 'number' && (
                      <span className="text-muted-foreground">/month</span>
                    )}
                  </div>
                  <p className="text-sm text-muted-foreground">{plan.description}</p>
                </div>

                <div className="space-y-3 mb-4">
                  <div className="flex items-center gap-2 text-sm">
                    <div className="w-5 h-5 rounded-full bg-accent/20 flex items-center justify-center flex-shrink-0">
                      <Check className="w-3 h-3 text-accent" />
                    </div>
                    <span className="text-xs font-medium text-accent">
                      {plan.trialDays}-day free trial
                    </span>
                  </div>
                </div>

                <ul className="space-y-2">
                  {plan.features.map((feature, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm">
                      <Check className="w-4 h-4 text-accent mt-0.5 flex-shrink-0" />
                      <span>{feature}</span>
                    </li>
                  ))}
                </ul>

                {selectedPlan === plan.id && (
                  <div className="absolute top-4 right-4">
                    <div className="w-6 h-6 rounded-full bg-accent flex items-center justify-center">
                      <Check className="w-4 h-4 text-white" />
                    </div>
                  </div>
                )}
              </button>
            );
          })}
        </div>

        {/* Actions */}
        <div className="flex items-center justify-center gap-4">
          <button
            onClick={handleContinue}
            className="rounded-lg bg-accent px-8 py-3 font-semibold text-white hover:bg-accent/90 transition-colors"
          >
            Continue
          </button>
        </div>
      </div>
    </div>
  );
}
