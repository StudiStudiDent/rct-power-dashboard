# RCT Power Dashboard

Mobile-friendly PWA to monitor your RCT Power inverter from anywhere.
No open ports, no VPN, no cloud subscription required.

Works behind DSLite (no public IPv4) via Cloudflare Tunnel.

## Deployment auf Proxmox LXC

### Einzeiler-Install (tteck-Stil)

Auf dem **Proxmox-Host** (Shell oder SSH als root):

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/StudiStudiDent/rct-power-dashboard/main/scripts/create-lxc.sh)"
```

Das Script:
- Fragt nach VMID, Hostname, Storage, IP und Root-Passwort
- Lädt Ubuntu 22.04 Template automatisch herunter (falls nicht vorhanden)
- Erstellt LXC (4 GB Disk, 256 MB RAM, unprivileged)
- Installiert Python + Dependencies
- Klont das Repo (falls GitHub-URL angegeben)
- Richtet systemd-Services ein

Danach nur noch `config.yaml.local` anpassen und Services starten — fertig.

---

### Manueller Weg (Schritt für Schritt)

In der Proxmox Web-UI:

1. **Create CT** klicken
2. Template: **Ubuntu 22.04**
3. Disk: **4 GB** (reicht für 90 Tage Daten)
4. RAM: **256 MB**
5. CPU: **1 Core**
6. Netzwerk: DHCP oder feste IP — egal, muss nur dein Heimnetz erreichen können
7. Optionen → **Nesting: aktivieren** (nur nötig wenn du später Docker willst)
8. Fertigstellen und starten

### Schritt 2 — LXC vorbereiten

Im LXC-Terminal (Proxmox → CT → Console):

```bash
apt update && apt upgrade -y
apt install -y python3.11 python3.11-venv python3-pip git
```

Datenverzeichnis anlegen:
```bash
mkdir -p /data
```

### Schritt 3 — Code auf den LXC kopieren

**Option A: direkt vom Mac kopieren** (kein GitHub nötig)

Auf dem **Mac** ausführen — `LXC_IP` ersetzen (steht in Proxmox unter der CT):
```bash
cd /Users/i540592/RCT-Power-Experiment
scp -r . root@LXC_IP:/opt/rct-dashboard
```

**Option B: via GitHub** (empfohlen wenn du das Projekt öffentlich teilen willst)
```bash
# Erst auf GitHub ein neues Repo anlegen, dann:
git clone https://github.com/StudiStudiDent/rct-power-dashboard /opt/rct-dashboard
```

### Schritt 4 — Frontend auf dem Mac bauen

Spart Node.js auf dem LXC. Auf dem **Mac** ausführen:

```bash
cd /Users/i540592/RCT-Power-Experiment/frontend
npm install && npm run build

# dist-Ordner auf LXC kopieren:
scp -r dist/ root@LXC_IP:/opt/rct-dashboard/frontend/dist/
```

> Falls Node.js auf dem LXC lieber: `apt install -y nodejs npm` und dann `cd /opt/rct-dashboard/frontend && npm install && npm run build`

### Schritt 5 — Python-Abhängigkeiten installieren

Im **LXC**:
```bash
cd /opt/rct-dashboard
python3.11 -m venv venv
venv/bin/pip install -r requirements.txt
```

### Schritt 6 — Konfiguration

```bash
cd /opt/rct-dashboard
cp config.yaml config.yaml.local
nano config.yaml.local
```

Folgendes anpassen:

```yaml
inverter:
  host: "192.168.178.90"   # ← bereits korrekt

auth:
  username: "admin"
  password: "SICHERES_PASSWORT_HIER"   # ← ändern!
  jwt_secret: "HIER_ZUFALLSSTRING"     # ← generieren (siehe unten)
```

JWT-Secret generieren:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### Schritt 7 — Wechselrichter-Verbindung testen

```bash
cd /opt/rct-dashboard
venv/bin/python -c "
import socket
s = socket.create_connection(('192.168.178.90', 8899), timeout=5)
print('OK — Wechselrichter erreichbar')
s.close()
"
```

Gibt `OK` aus? Weiter. Gibt Fehler? LXC und Wechselrichter im gleichen Netz-Segment prüfen.

### Schritt 8 — Systemd-Services installieren

```bash
useradd -r -s /bin/false solar
chown -R solar:solar /opt/rct-dashboard /data

cp /opt/rct-dashboard/systemd/rct-poller.service /etc/systemd/system/
cp /opt/rct-dashboard/systemd/rct-dashboard.service /etc/systemd/system/

systemctl daemon-reload
systemctl enable --now rct-poller rct-dashboard
```

Status prüfen:
```bash
systemctl status rct-poller rct-dashboard
journalctl -u rct-poller -f          # Echtzeit-Log des Pollers
journalctl -u rct-dashboard -f       # Echtzeit-Log des Backends
```

Dashboard lokal erreichbar unter: `http://LXC_IP:8000`

### Schritt 9 — Cloudflare Tunnel einrichten (für Zugriff von außen)

```bash
# cloudflared installieren
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o /tmp/cloudflared.deb
dpkg -i /tmp/cloudflared.deb

# Login (öffnet Browser-Link zum Kopieren)
cloudflared tunnel login

# Tunnel erstellen
cloudflared tunnel create solar-dashboard

# Config anpassen
cp /opt/rct-dashboard/systemd/cloudflared-config.yaml ~/.cloudflared/config.yaml
nano ~/.cloudflared/config.yaml
# → hostname: solar.deine-domain.com
# → CNAME in Cloudflare DNS: solar.deine-domain.com → <tunnel-id>.cfargotunnel.com

# Als Service installieren
cp /opt/rct-dashboard/systemd/cloudflared.service /etc/systemd/system/
systemctl enable --now cloudflared
```

Dashboard ist jetzt live unter `https://solar.deine-domain.com` — ohne offene Ports.

**"Zum Home-Bildschirm hinzufügen"** auf iPhone/Android für App-Gefühl.

---

## Architecture

```
[RCT Inverter :8899]
      ↓ TCP (rctclient)
[rct-poller.py]         ← separate process, writes every 30s
      ↓
[SQLite /data/solar.db]  ← WAL mode, UNIQUE ts, 90-day retention
      ↓
[FastAPI :8000]          ← reads SQLite, REST API + WebSocket push
      ↓
[SvelteKit PWA]          ← served as static files by FastAPI
      ↓
[Cloudflare Tunnel]      ← outbound-only, no open ports
      ↓
[Your Phone / Browser]
```

**Security:** Cloudflare Tunnel (no open ports) + HTTPS + HttpOnly JWT Cookie + Rate limiting (5 login attempts/min/IP).

---

## Data fields

| Field | Source | Description |
|-------|--------|-------------|
| battery_soc | battery.soc | Battery charge % |
| pv_string1_w | dc_conv.dc_conv_struct[0].p_dc | PV String 1 power W |
| pv_string2_w | dc_conv.dc_conv_struct[1].p_dc | PV String 2 power W |
| grid_w | g_sync.p_ac_grid_sum | Grid: positive=feed-in, negative=draw |
| load_w | g_sync.p_ac_load_total | House consumption W |
| battery_w | battery.power | Battery: positive=charging, negative=discharging |
| inverter_temp | inv_struct.temperature | Inverter temperature °C |
| battery_status | battery.bat_status | Battery status code |

---

## Alerts (ntfy.sh)

Push-Benachrichtigungen aktivieren in `config.yaml.local`:

```yaml
alerts:
  enabled: true
  ntfy_topic: "mein-solar-geheim-topic"  # privater Topic-Name
  battery_low_pct: 20
  inverter_offline_minutes: 5
```

ntfy-App auf iPhone/Android installieren, Topic abonnieren — fertig.

---

## Development

```bash
# Backend (with hot reload)
venv/bin/uvicorn backend.main:app --reload

# Frontend (with API proxy to backend)
cd frontend && npm run dev

# Tests
venv/bin/pytest
```

---

## Docker Compose (alternative zu LXC)

Für Nicht-Proxmox-Setups (Raspberry Pi, beliebiges Linux mit Docker):

```bash
cp config.yaml config.yaml.local && nano config.yaml.local
docker compose up -d
```

---

## Contributing

Issues und PRs willkommen. Gebaut für die RCT Power Community in D/A/CH.

Andere RCT Power Modelle oder Firmware-Versionen? Issue öffnen mit den rctclient Object-IDs die bei dir funktionieren.
