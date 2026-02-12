import '@/styles/globals.css';

import type { AppProps } from 'next/app';
import { Toaster } from 'sonner';

import { AppearanceProvider, FetcherProvider } from '@/components/providers';
import { OnboardingProvider } from '@/lib/state/onboarding';

export default function App({ Component, pageProps }: AppProps) {
  return (
    <AppearanceProvider>
      <FetcherProvider>
        <OnboardingProvider>
          <>
            <Toaster position="top-right" richColors expand theme="system" closeButton />
            <Component {...pageProps} />
          </>
        </OnboardingProvider>
      </FetcherProvider>
    </AppearanceProvider>
  );
}
// Cache bust: 1762929967
