#!/usr/bin/env bash
# =============================================================================
# setup_hotspot.sh — Pi 5 Wi-Fi Direct hotspot for the SHAPE showcase rig
# =============================================================================
#
# Run ONCE on the Pi 5 to create a persistent private hotspot that the
# Zero 2 W connects to.  No router.  No internet.  Fully offline.
#
# After this script runs the Pi 5 will:
#   • Create a Wi-Fi access point called "SHAPE" on wlan0
#   • Hand out IP addresses in 10.42.0.0/24
#   • Always be reachable at 10.42.0.1 from the Zero 2 W
#   • Start the hotspot automatically on every boot
#
# The Zero 2 W then sets:
#   export SHAPE_PI5_URL=http://10.42.0.1:8765
#
# Physical wiring unchanged — this only affects the wireless layer.
#
# Usage:
#   chmod +x hardware/pi5/setup_hotspot.sh
#   sudo hardware/pi5/setup_hotspot.sh
#
# To tear down:
#   sudo nmcli connection delete SHAPE-Hotspot
#
# Group 3 — ITAI2376-14562
# Cherluk Sumdin, Olubukola Kukoyi, Taki Eddine Boubekri, Michael Rivas
# =============================================================================

set -euo pipefail

SSID="SHAPE"
PASSWORD="shapedemo"          # change before deployment if desired
IFACE="wlan0"
HOTSPOT_IP="10.42.0.1/24"
CONN_NAME="SHAPE-Hotspot"

# ---------------------------------------------------------------------------
# 0. Must run as root
# ---------------------------------------------------------------------------
if [[ $EUID -ne 0 ]]; then
    echo "[ERROR] Run with sudo: sudo $0"
    exit 1
fi

echo "======================================================"
echo "  SHAPE Wi-Fi Direct Hotspot Setup"
echo "  SSID     : $SSID"
echo "  Password : $PASSWORD"
echo "  Interface: $IFACE"
echo "  Pi 5 IP  : ${HOTSPOT_IP%/*}"
echo "======================================================"
echo ""

# ---------------------------------------------------------------------------
# 1. Check NetworkManager is running
# ---------------------------------------------------------------------------
if ! systemctl is-active --quiet NetworkManager; then
    echo "[INFO] Starting NetworkManager..."
    systemctl start NetworkManager
    sleep 2
fi

# ---------------------------------------------------------------------------
# 2. Remove any existing SHAPE-Hotspot connection so we start clean
# ---------------------------------------------------------------------------
if nmcli connection show "$CONN_NAME" &>/dev/null; then
    echo "[INFO] Removing existing $CONN_NAME connection..."
    nmcli connection delete "$CONN_NAME"
fi

# ---------------------------------------------------------------------------
# 3. Create the hotspot connection profile
#    - mode: ap  (Access Point — Pi 5 is the base station)
#    - band: bg  (2.4 GHz — Zero 2 W supports 2.4 GHz only)
#    - ipv4.method: shared  (Pi 5 hands out DHCP leases)
#    - autoconnect: yes  (starts on every boot automatically)
# ---------------------------------------------------------------------------
echo "[INFO] Creating hotspot connection profile..."
nmcli connection add \
    type wifi \
    ifname "$IFACE" \
    con-name "$CONN_NAME" \
    autoconnect yes \
    ssid "$SSID" \
    -- \
    wifi.mode ap \
    wifi.band bg \
    wifi-sec.key-mgmt wpa-psk \
    wifi-sec.psk "$PASSWORD" \
    ipv4.method shared \
    ipv4.addresses "$HOTSPOT_IP" \
    ipv6.method disabled

# ---------------------------------------------------------------------------
# 4. Bring the hotspot up now
# ---------------------------------------------------------------------------
echo "[INFO] Activating hotspot..."
nmcli connection up "$CONN_NAME"

# ---------------------------------------------------------------------------
# 5. Confirm
# ---------------------------------------------------------------------------
echo ""
echo "======================================================"
echo "  Hotspot active."
echo ""
echo "  Pi 5 IP  :  ${HOTSPOT_IP%/*}"
echo "  SSID     :  $SSID"
echo "  Password :  $PASSWORD"
echo ""
echo "  On the Zero 2 W, connect to Wi-Fi 'SHAPE' then:"
echo "    export SHAPE_PI5_URL=http://${HOTSPOT_IP%/*}:8765"
echo "    export SHAPE_API_KEY=shape_local_key"
echo ""
echo "  Or add to ~/.bashrc on the Zero 2 W for persistence:"
echo "    echo 'export SHAPE_PI5_URL=http://${HOTSPOT_IP%/*}:8765' >> ~/.bashrc"
echo "    echo 'export SHAPE_API_KEY=shape_local_key' >> ~/.bashrc"
echo ""
echo "  Test connectivity from Zero 2 W:"
echo "    curl -s http://${HOTSPOT_IP%/*}:8765/status \\"
echo "         -H 'X-API-Key: shape_local_key'"
echo "======================================================"

# ---------------------------------------------------------------------------
# 6. Write a companion teardown script next to this one
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cat > "$SCRIPT_DIR/teardown_hotspot.sh" << 'EOF'
#!/usr/bin/env bash
# Removes the SHAPE Wi-Fi Direct hotspot.
set -euo pipefail
if [[ $EUID -ne 0 ]]; then echo "[ERROR] Run with sudo: sudo $0"; exit 1; fi
nmcli connection delete SHAPE-Hotspot && echo "Hotspot removed."
EOF
chmod +x "$SCRIPT_DIR/teardown_hotspot.sh"
echo "[INFO] Teardown script written to teardown_hotspot.sh"
