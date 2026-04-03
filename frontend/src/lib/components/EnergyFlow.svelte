<script lang="ts">
  import { liveData, pvTotal, isStale } from '$lib/stores/live';

  // Format watts: auto-switch to kW above 950W
  function fmt(w: number | null): string {
    if (w === null || w === undefined) return '—';
    const abs = Math.abs(w);
    if (abs >= 950) return (abs / 1000).toFixed(1) + ' kW';
    return Math.round(abs) + ' W';
  }

  // Animation duration in seconds: faster = more power
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

  // Flow states
  $: pvOn   = pv > 10;
  $: batChg = batW > 10;      // house → battery
  $: batDis = batW < -10;     // battery → house
  $: bezug  = gridW > 10;     // grid → house
  $: einsp  = gridW < -10;    // house → grid

  $: pvD   = animDur(pv);
  $: batD  = animDur(batW);
  $: gridD = animDur(gridW);

  // Autarky: % of load covered by solar + battery (not from grid)
  $: autarky = (load && load > 0)
    ? Math.min(100, Math.round(Math.max(0, load - Math.max(0, gridW)) / load * 100))
    : null;
</script>

<div class="wrap">
  <svg viewBox="0 0 360 250" class="flow" aria-label="Energiefluss-Diagramm">
    <defs>
      <!-- Paths define direction of animated dots -->
      <path id="fp-s"  d="M 180 88  L 180 128"/>
      <path id="fp-bh" d="M 90  160 L 148 160"/>
      <path id="fp-hb" d="M 148 160 L 90  160"/>
      <path id="fp-gh" d="M 270 160 L 212 160"/>
      <path id="fp-hg" d="M 212 160 L 270 160"/>
    </defs>

    <!-- ── Connection lines ── -->
    <line x1="180" y1="88"  x2="180" y2="128"
      stroke={pvOn ? '#f59e0b' : '#1e3a5f'} stroke-width="3" stroke-linecap="round"/>
    <line x1="90"  y1="160" x2="148" y2="160"
      stroke={batChg ? '#22c55e' : batDis ? '#f97316' : '#1e3a5f'} stroke-width="3" stroke-linecap="round"/>
    <line x1="212" y1="160" x2="270" y2="160"
      stroke={bezug ? '#ef4444' : einsp ? '#22c55e' : '#1e3a5f'} stroke-width="3" stroke-linecap="round"/>

    <!-- ── Animated dots ── -->

    <!-- Solar → House -->
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
        <circle r="4.5" fill="#22c55e">
          <animateMotion dur="{batD.toFixed(2)}s" begin="{(i * batD / 3).toFixed(2)}s" repeatCount="indefinite">
            <mpath href="#fp-hb"/>
          </animateMotion>
        </circle>
      {/each}
    {/if}

    <!-- Grid → House (Bezug) -->
    {#if bezug}
      {#each [0, 1, 2] as i}
        <circle r="4.5" fill="#ef4444">
          <animateMotion dur="{gridD.toFixed(2)}s" begin="{(i * gridD / 3).toFixed(2)}s" repeatCount="indefinite">
            <mpath href="#fp-gh"/>
          </animateMotion>
        </circle>
      {/each}
    {/if}

    <!-- House → Grid (Einspeisung) -->
    {#if einsp}
      {#each [0, 1, 2] as i}
        <circle r="4.5" fill="#22c55e">
          <animateMotion dur="{gridD.toFixed(2)}s" begin="{(i * gridD / 3).toFixed(2)}s" repeatCount="indefinite">
            <mpath href="#fp-hg"/>
          </animateMotion>
        </circle>
      {/each}
    {/if}

    <!-- ── Nodes (rendered last = on top of dots) ── -->

    <!-- Solar (top) -->
    <circle cx="180" cy="58" r="30" fill="#0f172a" stroke={pvOn ? '#f59e0b' : '#334155'} stroke-width="2"/>
    <text x="180" y="52" text-anchor="middle" dominant-baseline="central" font-size="18">☀️</text>
    <text x="180" y="69" text-anchor="middle" font-size="10.5" fill={pvOn ? '#fbbf24' : '#475569'}>{fmt($pvTotal)}</text>
    <text x="180" y="18" text-anchor="middle" font-size="9" fill="#475569" letter-spacing="1">SOLAR</text>

    <!-- House (center) -->
    <circle cx="180" cy="160" r="32" fill="#0f172a" stroke="#3b82f6" stroke-width="2"/>
    <text x="180" y="153" text-anchor="middle" dominant-baseline="central" font-size="20">🏠</text>
    <text x="180" y="173" text-anchor="middle" font-size="10.5" fill="#94a3b8">{fmt(load)}</text>

    <!-- Battery (left) -->
    <circle cx="60" cy="160" r="30" fill="#0f172a"
      stroke={batChg ? '#22c55e' : batDis ? '#f97316' : '#334155'} stroke-width="2"/>
    <text x="60" y="153" text-anchor="middle" dominant-baseline="central" font-size="16">🔋</text>
    <text x="60" y="171" text-anchor="middle" font-size="10.5" fill="#94a3b8">
      {soc !== null ? Math.round(soc) + '%' : '—'}
    </text>
    <text x="60" y="208" text-anchor="middle" font-size="9" fill="#475569" letter-spacing="1">BATTERIE</text>
    {#if batChg || batDis}
      <text x="60" y="220" text-anchor="middle" font-size="9" fill={batChg ? '#22c55e' : '#f97316'}>
        {batChg ? '↑ ' : '↓ '}{fmt(batW)}
      </text>
    {/if}

    <!-- Grid (right) -->
    <circle cx="300" cy="160" r="30" fill="#0f172a"
      stroke={bezug ? '#ef4444' : einsp ? '#22c55e' : '#334155'} stroke-width="2"/>
    <text x="300" y="153" text-anchor="middle" dominant-baseline="central" font-size="16">⚡</text>
    <text x="300" y="171" text-anchor="middle" font-size="10.5"
      fill={bezug ? '#fca5a5' : einsp ? '#86efac' : '#94a3b8'}>
      {Math.abs(gridW) > 10 ? fmt(gridW) : '—'}
    </text>
    <text x="300" y="208" text-anchor="middle" font-size="9"
      fill={bezug ? '#ef4444' : einsp ? '#22c55e' : '#475569'} letter-spacing="1">
      {bezug ? 'BEZUG' : einsp ? 'EINSPEISUNG' : 'NETZ'}
    </text>
  </svg>

  <!-- Bottom stats row -->
  <div class="stats">
    {#if autarky !== null}
      <span class="stat">
        <span class="stat-label">Autarkie</span>
        <span class="stat-val" style="color: {autarky > 70 ? '#22c55e' : autarky > 30 ? '#f59e0b' : '#ef4444'}">{autarky}%</span>
      </span>
    {/if}
    {#if temp !== null}
      <span class="stat">
        <span class="stat-label">WR Temp</span>
        <span class="stat-val" style="color: {temp > 70 ? '#ef4444' : '#94a3b8'}">{temp.toFixed(1)} °C</span>
      </span>
    {/if}
    {#if $isStale}
      <span class="stat stale">⚠ Keine aktuellen Daten</span>
    {/if}
  </div>
</div>

<style>
  .wrap {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.75rem;
    padding: 0.5rem 0;
  }
  .flow {
    width: 100%;
    max-width: 420px;
    display: block;
  }
  .stats {
    display: flex;
    gap: 1.5rem;
    flex-wrap: wrap;
    justify-content: center;
  }
  .stat {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.15rem;
  }
  .stat-label {
    font-size: 0.7rem;
    color: #475569;
    letter-spacing: 0.05em;
    text-transform: uppercase;
  }
  .stat-val {
    font-size: 1rem;
    font-weight: 600;
  }
  .stale {
    font-size: 0.75rem;
    color: #f59e0b;
    align-self: center;
  }
</style>
