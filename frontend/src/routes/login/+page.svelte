<script lang="ts">
  import { login } from '$lib/stores/auth';

  let username = '';
  let password = '';
  let error = '';
  let loading = false;

  async function handleSubmit() {
    error = '';
    loading = true;
    try {
      await login(username, password);
    } catch (e: any) {
      error = e.message || 'Anmeldung fehlgeschlagen';
    } finally {
      loading = false;
    }
  }
</script>

<svelte:head><title>Anmelden – Solar Dashboard</title></svelte:head>

<div class="login-page">
  <div class="login-card">
    <div class="logo">☀️</div>
    <h1>Solar Dashboard</h1>
    <p class="subtitle">RCT Power Monitoring</p>

    <form on:submit|preventDefault={handleSubmit}>
      <label>
        <span>Benutzername</span>
        <input type="text" bind:value={username} autocomplete="username" required />
      </label>
      <label>
        <span>Passwort</span>
        <input type="password" bind:value={password} autocomplete="current-password" required />
      </label>
      {#if error}
        <div class="error">{error}</div>
      {/if}
      <button type="submit" class="btn btn-primary" disabled={loading}>
        {loading ? 'Anmelden…' : 'Anmelden'}
      </button>
    </form>
  </div>
</div>

<style>
  .login-page {
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 1rem;
    background: #f5f5f5;
  }
  .login-card {
    background: #fff;
    border-radius: 0.75rem;
    box-shadow: 0 4px 6px rgba(0,0,0,0.07), 0 2px 4px rgba(0,0,0,0.06);
    padding: 2.5rem 2rem;
    width: 100%;
    max-width: 360px;
    text-align: center;
  }
  .logo { font-size: 3rem; margin-bottom: 0.5rem; }
  h1 { margin: 0; font-size: 1.375rem; font-weight: 700; color: #212121; }
  .subtitle { color: #9e9e9e; font-size: 0.875rem; margin: 0.25rem 0 1.75rem; }
  form { display: flex; flex-direction: column; gap: 1rem; text-align: left; }
  label span { display: block; font-size: 0.75rem; font-weight: 600; color: #757575; margin-bottom: 0.3rem; text-transform: uppercase; letter-spacing: 0.04em; }
  .error { color: #dc2626; font-size: 0.8rem; background: #fef2f2; padding: 0.5rem 0.75rem; border-radius: 0.375rem; }
  .btn-primary { width: 100%; margin-top: 0.25rem; padding: 0.625rem; font-size: 0.9375rem; }
</style>
