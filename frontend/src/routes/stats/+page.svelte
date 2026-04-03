<script lang="ts">
  import { onMount } from 'svelte';

  let summary: any[] = [];
  let loading = true;
  let error = '';

  onMount(async () => {
    try {
      const res = await fetch('/api/summary', { credentials: 'include' });
      if (!res.ok) throw new Error('Fehler beim Laden');
      summary = await res.json();
    } catch (e: any) {
      error = e.message;
    } finally {
      loading = false;
    }
  });

  function fmt(v: number | null, dec = 1): string {
    return v !== null && v !== undefined ? v.toFixed(dec) : '–';
  }
</script>

<svelte:head><title>Statistik – Solar Dashboard</title></svelte:head>

<h2>Tagesstatistik</h2>

{#if loading}
  <div class="loading">Lade Statistiken…</div>
{:else if error}
  <div class="error">{error}</div>
{:else if summary.length === 0}
  <div class="empty">Noch keine Tagesdaten vorhanden.</div>
{:else}
  <div class="table-wrapper">
    <table>
      <thead>
        <tr>
          <th>Datum</th>
          <th>☀️ Ertrag</th>
          <th>🔌 Einspeisung</th>
          <th>⬇️ Bezug</th>
          <th>🏠 Verbrauch</th>
          <th>🔋 Bat. Min/Max</th>
        </tr>
      </thead>
      <tbody>
        {#each summary as row}
          <tr>
            <td>{row.date}</td>
            <td class="num amber">{fmt(row.yield_kwh)} kWh</td>
            <td class="num green">{fmt(row.grid_feed_kwh)} kWh</td>
            <td class="num red">{fmt(row.grid_draw_kwh)} kWh</td>
            <td class="num blue">{fmt(row.load_kwh)} kWh</td>
            <td class="num muted">{fmt(row.battery_min_pct, 0)}% / {fmt(row.battery_max_pct, 0)}%</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
{/if}

<style>
  h2 { margin: 0 0 1rem; font-size: 1.125rem; }
  .loading, .empty { color: #94a3b8; padding: 2rem; text-align: center; }
  .error { color: #ef4444; }
  .table-wrapper { overflow-x: auto; }
  table { width: 100%; border-collapse: collapse; font-size: 0.875rem; }
  th { text-align: left; padding: 0.5rem 0.75rem; color: #64748b; border-bottom: 1px solid #334155; white-space: nowrap; }
  td { padding: 0.5rem 0.75rem; border-bottom: 1px solid #1e293b; }
  tr:hover td { background: #1e293b; }
  .num { text-align: right; font-variant-numeric: tabular-nums; }
  .amber { color: #f59e0b; }
  .green { color: #22c55e; }
  .red   { color: #ef4444; }
  .blue  { color: #3b82f6; }
  .muted { color: #94a3b8; }
</style>
