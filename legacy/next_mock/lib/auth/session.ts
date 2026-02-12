/**
 * Mock session management
 * In production, this would integrate with your backend auth system
 */

export interface Session {
  user: {
    id: string;
    name: string;
    email: string;
    avatar?: string;
  };
  expiresAt: number;
}

const SESSION_KEY = 'camarad_session';

export function getSession(): Session | null {
  if (typeof window === 'undefined') return null;
  
  try {
    const stored = localStorage.getItem(SESSION_KEY);
    if (!stored) return null;
    
    const session: Session = JSON.parse(stored);
    
    // Check if expired
    if (Date.now() > session.expiresAt) {
      clearSession();
      return null;
    }
    
    return session;
  } catch {
    return null;
  }
}

export function setSession(user: Session['user']): void {
  const session: Session = {
    user,
    expiresAt: Date.now() + 7 * 24 * 60 * 60 * 1000, // 7 days
  };
  
  localStorage.setItem(SESSION_KEY, JSON.stringify(session));
}

export function clearSession(): void {
  localStorage.removeItem(SESSION_KEY);
}

export function isAuthenticated(): boolean {
  return getSession() !== null;
}

/**
 * Mock login - replace with actual API call
 */
export async function login(email: string, password: string): Promise<{ success: boolean; error?: string }> {
  // Simulate API delay
  await new Promise(resolve => setTimeout(resolve, 800));
  
  // Mock validation
  if (!email || !password) {
    return { success: false, error: 'Email and password required' };
  }
  
  if (password.length < 6) {
    return { success: false, error: 'Password must be at least 6 characters' };
  }
  
  // Create mock session
  setSession({
    id: 'user-001',
    name: email.split('@')[0],
    email,
    avatar: undefined,
  });
  
  return { success: true };
}

/**
 * Mock register - replace with actual API call
 */
export async function register(name: string, email: string, password: string): Promise<{ success: boolean; error?: string }> {
  await new Promise(resolve => setTimeout(resolve, 800));
  
  if (!name || !email || !password) {
    return { success: false, error: 'All fields required' };
  }
  
  if (password.length < 6) {
    return { success: false, error: 'Password must be at least 6 characters' };
  }
  
  // Create mock session
  setSession({
    id: 'user-' + Date.now(),
    name,
    email,
    avatar: undefined,
  });
  
  return { success: true };
}

/**
 * Mock OAuth login
 */
export async function loginWithGoogle(): Promise<void> {
  // In production, redirect to OAuth provider
  // For now, create mock session
  setSession({
    id: 'user-google-' + Date.now(),
    name: 'Google User',
    email: 'user@gmail.com',
    avatar: undefined,
  });
}
