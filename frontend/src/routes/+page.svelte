<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { connectWebSocket } from '$lib/stores/live';
  import EnergyFlow from '$lib/components/EnergyFlow.svelte';

  let cleanup: (() => void) | null = null;
  onMount(() => { cleanup = connectWebSocket(); });
  onDestroy(() => cleanup?.());
</script>

<svelte:head><title>Live – Solar Dashboard</title></svelte:head>

<EnergyFlow />
