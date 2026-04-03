<script lang="ts">
  import { dataAge, isStale } from '$lib/stores/live';

  // Reactive: update display every second
  let now = Date.now();
  const interval = setInterval(() => (now = Date.now()), 1000);

  import { onDestroy } from 'svelte';
  onDestroy(() => clearInterval(interval));

  function formatAge(seconds: number | null): string {
    if (seconds === null) return '–';
    if (seconds < 60) return `vor ${seconds}s`;
    if (seconds < 3600) return `vor ${Math.floor(seconds / 60)}min`;
    return `vor ${Math.floor(seconds / 3600)}h`;
  }
</script>

<!-- Stale data indicator — shown in header -->
<span class="status-badge" class:stale={$isStale} title="Zuletzt aktualisiert">
  {#if $dataAge === null}
    <span class="dot unknown">●</span> Warte auf Daten...
  {:else if $isStale}
    <span class="dot stale">●</span> Zuletzt: {formatAge($dataAge)}
  {:else}
    <span class="dot live">●</span> Live · {formatAge($dataAge)}
  {/if}
</span>

<style>
  .status-badge {
    font-size: 0.75rem;
    display: flex;
    align-items: center;
    gap: 0.25rem;
    color: #94a3b8;
  }
  .dot { font-size: 0.6rem; }
  .dot.live  { color: #22c55e; }
  .dot.stale { color: #ef4444; }
  .dot.unknown { color: #64748b; }
  .status-badge.stale { color: #fca5a5; }
</style>
