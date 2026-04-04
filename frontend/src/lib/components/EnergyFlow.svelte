<script lang="ts">
  import { liveData, pvTotal, isStale } from '$lib/stores/live';

  function fmt(w: number | null): string {
    if (w === null || w === undefined) return '—';
    const abs = Math.abs(w);
    if (abs >= 950) return (abs / 1000).toFixed(1) + ' kW';
    return Math.round(abs) + ' W';
  }

  function animDur(watts: number): number {
    const abs = Math.abs(watts);
    if (abs < 10) return 99;
    return Math.max(0.5, Math.min(5, 2000 / abs));
  }

  $: pv    = $pvTotal ?? 0;
  $: gridW = $liveData.grid_w ?? 0;
  $: batW  = $liveData.battery_w ?? 0;
  $: soc   = $liveData.battery_soc;
  $: load  = $liveData.load_w;
  $: temp  = $liveData.inverter_temp;

  $: pvOn   = pv > 10;
  $: batChg = batW < -10;   // negative = charging (inverter convention)
  $: batDis = batW > 10;    // positive = discharging
  $: bezug  = gridW > 10;
  $: einsp  = gridW < -10;

  $: pvD   = animDur(pv);
  $: batD  = animDur(batW);
  $: gridD = animDur(gridW);

  $: autarky = (load && load > 0)
    ? Math.min(100, Math.round(Math.max(0, load - Math.max(0, gridW)) / load * 100))
    : null;

  // Line colors
  const lineInactive = '#e0e0e0';
  $: linePv   = pvOn   ? '#f59e0b' : lineInactive;
  $: lineBat  = batChg ? '#16a34a' : batDis ? '#f97316' : lineInactive;
  $: lineGrid = bezug  ? '#dc2626' : einsp ? '#16a34a' : lineInactive;

  // Node border colors
  $: borderPv   = pvOn   ? '#f59e0b' : '#e0e0e0';
  $: borderBat  = batChg ? '#16a34a' : batDis ? '#f97316' : '#e0e0e0';
  $: borderGrid = bezug  ? '#dc2626' : einsp  ? '#16a34a' : '#e0e0e0';
</script>

<div class="wrap">
  <div class="card">
    <svg viewBox="0 0 360 250" class="flow" aria-label="Energiefluss-Diagramm">
      <defs>
        <path id="fp-s"  d="M 180 88  L 180 128"/>
        <path id="fp-bh" d="M 90  160 L 148 160"/>
        <path id="fp-hb" d="M 148 160 L 90  160"/>
        <path id="fp-gh" d="M 270 160 L 212 160"/>
        <path id="fp-hg" d="M 212 160 L 270 160"/>
      </defs>

      <!-- Connection lines -->
      <line x1="180" y1="88"  x2="180" y2="128" stroke={linePv}   stroke-width="3" stroke-linecap="round"/>
      <line x1="90"  y1="160" x2="148" y2="160" stroke={lineBat}  stroke-width="3" stroke-linecap="round"/>
      <line x1="212" y1="160" x2="270" y2="160" stroke={lineGrid} stroke-width="3" stroke-linecap="round"/>

      <!-- Animated dots: Solar → House -->
      {#if pvOn}
        {#each [0, 1, 2] as i}
          <circle r="4.5" fill="#f59e0b">
            <animateMotion dur="{pvD.toFixed(2)}s" begin="{(i * pvD / 3).toFixed(2)}s" repeatCount="indefinite">
              <mpath href="#fp-s"/>
            </animateMotion>
          </circle>
        {/each}
      {/if}

      <!-- Battery → House (discharging) -->
      {#if batDis}
        {#each [0, 1, 2] as i}
          <circle r="4.5" fill="#f97316">
            <animateMotion dur="{batD.toFixed(2)}s" begin="{(i * batD / 3).toFixed(2)}s" repeatCount="indefinite">
              <mpath href="#fp-bh"/>
            </animateMotion>
          </circle>
        {/each}
      {/if}

      <!-- House → Battery (charging) -->
      {#if batChg}
        {#each [0, 1, 2] as i}
          <circle r="4.5" fill="#16a34a">
            <animateMotion dur="{batD.toFixed(2)}s" begin="{(i * batD / 3).toFixed(2)}s" repeatCount="indefinite">
              <mpath href="#fp-hb"/>
            </animateMotion>
          </circle>
        {/each}
      {/if}

      <!-- Grid → House (Bezug) -->
      {#if bezug}
        {#each [0, 1, 2] as i}
          <circle r="4.5" fill="#dc2626">
            <animateMotion dur="{gridD.toFixed(2)}s" begin="{(i * gridD / 3).toFixed(2)}s" repeatCount="indefinite">
              <mpath href="#fp-gh"/>
            </animateMotion>
          </circle>
        {/each}
      {/if}

      <!-- House → Grid (Einspeisung) -->
      {#if einsp}
        {#each [0, 1, 2] as i}
          <circle r="4.5" fill="#16a34a">
            <animateMotion dur="{gridD.toFixed(2)}s" begin="{(i * gridD / 3).toFixed(2)}s" repeatCount="indefinite">
              <mpath href="#fp-hg"/>
            </animateMotion>
          </circle>
        {/each}
      {/if}

      <!-- Nodes -->

      <!-- Solar -->
      <circle cx="180" cy="58" r="30" fill="#fff" stroke={borderPv} stroke-width="2.5"
        style="filter: drop-shadow(0 2px 4px rgba(0,0,0,0.1))"/>
      <text x="180" y="52" text-anchor="middle" dominant-baseline="central" font-size="18">☀️</text>
      <text x="180" y="69" text-anchor="middle" font-size="10.5" font-weight="600"
        fill={pvOn ? '#f59e0b' : '#9e9e9e'}>{fmt($pvTotal)}</text>
      <text x="180" y="18" text-anchor="middle" font-size="9" fill="#9e9e9e" letter-spacing="0.8">SOLAR</text>

      <!-- House -->
      <circle cx="180" cy="160" r="32" fill="#fff" stroke="#1d4ed8" stroke-width="2.5"
        style="filter: drop-shadow(0 2px 4px rgba(0,0,0,0.1))"/>
      <text x="180" y="153" text-anchor="middle" dominant-baseline="central" font-size="20">🏠</text>
      <text x="180" y="173" text-anchor="middle" font-size="10.5" font-weight="600" fill="#424242">{fmt(load)}</text>

      <!-- Battery -->
      <circle cx="60" cy="160" r="30" fill="#fff" stroke={borderBat} stroke-width="2.5"
        style="filter: drop-shadow(0 2px 4px rgba(0,0,0,0.1))"/>
      <text x="60" y="153" text-anchor="middle" dominant-baseline="central" font-size="16">🔋</text>
      <text x="60" y="171" text-anchor="middle" font-size="10.5" font-weight="600" fill="#424242">
        {soc !== null ? Math.round(soc) + '%' : '—'}
      </text>
      <text x="60" y="208" text-anchor="middle" font-size="9" fill="#9e9e9e" letter-spacing="0.8">BATTERIE</text>
      {#if batChg || batDis}
        <text x="60" y="220" text-anchor="middle" font-size="9" font-weight="600"
          fill={batChg ? '#16a34a' : '#f97316'}>
          {batChg ? '↑ ' : '↓ '}{fmt(batW)}
        </text>
      {/if}

      <!-- Grid -->
      <circle cx="300" cy="160" r="30" fill="#fff" stroke={borderGrid} stroke-width="2.5"
        style="filter: drop-shadow(0 2px 4px rgba(0,0,0,0.1))"/>
      <text x="300" y="153" text-anchor="middle" dominant-baseline="central" font-size="16">⚡</text>
      <text x="300" y="171" text-anchor="middle" font-size="10.5" font-weight="600"
        fill={bezug ? '#dc2626' : einsp ? '#16a34a' : '#9e9e9e'}>
        {Math.abs(gridW) > 10 ? fmt(gridW) : '—'}
      </text>
      <text x="300" y="208" text-anchor="middle" font-size="9" font-weight="600"
        fill={bezug ? '#dc2626' : einsp ? '#16a34a' : '#9e9e9e'} letter-spacing="0.8">
        {bezug ? 'BEZUG' : einsp ? 'EINSPEISUNG' : 'NETZ'}
      </text>
    </svg>
  </div>

  <!-- Stats row -->
  <div class="stats">
    {#if autarky !== null}
      <div class="stat-chip">
        <span class="stat-label">Autarkie</span>
        <span class="stat-val" style="color: {autarky > 70 ? '#16a34a' : autarky > 30 ? '#f59e0b' : '#dc2626'}">{autarky}%</span>
      </div>
    {/if}
    {#if temp !== null}
      <div class="stat-chip">
        <span class="stat-label">WR Temperatur</span>
        <span class="stat-val" style="color: {temp > 70 ? '#dc2626' : '#424242'}">{temp.toFixed(1)} °C</span>
      </div>
    {/if}
    {#if $isStale}
      <div class="stat-chip stale">⚠ Keine aktuellen Daten</div>
    {/if}
  </div>
</div>

<style>
  .wrap {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1rem;
  }
  .card {
    background: #fff;
    border-radius: 0.75rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.08);
    padding: 1rem 0.5rem 0.5rem;
    width: 100%;
    max-width: 440px;
  }
  .flow {
    width: 100%;
    display: block;
  }
  .stats {
    display: flex;
    gap: 0.75rem;
    flex-wrap: wrap;
    justify-content: center;
  }
  .stat-chip {
    background: #fff;
    border-radius: 2rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    padding: 0.4rem 1rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  .stat-label {
    font-size: 0.75rem;
    color: #757575;
  }
  .stat-val {
    font-size: 0.9375rem;
    font-weight: 700;
  }
  .stale { color: #f59e0b; font-size: 0.8rem; }
</style>
