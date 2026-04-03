<script lang="ts">
  import '../app.css';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { onMount } from 'svelte';
  import { checkAuth, logout } from '$lib/stores/auth';
  import StatusBadge from '$lib/components/StatusBadge.svelte';

  onMount(async () => {
    const ok = await checkAuth();
    if (!ok && $page.url.pathname !== '/login') {
      goto('/login');
    }
  });

  const navItems = [
    { href: '/',        label: '⚡ Live'      },
    { href: '/history', label: '📈 Verlauf'   },
    { href: '/stats',   label: '📊 Statistik' },
  ];
</script>

<div class="app-shell">
  <header>
    <div class="header-left">
      <span class="logo">☀️ Solar</span>
      <StatusBadge />
    </div>
    <nav>
      {#each navItems as item}
        <a
          href={item.href}
          class:active={$page.url.pathname === item.href}
        >{item.label}</a>
      {/each}
    </nav>
    <button class="btn btn-ghost logout" on:click={logout}>Logout</button>
  </header>

  <main>
    <slot />
  </main>
</div>

<style>
  .app-shell {
    display: flex;
    flex-direction: column;
    min-height: 100vh;
  }
  header {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 0 1rem;
    height: 56px;
    background: #ffffff;
    border-bottom: 1px solid #e0e0e0;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    position: sticky;
    top: 0;
    z-index: 10;
    flex-wrap: wrap;
  }
  .header-left {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex: 1;
  }
  .logo { font-size: 0.9375rem; font-weight: 700; color: #212121; letter-spacing: -0.01em; }
  nav { display: flex; gap: 0.125rem; }
  nav a {
    padding: 0.375rem 0.875rem;
    border-radius: 0.375rem;
    font-size: 0.875rem;
    font-weight: 500;
    color: #757575;
    transition: all 0.15s;
  }
  nav a:hover { background: #f5f5f5; color: #212121; }
  nav a.active { background: #fff8e1; color: #f59e0b; font-weight: 600; }
  .logout { font-size: 0.75rem; padding: 0.375rem 0.75rem; }
  main { flex: 1; padding: 1.25rem 1rem; max-width: 900px; margin: 0 auto; width: 100%; }
</style>
