# Single Quantum WebSQ (SNSPD) Integration Guide

This guide covers setting up and using the Single Quantum SNSPD detector system with **qt3scope** and **qt3scan** on TQLM.

## Prerequisites

- **SNSPD Hardware:** Single Quantum Atlas driver with WebSQ firmware
- **Network:** SNSPD connected to lab LAN with static IP
- **Ports:** TCP ports 12345 (counts stream) and 12000 (control) accessible from TQLM

## 1. Connection Setup

### 1.1 Verify SNSPD Network Configuration

Test network connectivity from TQLM:

On Windows, open PowerShell and run:
```powershell
Test-NetConnection -ComputerName 3.3.44.57 -Port 12345
Test-NetConnection -ComputerName 3.3.44.57 -Port 12000
```

Both should return `TcpTestSucceeded: True`.

Alternatively, use Python:
```bash
python3 src/qt3utils/tools/test_snspd_connection.py --host 3.3.44.57 --counts-port 12345 --control-port 12000
```

## 2. Using SNSPD with qt3scope

Launch qt3scope with SNSPD:
```bash
python3 -m qt3utils.applications.qt3scope.main qt3scope_snspd
```

Signal Source selector should show "snspd" as active.

## 3. Using SNSPD with qt3scan

Launch qt3scan with SNSPD:
```bash
python3 -m qt3utils.applications.qt3scan.main qt3scan_snspd
```

## 4. Configuration

Edit config files if SNSPD IP changes:
- `src/qt3utils/applications/qt3scope/config_files/qt3scope_snspd.yaml`
- `src/qt3utils/applications/qt3scan/config_files/qt3scan_snspd.yaml`

Change `host` parameter to new IP address.

## 5. Troubleshooting

Test connection:
```bash
python3 src/qt3utils/tools/test_snspd_connection.py --host 3.3.44.57
```

Check SNSPD is powered on and network connected.

For more details, see the Single Quantum EOS manual.
