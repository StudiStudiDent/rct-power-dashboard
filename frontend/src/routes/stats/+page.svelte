<script lang="ts">
  import { onMount, onDestroy, tick } from 'svelte';
  import ApexCharts from 'apexcharts';

  let summary: any[] = [];
  let loading = true;
  let activeFilter = '30';

  // Single-day state
  let selectedDate = '';
  let dayReadings: any[] = [];
  let dayLoading = false;
  let chartDayEl: HTMLDivElement;
  let chartDay: ApexCharts | null = null;

  // Chart DOM refs
  let chartOverviewEl: HTMLDivElement;
  let chartPvUsageEl: HTMLDivElement;
  let chartEfficiencyEl: HTMLDivElement;
  let chartBalanceEl: HTMLDivElement;

  let chartOverview: ApexCharts | null = null;
  let chartPvUsage: ApexCharts | null = null;
  let chartEfficiency: ApexCharts | null = null;
  let chartBalance: ApexCharts | null = null;

  onMount(async () => {
    try {
      const res = await fetch('/api/summary', { credentials: 'include' });
      if (res.ok) summary = await res.json();
    } finally {
      loading = false;
    }
  });

  onDestroy(() => {
    chartOverview?.destroy();
    chartPvUsage?.destroy();
    chartEfficiency?.destroy();
    chartBalance?.destroy();
    chartDay?.destroy();
  });

  // --- Single-day date picker ---

  async function loadDay(date: string) {
    if (!date) return;
    dayLoading = true;
    activeFilter = `day:${date}`;
    try {
      const res = await fetch(`/api/history?date=${date}`, { credentials: 'include' });
      if (res.ok) dayReadings = await res.json();
      else dayReadings = [];
    } finally {
      dayLoading = false;
      await tick();
      renderDayChart();
    }
  }

  function onDateInput(e: Event) {
    const v = (e.target as HTMLInputElement).value;
    if (v) loadDay(v);
  }

  // Derived KPIs for single day from summary table
  $: dayRow = activeFilter.startsWith('day:')
    ? summary.find(r => r.date === activeFilter.slice(4)) ?? null
    : null;

  function renderDayChart() {
    if (!chartDayEl || dayReadings.length === 0) return;
    const times = dayReadings.map(r => new Date(r.ts * 1000).toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' }));
    const opts = {
      chart: { ...chartBase, type: 'line', height: 260 },
      theme: lightTheme,
      stroke: { curve: 'smooth', width: [2, 2, 2, 2] },
      xaxis: { categories: times, labels: { rotate: -45, style: { colors: '#757575', fontSize: '11px' } }, tickAmount: 12 },
      yaxis: { labels: { formatter: (v: number) => `${Math.round(v)}W`, style: { colors: '#757575' } } },
      tooltip: { y: { formatter: (v: number) => `${Math.round(v)} W` }, theme: 'light' },
      grid: lightGrid,
      legend: { position: 'top', labels: { colors: '#424242' } },
      dataLabels: { enabled: false },
      series: [
        { name: '☀️ PV Gesamt', data: dayReadings.map(r => Math.round(((r.pv_string1_w ?? 0) + (r.pv_string2_w ?? 0))) ) },
        { name: '🏠 Verbrauch',  data: dayReadings.map(r => Math.round(r.load_w ?? 0)) },
        { name: '⬇️ Netz',       data: dayReadings.map(r => Math.round(r.grid_w ?? 0)) },
        { name: '🔋 Batterie',   data: dayReadings.map(r => Math.round(r.battery_w ?? 0)) },
      ],
      colors: ['#f59e0b', '#1d4ed8', '#dc2626', '#16a34a'],
    };
    if (chartDay) { chartDay.destroy(); chartDay = null; }
    chartDayEl.innerHTML = '';
    chartDay = new ApexCharts(chartDayEl, opts);
    chartDay.render();
  }

  // --- Filter logic ---

  $: years = [...new Set(summary.map(r => r.date.slice(0, 4)))].sort().reverse();

  $: filtered = (() => {
    if (activeFilter.startsWith('day:')) return [];
    if (activeFilter === 'all') return [...summary].reverse();
    if (activeFilter === '7')  return [...summary].slice(0, 7).reverse();
    if (activeFilter === '30') return [...summary].slice(0, 30).reverse();
    if (activeFilter === '90') return [...summary].slice(0, 90).reverse();
    // Calendar year
    return summary.filter(r => r.date.startsWith(activeFilter)).reverse();
  })();

  // --- Derived totals ---

  $: totals = filtered.reduce(
    (acc, r) => ({
      yield_kwh:     acc.yield_kwh     + (r.yield_kwh     ?? 0),
      grid_feed_kwh: acc.grid_feed_kwh + (r.grid_feed_kwh ?? 0),
      grid_draw_kwh: acc.grid_draw_kwh + (r.grid_draw_kwh ?? 0),
      load_kwh:      acc.load_kwh      + (r.load_kwh      ?? 0),
    }),
    { yield_kwh: 0, grid_feed_kwh: 0, grid_draw_kwh: 0, load_kwh: 0 }
  );

  $: selfConsumedKwh = Math.max(0, totals.yield_kwh - totals.grid_feed_kwh);
  $: autarkyPct = totals.load_kwh > 0
    ? Math.round(Math.max(0, totals.load_kwh - totals.grid_draw_kwh) / totals.load_kwh * 100)
    : null;
  $: selfConsumptionPct = totals.yield_kwh > 0
    ? Math.round(selfConsumedKwh / totals.yield_kwh * 100)
    : null;

  // --- Render all charts when data changes ---

  $: if (!loading && filtered.length > 0) {
    tick().then(() => setTimeout(renderAllCharts, 0));
  }

  function renderAllCharts() {
    renderOverview();
    renderPvUsage();
    renderEfficiency();
    renderBalance();
  }

  const chartBase = {
    background: '#ffffff',
    toolbar: { show: false },
    animations: { enabled: false },
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
  };
  const lightTheme = { mode: 'light' };
  const lightGrid = { borderColor: '#f0f0f0', strokeDashArray: 4 };
  const xLabels = (rows: any[]) => ({
    categories: rows.map(r => r.date),
    labels: { rotate: -45, style: { colors: '#757575', fontSize: '11px' }, formatter: (v: string) => (typeof v === 'string' && v.length >= 7 ? v.slice(5) : v) },
  });

  // Chart 1: Overview — grouped bars (Ertrag / Einspeisung / Bezug / Verbrauch)
  function renderOverview() {
    if (!chartOverviewEl || filtered.length === 0) return;
    const opts = {
      chart: { ...chartBase, type: 'bar', height: 260 },
      theme: lightTheme,
      plotOptions: { bar: { columnWidth: '75%', borderRadius: 2 } },
      dataLabels: { enabled: false },
      xaxis: xLabels(filtered),
      yaxis: { labels: { formatter: (v: number) => `${v.toFixed(1)}`, style: { colors: '#757575' } } },
      tooltip: { y: { formatter: (v: number) => `${v.toFixed(2)} kWh` }, theme: 'light' },
      grid: lightGrid,
      legend: { position: 'top', labels: { colors: '#424242' } },
      series: [
        { name: '☀️ Ertrag',      data: filtered.map(r => +(r.yield_kwh     ?? 0).toFixed(2)) },
        { name: '🔌 Einspeisung', data: filtered.map(r => +(r.grid_feed_kwh ?? 0).toFixed(2)) },
        { name: '⬇️ Bezug',       data: filtered.map(r => +(r.grid_draw_kwh ?? 0).toFixed(2)) },
        { name: '🏠 Verbrauch',   data: filtered.map(r => +(r.load_kwh      ?? 0).toFixed(2)) },
      ],
      colors: ['#f59e0b', '#16a34a', '#dc2626', '#1d4ed8'],
    };
    if (chartOverview) chartOverview.updateOptions(opts);
    else { chartOverview = new ApexCharts(chartOverviewEl, opts); chartOverview.render(); }
  }

  // Chart 2: PV Nutzung — stacked: Eigenverbrauch + Einspeisung = PV total; plus Bezug
  function renderPvUsage() {
    if (!chartPvUsageEl || filtered.length === 0) return;
    const opts = {
      chart: { ...chartBase, type: 'bar', height: 260, stacked: true },
      theme: lightTheme,
      plotOptions: { bar: { columnWidth: '65%', borderRadius: 2 } },
      dataLabels: { enabled: false },
      xaxis: xLabels(filtered),
      yaxis: { labels: { formatter: (v: number) => `${v.toFixed(1)}`, style: { colors: '#757575' } } },
      tooltip: { y: { formatter: (v: number) => `${v.toFixed(2)} kWh` }, theme: 'light' },
      grid: lightGrid,
      legend: { position: 'top', labels: { colors: '#424242' } },
      series: [
        {
          name: '☀️ Eigenverbrauch',
          data: filtered.map(r => +Math.max(0, (r.yield_kwh ?? 0) - (r.grid_feed_kwh ?? 0)).toFixed(2))
        },
        {
          name: '🔌 Einspeisung',
          data: filtered.map(r => +(r.grid_feed_kwh ?? 0).toFixed(2))
        },
        {
          name: '⬇️ Netzbezug',
          data: filtered.map(r => +(r.grid_draw_kwh ?? 0).toFixed(2))
        },
      ],
      colors: ['#f59e0b', '#16a34a', '#dc2626'],
    };
    if (chartPvUsage) chartPvUsage.updateOptions(opts);
    else { chartPvUsage = new ApexCharts(chartPvUsageEl, opts); chartPvUsage.render(); }
  }

  // Chart 3: Autarkie & Eigenverbrauchsquote — dual line %
  function renderEfficiency() {
    if (!chartEfficiencyEl || filtered.length === 0) return;

    const autarkyData = filtered.map(r => {
      const load = r.load_kwh ?? 0;
      if (load <= 0) return 0;
      return +Math.min(100, Math.max(0, (load - (r.grid_draw_kwh ?? 0)) / load * 100)).toFixed(1);
    });
    const selfConsData = filtered.map(r => {
      const y = r.yield_kwh ?? 0;
      if (y <= 0) return 0;
      return +Math.min(100, Math.max(0, (y - (r.grid_feed_kwh ?? 0)) / y * 100)).toFixed(1);
    });

    const opts = {
      chart: { ...chartBase, type: 'line', height: 240 },
      theme: lightTheme,
      stroke: { curve: 'smooth', width: [2, 2] },
      markers: { size: filtered.length <= 14 ? 3 : 0 },
      xaxis: xLabels(filtered),
      yaxis: { min: 0, max: 100, labels: { formatter: (v: number) => `${Math.round(v)}%`, style: { colors: '#757575' } } },
      tooltip: { y: { formatter: (v: number) => `${v.toFixed(0)}%` }, theme: 'light' },
      grid: lightGrid,
      legend: { position: 'top', labels: { colors: '#424242' } },
      series: [
        { name: '⚡ Autarkie',              data: autarkyData },
        { name: '☀️ Eigenverbrauchsquote', data: selfConsData },
      ],
      colors: ['#1d4ed8', '#f59e0b'],
    };
    if (chartEfficiency) {
      chartEfficiency.destroy();
      chartEfficiency = null;
    }
    chartEfficiencyEl.innerHTML = '';
    chartEfficiency = new ApexCharts(chartEfficiencyEl, opts);
    chartEfficiency.render();
  }


  // Chart 4: Energie-Bilanz — Ertrag minus Verbrauch pro Tag (positiv = Überschuss, negativ = Defizit)
  function renderBalance() {
    if (!chartBalanceEl || filtered.length === 0) return;
    const balanceData = filtered.map(r => +((r.yield_kwh ?? 0) - (r.load_kwh ?? 0)).toFixed(2));
    const opts = {
      chart: { ...chartBase, type: 'bar', height: 220 },
      theme: lightTheme,
      plotOptions: { bar: { columnWidth: '70%', borderRadius: 2, colors: {
        ranges: [
          { from: -999, to: 0,    color: '#dc2626' },
          { from: 0,    to: 999,  color: '#16a34a' },
        ]
      }}},
      dataLabels: { enabled: false },
      xaxis: xLabels(filtered),
      yaxis: { labels: { formatter: (v: number) => `${v.toFixed(1)}`, style: { colors: '#757575' } } },
      tooltip: { y: { formatter: (v: number) => `${v > 0 ? '+' : ''}${v.toFixed(2)} kWh` }, theme: 'light' },
      grid: { ...lightGrid, xaxis: { lines: { show: false } } },
      legend: { show: false },
      series: [{ name: 'Bilanz (Ertrag − Verbrauch)', data: balanceData }],
    };
    if (chartBalance) chartBalance.updateOptions(opts);
    else { chartBalance = new ApexCharts(chartBalanceEl, opts); chartBalance.render(); }
  }

  function fmt(v: number, dec = 1): string { return v.toFixed(dec); }
  function setFilter(f: string) {
    activeFilter = f;
    selectedDate = '';
  }
</script>

<svelte:head><title>Statistik – Solar Dashboard</title></svelte:head>

<div class="header">
  <h2>Statistik</h2>
  <div class="filter-row">
    <button class="btn {activeFilter === '7'   ? 'btn-active' : 'btn-outline'}" on:click={() => setFilter('7')}>7T</button>
    <button class="btn {activeFilter === '30'  ? 'btn-active' : 'btn-outline'}" on:click={() => setFilter('30')}>30T</button>
    <button class="btn {activeFilter === '90'  ? 'btn-active' : 'btn-outline'}" on:click={() => setFilter('90')}>90T</button>
    {#each years as y}
      <button class="btn {activeFilter === y ? 'btn-active' : 'btn-outline'}" on:click={() => setFilter(y)}>{y}</button>
    {/each}
    <button class="btn {activeFilter === 'all' ? 'btn-active' : 'btn-outline'}" on:click={() => setFilter('all')}>Gesamt</button>
    <input
      type="date"
      class="date-input {activeFilter.startsWith('day:') ? 'date-active' : ''}"
      bind:value={selectedDate}
      on:change={onDateInput}
      title="Einzelner Tag"
    />
  </div>
</div>

{#if loading}
  <div class="loading">Lade Daten…</div>
{:else if summary.length === 0}
  <div class="empty">Noch keine Daten vorhanden.</div>
{:else if activeFilter.startsWith('day:')}

  <!-- Single-day view -->
  {#if dayLoading}
    <div class="loading">Lade Tagesdaten…</div>
  {:else}
    {@const d = activeFilter.slice(4)}
    <div class="day-header">
      <span class="day-title">📅 {d}</span>
    </div>
    {#if dayRow}
      <div class="kpi-grid">
        <div class="kpi-card">
          <div class="kpi-label">☀️ PV Ertrag</div>
          <div class="kpi-value amber">{fmt(dayRow.yield_kwh ?? 0)} <span class="unit">kWh</span></div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">🔌 Einspeisung</div>
          <div class="kpi-value green">{fmt(dayRow.grid_feed_kwh ?? 0)} <span class="unit">kWh</span></div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">⬇️ Netzbezug</div>
          <div class="kpi-value red">{fmt(dayRow.grid_draw_kwh ?? 0)} <span class="unit">kWh</span></div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">🏠 Verbrauch</div>
          <div class="kpi-value blue">{fmt(dayRow.load_kwh ?? 0)} <span class="unit">kWh</span></div>
        </div>
        {#if (dayRow.load_kwh ?? 0) > 0}
          {@const aut = Math.round(Math.max(0, (dayRow.load_kwh - (dayRow.grid_draw_kwh ?? 0)) / dayRow.load_kwh * 100))}
          <div class="kpi-card">
            <div class="kpi-label">⚡ Autarkie</div>
            <div class="kpi-value" style="color:{aut>70?'#16a34a':aut>30?'#f59e0b':'#dc2626'}">{aut}<span class="unit">%</span></div>
          </div>
        {/if}
        {#if (dayRow.yield_kwh ?? 0) > 0}
          {@const sc = Math.round(Math.max(0, Math.min(100, ((dayRow.yield_kwh - (dayRow.grid_feed_kwh ?? 0)) / dayRow.yield_kwh * 100))))}
          <div class="kpi-card">
            <div class="kpi-label">☀️ Eigenverbrauchsquote</div>
            <div class="kpi-value amber">{sc}<span class="unit">%</span></div>
          </div>
        {/if}
      </div>
    {/if}
    {#if dayReadings.length > 0}
      <div class="chart-card">
        <div class="chart-title">Leistungsverlauf · {d}</div>
        <div class="chart-desc">Alle Messpunkte des Tages (Watt)</div>
        <div bind:this={chartDayEl} style="min-height:260px"></div>
      </div>
    {:else}
      <div class="empty">Keine Messpunkte für diesen Tag in der Datenbank.</div>
    {/if}
  {/if}

{:else}

  <!-- KPI Cards -->
  <div class="kpi-grid">
    <div class="kpi-card">
      <div class="kpi-label">☀️ PV Ertrag</div>
      <div class="kpi-value amber">{fmt(totals.yield_kwh)} <span class="unit">kWh</span></div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">🔌 Einspeisung</div>
      <div class="kpi-value green">{fmt(totals.grid_feed_kwh)} <span class="unit">kWh</span></div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">⬇️ Netzbezug</div>
      <div class="kpi-value red">{fmt(totals.grid_draw_kwh)} <span class="unit">kWh</span></div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">🏠 Verbrauch</div>
      <div class="kpi-value blue">{fmt(totals.load_kwh)} <span class="unit">kWh</span></div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">☀️ Eigenverbrauch</div>
      <div class="kpi-value amber">{fmt(selfConsumedKwh)} <span class="unit">kWh</span></div>
    </div>
    {#if autarkyPct !== null}
      <div class="kpi-card">
        <div class="kpi-label">⚡ Autarkie</div>
        <div class="kpi-value" style="color:{autarkyPct>70?'#16a34a':autarkyPct>30?'#f59e0b':'#dc2626'}">{autarkyPct}<span class="unit">%</span></div>
      </div>
    {/if}
    {#if selfConsumptionPct !== null}
      <div class="kpi-card">
        <div class="kpi-label">☀️ Eigenverbrauchsquote</div>
        <div class="kpi-value amber">{selfConsumptionPct}<span class="unit">%</span></div>
      </div>
    {/if}
  </div>

  <!-- Chart 1: Übersicht -->
  <div class="chart-card">
    <div class="chart-title">Energieübersicht · täglich</div>
    <div bind:this={chartOverviewEl}></div>
  </div>

  <!-- Chart 2: PV Nutzung -->
  <div class="chart-card">
    <div class="chart-title">PV-Nutzung · Eigenverbrauch vs. Einspeisung vs. Netzbezug</div>
    <div class="chart-desc">Wie wird der Solarstrom genutzt? Amber = selbst verbraucht, Grün = ins Netz, Rot = aus dem Netz</div>
    <div bind:this={chartPvUsageEl}></div>
  </div>

  <!-- Chart 3: Autarkie & Eigenverbrauchsquote -->
  <div class="chart-card">
    <div class="chart-title">Autarkie & Eigenverbrauchsquote · täglich</div>
    <div class="chart-desc">Autarkie = wie viel vom Verbrauch kommt aus Solar. Eigenverbrauchsquote = wie viel PV-Strom wird selbst genutzt.</div>
    <div bind:this={chartEfficiencyEl} style="min-height:240px"></div>
  </div>

  <!-- Chart 4: Energie-Bilanz -->
  <div class="chart-card">
    <div class="chart-title">Energie-Bilanz · Ertrag minus Verbrauch</div>
    <div class="chart-desc">Grün = Überschuss-Tag (mehr erzeugt als verbraucht). Rot = Defizit-Tag.</div>
    <div bind:this={chartBalanceEl}></div>
  </div>

{/if}

<style>
  .header { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 1rem; flex-wrap: wrap; gap: 0.75rem; }
  h2 { margin: 0; font-size: 1.125rem; font-weight: 600; color: #212121; }
  .filter-row { display: flex; flex-wrap: wrap; gap: 0.375rem; align-items: center; }
  .btn { padding: 0.3rem 0.75rem; border-radius: 2rem; font-size: 0.8rem; font-weight: 600; cursor: pointer; border: 1px solid #e0e0e0; transition: all 0.15s; background: #fff; color: #757575; }
  .btn-active { background: #f59e0b; color: #fff; border-color: #f59e0b; }
  .btn-outline:hover { background: #f5f5f5; color: #212121; }
  .date-input { padding: 0.25rem 0.5rem; border-radius: 0.5rem; border: 1px solid #e0e0e0; font-size: 0.8rem; color: #424242; background: #fff; cursor: pointer; height: 2rem; }
  .date-input:focus { outline: none; border-color: #f59e0b; }
  .date-active { border-color: #f59e0b; background: #fffbeb; }
  .loading, .empty { color: #757575; padding: 2rem; text-align: center; }

  .day-header { margin-bottom: 0.75rem; }
  .day-title { font-size: 1rem; font-weight: 600; color: #424242; }

  .kpi-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: 0.625rem; margin-bottom: 1rem; }
  .kpi-card { background: #fff; border-radius: 0.75rem; box-shadow: 0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.08); padding: 0.875rem 1rem; display: flex; flex-direction: column; gap: 0.2rem; }
  .kpi-label { font-size: 0.7rem; color: #757575; text-transform: uppercase; letter-spacing: 0.05em; }
  .kpi-value { font-size: 1.375rem; font-weight: 700; line-height: 1.1; }
  .unit { font-size: 0.75rem; font-weight: 400; color: #9e9e9e; margin-left: 0.1rem; }
  .amber { color: #f59e0b; } .green { color: #16a34a; } .red { color: #dc2626; } .blue { color: #1d4ed8; }

  .chart-card { background: #fff; border-radius: 0.75rem; box-shadow: 0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.08); padding: 1rem; margin-bottom: 1rem; }
  .chart-title { font-size: 0.875rem; font-weight: 600; color: #212121; margin-bottom: 0.2rem; }
  .chart-desc { font-size: 0.75rem; color: #9e9e9e; margin-bottom: 0.5rem; }
</style>
