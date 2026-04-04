<script lang="ts">
  import { onMount, onDestroy, tick } from 'svelte';
  import ApexCharts from 'apexcharts';

  let selectedHours = 24;
  let data: any[] = [];
  let summary: any[] = [];
  let loading = false;
  let loadingSummary = false;
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
      await tick();
      renderChart();
    } catch (e: any) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  async function loadSummary() {
    loadingSummary = true;
    try {
      const res = await fetch('/api/summary', { credentials: 'include' });
      if (!res.ok) throw new Error('Fehler beim Laden');
      summary = await res.json();
    } catch {} finally {
      loadingSummary = false;
    }
  }

  function renderChart() {
    if (!chartEl || data.length === 0) return;
    const options = {
      chart: {
        type: 'area',
        height: 280,
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
      chart.destroy();
      chart = null;
    }
    chartEl.innerHTML = '';
    chart = new ApexCharts(chartEl, options);
    chart.render();
  }

  function fmt(v: number | null, dec = 1): string {
    return v !== null && v !== undefined ? v.toFixed(dec) : '–';
  }

  onMount(() => {
    loadHistory(selectedHours);
    loadSummary();
  });
  onDestroy(() => chart?.destroy());
</script>

<svelte:head><title>Verlauf – Solar Dashboard</title></svelte:head>

<!-- Live-Chart -->
<div class="section-header">
  <h2>Leistungsverlauf</h2>
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
  <div class="empty">Keine Messdaten für diesen Zeitraum.</div>
{:else}
  <div class="chart-wrapper">
    <p class="hint">{data.length} Messpunkte · {selectedHours}h</p>
    <div bind:this={chartEl} style="min-height:280px"></div>
  </div>
{/if}

<!-- Tages-Tabelle -->
<h2 class="table-heading">Tageswerte</h2>

{#if loadingSummary}
  <div class="loading">Lade Tageswerte…</div>
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
            <td class="num muted">
              {row.battery_min_pct !== null ? fmt(row.battery_min_pct, 0) + '%' : '–'}
              /
              {row.battery_max_pct !== null ? fmt(row.battery_max_pct, 0) + '%' : '–'}
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
{/if}

<style>
  .section-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 1rem; flex-wrap: wrap; gap: 0.5rem; }
  h2 { margin: 0; font-size: 1.125rem; font-weight: 600; color: #212121; }
  .table-heading { margin: 1.5rem 0 1rem; font-size: 1.125rem; font-weight: 600; color: #212121; }
  .range-buttons { display: flex; gap: 0.375rem; }
  .btn { padding: 0.375rem 0.875rem; border-radius: 2rem; font-size: 0.8125rem; font-weight: 600; cursor: pointer; border: 1px solid #e0e0e0; transition: all 0.15s; background: #fff; color: #757575; }
  .btn-active { background: #f59e0b; color: #fff; border-color: #f59e0b; }
  .btn-outline:hover { background: #f5f5f5; color: #212121; }
  .loading, .empty { color: #757575; padding: 2rem; text-align: center; }
  .error { color: #dc2626; padding: 1rem; }
  .chart-wrapper { background: #fff; border-radius: 0.75rem; box-shadow: 0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.08); padding: 1rem; }
  .hint { font-size: 0.75rem; color: #9e9e9e; margin: 0 0 0.5rem; }
  .table-wrapper { background: #fff; border-radius: 0.75rem; box-shadow: 0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.08); overflow: hidden; }
  table { width: 100%; border-collapse: collapse; font-size: 0.875rem; }
  th { text-align: left; padding: 0.75rem 1rem; color: #757575; font-weight: 600; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.04em; border-bottom: 2px solid #e0e0e0; white-space: nowrap; background: #fafafa; }
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
