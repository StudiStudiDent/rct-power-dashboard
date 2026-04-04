// live.ts — Real-time inverter data store with WebSocket connection
import { writable, derived } from 'svelte/store';

export interface Reading {
  ts: number | null;
  battery_soc: number | null;
  pv_string1_w: number | null;
  pv_string2_w: number | null;
  grid_w: number | null;
  load_w: number | null;
  battery_w: number | null;
  inverter_temp: number | null;
  battery_status: number | null;
}

const empty: Reading = {
  ts: null,
  battery_soc: null,
  pv_string1_w: null,
  pv_string2_w: null,
  grid_w: null,
  load_w: null,
  battery_w: null,
  inverter_temp: null,
  battery_status: null,
};

export const liveData = writable<Reading>(empty);

// Derived: total PV power from both strings
export const pvTotal = derived(liveData, ($d) =>
  $d.pv_string1_w !== null ? ($d.pv_string1_w ?? 0) + ($d.pv_string2_w ?? 0) : null
);

// Derived: seconds since last update (for stale data indicator)
export const dataAge = derived(liveData, ($d) => {
  if (!$d.ts) return null;
  return Math.floor(Date.now() / 1000) - $d.ts;
});

// Derived: is data stale (> 2 minutes old)
export const isStale = derived(dataAge, ($age) => $age !== null && $age > 120);

let ws: WebSocket | null = null;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

function sendVisibility() {
  if (ws?.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ visible: !document.hidden }));
  }
}

export function connectWebSocket(): () => void {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const url = `${protocol}//${location.host}/ws/live`;

  function connect() {
    ws = new WebSocket(url);

    ws.onopen = () => {
      // Tell backend our current visibility state immediately on connect
      sendVisibility();
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as Reading;
        liveData.set(data);
      } catch {}
    };

    ws.onclose = () => {
      reconnectTimer = setTimeout(connect, 5000);
    };

    ws.onerror = () => {
      ws?.close();
    };
  }

  connect();

  // Notify backend whenever tab visibility changes
  document.addEventListener('visibilitychange', sendVisibility);

  return () => {
    document.removeEventListener('visibilitychange', sendVisibility);
    if (reconnectTimer) clearTimeout(reconnectTimer);
    ws?.close();
    ws = null;
  };
}
