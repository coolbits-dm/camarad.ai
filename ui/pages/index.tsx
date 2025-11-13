import { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import Link from 'next/link';
import { Leaf } from 'lucide-react';
import { isAuthenticated } from '@/lib/auth/session';

export default function LandingPage() {
  const router = useRouter();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    // Redirect if already logged in
    if (isAuthenticated()) {
      router.replace('/p/personal');
    }
  }, [router]);

  if (!mounted) return null;
  
  if (isAuthenticated()) {
    return null; // Will redirect
  }

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col">
      {/* Header */}
      <header className="fixed top-0 left-0 right-0 z-50 border-b border-border/40 bg-background/80 backdrop-blur-xl">
        <div className="container mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-500 to-violet-500 flex items-center justify-center">
              <span className="text-white font-bold text-sm">C</span>
            </div>
            <span className="text-lg font-semibold">Camarad</span>
          </div>
          
          <Link
            href="/login"
            className="text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            Login
          </Link>
        </div>
      </header>

      {/* Hero Section */}
      <main className="flex-1 flex items-center justify-center px-6 pt-16">
        <div className="max-w-5xl w-full text-center space-y-8 py-20">
          {/* Logo */}
          <div className="flex justify-center mb-8">
            <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-cyan-500 via-blue-500 to-violet-500 flex items-center justify-center shadow-2xl">
              <span className="text-white font-bold text-3xl">C</span>
            </div>
          </div>

          {/* Headline */}
          <h1 className="text-5xl md:text-7xl font-bold tracking-tight">
            <span className="bg-gradient-to-r from-cyan-400 via-blue-400 to-violet-400 bg-clip-text text-transparent">
              AI Development
            </span>
            {' '}
            <span className="bg-gradient-to-r from-violet-400 via-purple-400 to-pink-400 bg-clip-text text-transparent">
              Studio
            </span>
          </h1>

          {/* Subheadline */}
          <p className="text-xl md:text-2xl text-muted-foreground max-w-3xl mx-auto leading-relaxed">
            Build intelligent workflows with AI agents and automation.
          </p>

          {/* CTA */}
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4 pt-4">
            <Link
              href="/register"
              className="px-8 py-4 rounded-xl bg-gradient-to-r from-cyan-500 to-violet-500 text-white font-semibold text-lg hover:shadow-2xl hover:shadow-cyan-500/20 transition-all duration-300 hover:scale-105"
            >
              Start now
            </Link>
            <Link
              href="/login"
              className="px-8 py-4 rounded-xl border-2 border-border hover:border-accent text-foreground font-semibold text-lg transition-all duration-300 hover:bg-surface/40"
            >
              Sign in
            </Link>
          </div>

          {/* Video */}
          <div className="mt-16 flex justify-center">
            <div className="w-full max-w-2xl rounded-xl overflow-hidden border-2 border-border/60 bg-surface/20 backdrop-blur-sm shadow-2xl">
              <div className="aspect-video">
                <iframe
                  width="100%"
                  height="100%"
                  src="https://www.youtube.com/embed/yD4RwPi1RUk"
                  title="Camarad Demo"
                  allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                  allowFullScreen
                  className="w-full h-full"
                ></iframe>
              </div>
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-border/40 py-12 px-6">
        <div className="container mx-auto max-w-5xl">
          <div className="flex flex-col items-center gap-6 text-center">
            {/* Links */}
            <div className="flex flex-wrap items-center justify-center gap-6 text-sm text-muted-foreground">
              <Link href="/about" className="hover:text-foreground transition-colors">About</Link>
              <Link href="/legal" className="hover:text-foreground transition-colors">Legal</Link>
              <Link href="/privacy" className="hover:text-foreground transition-colors">Privacy</Link>
              <Link href="/terms" className="hover:text-foreground transition-colors">Terms</Link>
              <Link href="/contact" className="hover:text-foreground transition-colors">Contact</Link>
            </div>

            {/* Copyright */}
            <div className="text-sm text-muted-foreground">
              © {new Date().getFullYear()} Coolbits.ai · tag, Ro
            </div>

            {/* Branding */}
            <div className="flex flex-col items-center gap-2 text-sm">
              <div className="text-muted-foreground">
                Powered by{' '}
                <span className="text-cyan-400 font-semibold">CoolBits.ai</span>
                {' · '}
                Backed by{' '}
                <span className="text-violet-400 font-semibold">Stripe</span>
              </div>
              <div className="flex items-center gap-2 text-emerald-400">
                <span>We donate 1% of revenue to remove CO₂</span>
                <Leaf className="w-4 h-4" />
              </div>
              <div className="mt-2 text-xs text-muted-foreground/60">
                Camarad
              </div>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
