<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import ApexCharts from 'apexcharts';

  let selectedHours = 24;
  let data: any[] = [];
  let loading = false;
  let error = '';
  let chartEl: HTMLDivElement;
  let chart: ApexCharts | null = null;

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
      renderChart();
    } catch (e: any) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  function renderChart() {
    if (!chartEl || data.length === 0) return;
    const options = {
      chart: {
        type: 'area',
        height: 300,
        background: '#ffffff',
        toolbar: { show: false },
        animations: { enabled: false },
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      },
      theme: { mode: 'light' },
      stroke: { curve: 'smooth', width: 2 },
      fill: { type: 'gradient', gradient: { opacityFrom: 0.25, opacityTo: 0.02 } },
      xaxis: {
        type: 'datetime',
        categories: data.map((d) => d.ts * 1000),
        labels: { datetimeUTC: false, style: { colors: '#757575' } },
      },
      yaxis: { labels: { formatter: (v: number) => `${Math.round(v)} W`, style: { colors: '#757575' } } },
      tooltip: { x: { format: 'dd.MM HH:mm' }, theme: 'light' },
      grid: { borderColor: '#f0f0f0', strokeDashArray: 4 },
      legend: { position: 'top', labels: { colors: '#424242' } },
      series: [
        { name: '☀️ PV Gesamt', data: data.map((d) => Math.round((d.pv_string1_w ?? 0) + (d.pv_string2_w ?? 0))) },
        { name: '🏠 Verbrauch', data: data.map((d) => Math.round(d.load_w ?? 0)) },
        { name: '🔌 Netz', data: data.map((d) => Math.round(d.grid_w ?? 0)) },
      ],
      colors: ['#f59e0b', '#1d4ed8', '#dc2626'],
    };
    if (chart) {
      chart.updateOptions(options);
    } else {
      chart = new ApexCharts(chartEl, options);
      chart.render();
    }
  }

  onMount(() => loadHistory(selectedHours));
  onDestroy(() => chart?.destroy());
</script>

<svelte:head><title>Verlauf – Solar Dashboard</title></svelte:head>

<div class="header">
  <h2>Verlauf</h2>
  <div class="range-buttons">
    {#each ranges as r}
      <button
        class="btn {selectedHours === r.hours ? 'btn-active' : 'btn-outline'}"
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
  <div class="chart-wrapper">
    <p class="hint">{data.length} Messpunkte · {selectedHours}h</p>
    <div bind:this={chartEl}></div>
  </div>
{/if}

<style>
  .header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 1rem; flex-wrap: wrap; gap: 0.5rem; }
  h2 { margin: 0; font-size: 1.125rem; font-weight: 600; color: #212121; }
  .range-buttons { display: flex; gap: 0.375rem; }
  .btn { padding: 0.375rem 0.875rem; border-radius: 2rem; font-size: 0.8125rem; font-weight: 600; cursor: pointer; border: 1px solid #e0e0e0; transition: all 0.15s; }
  .btn-active { background: #f59e0b; color: #fff; border-color: #f59e0b; }
  .btn-outline { background: #fff; color: #757575; }
  .btn-outline:hover { background: #f5f5f5; color: #212121; }
  .loading, .empty { color: #757575; padding: 2rem; text-align: center; }
  .error { color: #dc2626; padding: 1rem; }
  .chart-wrapper {
    background: #fff;
    border-radius: 0.75rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.08);
    padding: 1rem;
  }
  .hint { font-size: 0.75rem; color: #9e9e9e; margin: 0 0 0.5rem; }
</style>
