<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { liveData, pvTotal, connectWebSocket } from '$lib/stores/live';
  import MetricCard from '$lib/components/MetricCard.svelte';

  let cleanup: (() => void) | null = null;

  onMount(() => {
    cleanup = connectWebSocket();
  });

  onDestroy(() => cleanup?.());

  // Grid direction label
  $: gridLabel = ($liveData.grid_w ?? 0) >= 0 ? 'Einspeisung' : 'Netzbezug';
  $: gridColor = ($liveData.grid_w ?? 0) >= 0 ? '#22c55e' : '#ef4444';
  $: gridValue = $liveData.grid_w !== null ? Math.abs($liveData.grid_w) : null;
</script>

<svelte:head><title>Live – Solar Dashboard</title></svelte:head>

<div class="grid">
  <MetricCard
    label="Batterie"
    value={$liveData.battery_soc}
    unit="%"
    icon="🔋"
    color={($liveData.battery_soc ?? 50) > 20 ? '#22c55e' : '#ef4444'}
    decimals={1}
  />
  <MetricCard
    label="Solarertrag"
    value={$pvTotal}
    unit="W"
    icon="☀️"
    color="#f59e0b"
    decimals={0}
  />
  <MetricCard
    label={gridLabel}
    value={gridValue}
    unit="W"
    icon="🔌"
    color={gridColor}
    decimals={0}
  />
  <MetricCard
    label="Hausverbrauch"
    value={$liveData.load_w}
    unit="W"
    icon="🏠"
    color="#3b82f6"
    decimals={0}
  />
  <MetricCard
    label="Batteriestrom"
    value={$liveData.battery_w}
    unit="W"
    icon={($liveData.battery_w ?? 0) >= 0 ? '⬆️' : '⬇️'}
    color={($liveData.battery_w ?? 0) >= 0 ? '#22c55e' : '#f59e0b'}
    decimals={0}
  />
  <MetricCard
    label="WR Temperatur"
    value={$liveData.inverter_temp}
    unit="°C"
    icon="🌡️"
    color="#94a3b8"
    decimals={1}
  />
</div>

<style>
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: 0.75rem;
  }
</style>
