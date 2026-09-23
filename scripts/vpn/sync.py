"""Run only the CAA data fetch inside an ephemeral WireGuard namespace."""
import os
from pathlib import Path
import socket
import subprocess
import sys


def run(*args):
    subprocess.run(args, check=True)


def main():
    config = sys.stdin.read()
    if not config.strip() or "<insert_" in config:
        raise SystemExit("Missing valid WireGuard configuration")
    # Docker's bridge isolates all interface and route changes from the host.
    os.umask(0o077)
    path = Path("/run/wireguard.conf")
    path.write_text(config)
    del config
    try:
        run("ip", "link", "add", "wg-caa", "type", "wireguard")
        run("wg", "setconf", "wg-caa", str(path))
    finally:
        path.unlink(missing_ok=True)
    run("ip", "address", "add", "10.14.0.2/32", "dev", "wg-caa")
    run("ip", "link", "set", "wg-caa", "mtu", "1380", "up")
    host = "dronegis.caa.gov.tw"
    ip = str(socket.getaddrinfo(host, 443, socket.AF_INET, socket.SOCK_STREAM)[0][4][0])
    run("ip", "route", "add", ip + "/32", "dev", "wg-caa")
    # Pin resolution so CAA cannot silently bypass the VPN on a DNS change.
    with open("/etc/hosts", "a") as hosts:
        hosts.write(f"\n{ip} {host}\n")
    print(f"CAA VPN route ready: {host} ({ip})", flush=True)
    # No GitHub token or private key is passed to the fetch process.
    run(sys.executable, "/workspace/scripts/sync_arcgis.py", *sys.argv[1:])
    peers = subprocess.check_output(["wg", "show", "wg-caa", "latest-handshakes"], text=True)
    if not any(int(line.split()[1]) > 0 for line in peers.splitlines()):
        raise SystemExit("WireGuard handshake was not established")
    print("WireGuard handshake verified", flush=True)


if __name__ == "__main__":
    main()
