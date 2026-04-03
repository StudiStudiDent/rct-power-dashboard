#!/usr/bin/env bash
# RCT Power Dashboard — Proxmox LXC Installer
#
# Ausführen auf dem Proxmox-HOST (nicht im LXC):
#   bash -c "$(curl -fsSL https://raw.githubusercontent.com/StudiStudiDent/rct-power-dashboard/main/scripts/create-lxc.sh)"
#
# Was dieses Script macht:
#   1. Fragt nach VMID, IP-Adresse und Passwort
#   2. Lädt Ubuntu 22.04 Template herunter (falls nicht vorhanden)
#   3. Erstellt LXC mit 4 GB Disk, 256 MB RAM
#   4. Installiert Python, Dependencies, App
#   5. Richtet systemd-Services ein
#   6. Zeigt die lokale Dashboard-URL

set -euo pipefail

# ── Farben ─────────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

info()    { echo -e "${CYAN}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC} $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

echo -e "${BOLD}"
echo "╔══════════════════════════════════════╗"
echo "║   RCT Power Dashboard — LXC Setup   ║"
echo "╚══════════════════════════════════════╝"
echo -e "${NC}"

# ── Voraussetzungen prüfen ─────────────────────────────────────────────────────
[[ "$(id -u)" -eq 0 ]] || error "Muss als root auf dem Proxmox-Host laufen."
command -v pct  &>/dev/null || error "pct nicht gefunden — dieses Script auf dem Proxmox-Host ausführen."
command -v pvesh &>/dev/null || error "pvesh nicht gefunden — dieses Script auf dem Proxmox-Host ausführen."

# ── Eingaben ───────────────────────────────────────────────────────────────────
# Nächste freie VMID vorschlagen
NEXT_VMID=$(pvesh get /cluster/nextid 2>/dev/null || echo "200")

read -rp "VMID [${NEXT_VMID}]: " VMID
VMID="${VMID:-$NEXT_VMID}"

read -rp "Hostname [solar-dashboard]: " HOSTNAME
HOSTNAME="${HOSTNAME:-solar-dashboard}"

read -rp "Storage für Disk [local-lxc]: " STORAGE
STORAGE="${STORAGE:-local-lxc}"

read -rp "Netzwerk-Bridge [vmbr0]: " BRIDGE
BRIDGE="${BRIDGE:-vmbr0}"

read -rp "IP-Adresse (leer = DHCP) [DHCP]: " LXC_IP
LXC_IP="${LXC_IP:-dhcp}"
if [[ "$LXC_IP" != "dhcp" && "$LXC_IP" != *"/"* ]]; then
  LXC_IP="${LXC_IP}/24"  # CIDR ergänzen falls vergessen
fi

read -rsp "Root-Passwort für den LXC: " ROOT_PASS
echo
[[ -n "$ROOT_PASS" ]] || error "Passwort darf nicht leer sein."

read -rp "GitHub-URL des Repos (leer = später manuell): " REPO_URL
REPO_URL="${REPO_URL:-}"

# ── Ubuntu 22.04 Template sicherstellen ────────────────────────────────────────
TEMPLATE_STORAGE="local"
TEMPLATE_FILE=$(find /var/lib/vz/template/cache/ -name "ubuntu-22.04-standard*.tar.*" 2>/dev/null | head -1)

if [[ -z "$TEMPLATE_FILE" ]]; then
  info "Ubuntu 22.04 Template wird heruntergeladen..."
  pveam update
  TEMPLATE_NAME=$(pveam available --section system | grep "ubuntu-22.04-standard" | sort -V | tail -1 | awk '{print $2}')
  [[ -n "$TEMPLATE_NAME" ]] || error "Ubuntu 22.04 Template nicht in der Proxmox-Liste gefunden."
  pveam download "$TEMPLATE_STORAGE" "$TEMPLATE_NAME"
  TEMPLATE_FILE="/var/lib/vz/template/cache/${TEMPLATE_NAME}"
else
  info "Template gefunden: $(basename "$TEMPLATE_FILE")"
fi

# ── LXC erstellen ─────────────────────────────────────────────────────────────
info "Erstelle LXC ${VMID} (${HOSTNAME})..."

NET_CONFIG="name=eth0,bridge=${BRIDGE},firewall=1"
if [[ "$LXC_IP" == "dhcp" ]]; then
  NET_CONFIG="${NET_CONFIG},ip=dhcp"
else
  NET_CONFIG="${NET_CONFIG},ip=${LXC_IP},gw=$(ip route | awk '/default/ {print $3; exit}')"
fi

pct create "$VMID" "$TEMPLATE_FILE" \
  --hostname "$HOSTNAME" \
  --password "$ROOT_PASS" \
  --memory 256 \
  --swap 256 \
  --cores 1 \
  --rootfs "${STORAGE}:4" \
  --net0 "$NET_CONFIG" \
  --unprivileged 1 \
  --features nesting=1 \
  --start 1 \
  --onboot 1

info "Warte bis LXC gestartet ist..."
sleep 5

# ── Netzwerk abwarten ─────────────────────────────────────────────────────────
info "Warte auf Netzwerkverbindung im LXC..."
for i in {1..20}; do
  if pct exec "$VMID" -- ping -c1 -W2 8.8.8.8 &>/dev/null; then
    success "Netzwerk bereit."
    break
  fi
  sleep 2
  if [[ "$i" -eq 20 ]]; then
    error "LXC hat nach 40s keine Netzwerkverbindung. DNS/Gateway prüfen."
  fi
done

# ── App im LXC installieren ───────────────────────────────────────────────────
info "Installiere Abhängigkeiten im LXC..."

pct exec "$VMID" -- bash -c "
  set -euo pipefail
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -q
  apt-get install -y -q python3.11 python3.11-venv python3-pip git curl
  mkdir -p /data
"

if [[ -n "$REPO_URL" ]]; then
  info "Klone Repository von ${REPO_URL}..."
  pct exec "$VMID" -- bash -c "git clone '${REPO_URL}' /opt/rct-dashboard"
else
  warn "Kein Repo angegeben — Code muss manuell nach /opt/rct-dashboard kopiert werden."
  warn "Beispiel vom Mac: scp -r /PFAD/ZUM/PROJEKT root@LXC_IP:/opt/rct-dashboard"
fi

# ── Python-Umgebung einrichten ────────────────────────────────────────────────
if pct exec "$VMID" -- test -d /opt/rct-dashboard; then
  info "Installiere Python-Dependencies..."
  pct exec "$VMID" -- bash -c "
    cd /opt/rct-dashboard
    python3.11 -m venv venv
    venv/bin/pip install -q -r requirements.txt
  "

  # ── systemd-User und Services ─────────────────────────────────────────────
  info "Richte systemd-Services ein..."
  pct exec "$VMID" -- bash -c "
    id solar &>/dev/null || useradd -r -s /bin/false solar
    chown -R solar:solar /opt/rct-dashboard /data

    cp /opt/rct-dashboard/systemd/rct-poller.service /etc/systemd/system/
    cp /opt/rct-dashboard/systemd/rct-dashboard.service /etc/systemd/system/
    systemctl daemon-reload
  "
  warn "Services noch NICHT gestartet — zuerst config.yaml.local anpassen!"
fi

# ── IP des LXC ermitteln ──────────────────────────────────────────────────────
FINAL_IP=$(pct exec "$VMID" -- ip -4 addr show eth0 | awk '/inet / {gsub(/\/.*/, "", $2); print $2}')

echo
echo -e "${GREEN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}${BOLD}  LXC ${VMID} erfolgreich erstellt!${NC}"
echo -e "${GREEN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo
echo -e "  IP-Adresse:   ${CYAN}${FINAL_IP}${NC}"
echo -e "  SSH:          ${CYAN}ssh root@${FINAL_IP}${NC}"
echo -e "  Dashboard:    ${CYAN}http://${FINAL_IP}:8000${NC} (nach Setup)"
echo
echo -e "${BOLD}Nächste Schritte:${NC}"
echo -e "  1. SSH in den LXC: ${CYAN}ssh root@${FINAL_IP}${NC}"
echo -e "  2. Config anpassen: ${CYAN}cp /opt/rct-dashboard/config.yaml /opt/rct-dashboard/config.yaml.local${NC}"
echo -e "     → Passwort + JWT-Secret setzen"
echo -e "  3. Services starten: ${CYAN}systemctl enable --now rct-poller rct-dashboard${NC}"
echo -e "  4. Logs prüfen: ${CYAN}journalctl -u rct-poller -f${NC}"
echo
