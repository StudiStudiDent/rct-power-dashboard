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
    padding: 0.75rem 1rem;
    background: #1e293b;
    border-bottom: 1px solid #334155;
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
  .logo { font-size: 1rem; font-weight: 700; }
  nav { display: flex; gap: 0.25rem; }
  nav a {
    padding: 0.375rem 0.75rem;
    border-radius: 0.375rem;
    font-size: 0.875rem;
    color: #94a3b8;
    transition: all 0.15s;
  }
  nav a:hover, nav a.active {
    background: #334155;
    color: #f1f5f9;
  }
  .logout { font-size: 0.75rem; padding: 0.375rem 0.75rem; }
  main { flex: 1; padding: 1rem; max-width: 900px; margin: 0 auto; width: 100%; }
</style>
