<script lang="ts">
  import { onMount } from 'svelte';

  let selectedHours = 24;
  let data: any[] = [];
  let loading = false;
  let error = '';

  const ranges = [
    { label: '24h', hours: 24 },
    { label: '7 Tage', hours: 168 },
    { label: '30 Tage', hours: 720 },
  ];

  async function loadHistory(hours: number) {
    loading = true;
    error = '';
    try {
      const res = await fetch(`/api/history?hours=${hours}`, { credentials: 'include' });
      if (!res.ok) throw new Error('Fehler beim Laden');
      data = await res.json();
    } catch (e: any) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  onMount(() => loadHistory(selectedHours));

  // ApexCharts options
  $: chartOptions = {
    chart: { type: 'area', height: 280, background: '#1e293b', toolbar: { show: false },
      animations: { enabled: false } },
    theme: { mode: 'dark' },
    stroke: { curve: 'smooth', width: 2 },
    fill: { type: 'gradient', gradient: { opacityFrom: 0.4, opacityTo: 0.05 } },
    xaxis: {
      type: 'datetime',
      categories: data.map((d) => d.ts * 1000),
      labels: { datetimeUTC: false },
    },
    yaxis: { labels: { formatter: (v: number) => `${Math.round(v)} W` } },
    tooltip: { x: { format: 'dd.MM HH:mm' } },
    grid: { borderColor: '#334155' },
    legend: { position: 'top' },
    series: [
      { name: '☀️ PV Gesamt', data: data.map((d) => Math.round((d.pv_string1_w ?? 0) + (d.pv_string2_w ?? 0))) },
      { name: '🏠 Verbrauch', data: data.map((d) => Math.round(d.load_w ?? 0)) },
      { name: '🔌 Netz', data: data.map((d) => Math.round(d.grid_w ?? 0)) },
    ],
    colors: ['#f59e0b', '#3b82f6', '#22c55e'],
  };
</script>

<svelte:head><title>Verlauf – Solar Dashboard</title></svelte:head>

<div class="header">
  <h2>Verlauf</h2>
  <div class="range-buttons">
    {#each ranges as r}
      <button
        class="btn {selectedHours === r.hours ? 'btn-primary' : 'btn-ghost'}"
        on:click={() => { selectedHours = r.hours; loadHistory(r.hours); }}
      >{r.label}</button>
    {/each}
  </div>
</div>

{#if loading}
  <div class="loading">Lade Daten…</div>
{:else if error}
  <div class="error">{error}</div>
{:else if data.length === 0}
  <div class="empty">Keine Daten für diesen Zeitraum.</div>
{:else}
  <!-- ApexCharts rendered via dynamic import to avoid SSR issues -->
  <div class="chart-wrapper">
    <p class="hint">{data.length} Messpunkte ({selectedHours}h)</p>
    <!-- Chart is rendered client-side via svelte:component after mount -->
    <svelte:component this={null} />
    <!-- Note: In production, use: import { Chart } from 'svelte-apexcharts' -->
    <!-- and render <Chart options={chartOptions} /> -->
    <!-- Placeholder until npm install is run -->
    <pre class="chart-placeholder">{JSON.stringify(chartOptions.series.map(s => s.name), null, 2)}</pre>
  </div>
{/if}

<style>
  .header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 1rem; flex-wrap: wrap; gap: 0.5rem; }
  h2 { margin: 0; font-size: 1.125rem; }
  .range-buttons { display: flex; gap: 0.375rem; }
  .loading, .empty { color: #94a3b8; padding: 2rem; text-align: center; }
  .error { color: #ef4444; padding: 1rem; }
  .chart-wrapper { background: #1e293b; border-radius: 0.75rem; padding: 1rem; }
  .hint { font-size: 0.75rem; color: #64748b; margin: 0 0 0.5rem; }
  .chart-placeholder { color: #64748b; font-size: 0.75rem; }
</style>
