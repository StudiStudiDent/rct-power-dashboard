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
  h2 { margin: 0 0 1rem; font-size: 1.125rem; font-weight: 600; color: #212121; }
  .loading, .empty { color: #757575; padding: 2rem; text-align: center; }
  .error { color: #dc2626; }
  .table-wrapper {
    background: #fff;
    border-radius: 0.75rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.08);
    overflow: hidden;
  }
  table { width: 100%; border-collapse: collapse; font-size: 0.875rem; }
  th { text-align: left; padding: 0.75rem 1rem; color: #757575; font-weight: 600;
       font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.04em;
       border-bottom: 2px solid #e0e0e0; white-space: nowrap; background: #fafafa; }
  td { padding: 0.625rem 1rem; border-bottom: 1px solid #f5f5f5; color: #212121; }
  tr:last-child td { border-bottom: none; }
  tr:hover td { background: #fafafa; }
  .num { text-align: right; font-variant-numeric: tabular-nums; font-weight: 500; }
  .amber { color: #f59e0b; }
  .green { color: #16a34a; }
  .red   { color: #dc2626; }
  .blue  { color: #1d4ed8; }
  .muted { color: #757575; }
</style>
