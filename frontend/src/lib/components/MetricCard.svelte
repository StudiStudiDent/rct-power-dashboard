<script lang="ts">
  export let value: number | null;
  export let label: string;
  export let unit: string;
  export let icon: string = '';
  export let color: string = '#f59e0b'; // amber default
  export let decimals: number = 0;

  $: display = value !== null ? value.toFixed(decimals) : '–';
</script>

<div class="card">
  <div class="card-label">{icon} {label}</div>
  <div class="card-value" style="color: {color}">
    {display}
    {#if value !== null}
      <span class="card-unit">{unit}</span>
    {/if}
  </div>
</div>

<style>
  .card {
    background: #1e293b;
    border-radius: 0.75rem;
    padding: 1rem 1.25rem;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }
  .card-label {
    font-size: 0.75rem;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .card-value {
    font-size: 1.75rem;
    font-weight: 700;
    line-height: 1;
  }
  .card-unit {
    font-size: 0.875rem;
    font-weight: 400;
    color: #64748b;
    margin-left: 0.2rem;
  }
</style>
