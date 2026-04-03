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
        <input
          type="text"
          bind:value={username}
          autocomplete="username"
          required
        />
      </label>
      <label>
        <span>Passwort</span>
        <input
          type="password"
          bind:value={password}
          autocomplete="current-password"
          required
        />
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
  }
  .login-card {
    background: #1e293b;
    border-radius: 1rem;
    padding: 2rem;
    width: 100%;
    max-width: 360px;
    text-align: center;
  }
  .logo { font-size: 3rem; margin-bottom: 0.5rem; }
  h1 { margin: 0; font-size: 1.375rem; }
  .subtitle { color: #64748b; font-size: 0.875rem; margin: 0.25rem 0 1.5rem; }
  form { display: flex; flex-direction: column; gap: 0.875rem; text-align: left; }
  label span { display: block; font-size: 0.75rem; color: #94a3b8; margin-bottom: 0.3rem; }
  .error { color: #ef4444; font-size: 0.8rem; }
  .btn-primary { width: 100%; margin-top: 0.25rem; }
</style>
