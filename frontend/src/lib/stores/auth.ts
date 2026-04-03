// auth.ts — Login/logout and auth state store
import { writable } from 'svelte/store';
import { goto } from '$app/navigation';

export const isAuthenticated = writable(false);

export async function login(username: string, password: string): Promise<void> {
  const res = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
    credentials: 'include',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Login failed');
  }
  isAuthenticated.set(true);
  goto('/');
}

export async function logout(): Promise<void> {
  await fetch('/api/auth/logout', { method: 'POST', credentials: 'include' });
  isAuthenticated.set(false);
  goto('/login');
}

export async function checkAuth(): Promise<boolean> {
  try {
    const res = await fetch('/api/live', { credentials: 'include' });
    if (res.ok) {
      isAuthenticated.set(true);
      return true;
    }
  } catch {}
  isAuthenticated.set(false);
  return false;
}
