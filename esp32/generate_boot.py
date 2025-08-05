#!/usr/bin/env python3

"""
Generate boot.py for ESP32-S3 with single WiFi network
Usage: ./generate_boot.py <ssid> <wifi_password> <webrepl_password>
"""

import sys

def generate_boot_py(ssid, wifi_password, webrepl_password):
    """Generate boot.py with specified network configuration"""

    boot_template = f'''#python
import network
import webrepl
import time


def scan_wifi():
	"""Scan for available WiFi networks"""
	wlan = network.WLAN(network.STA_IF)
	wlan.active(True)

	try:
		networks_found = wlan.scan()
		if networks_found:
			print("Available networks:")
			for net in networks_found:
				net_ssid = net[0].decode('utf-8')
				signal = net[3]
				print(f"  - {{net_ssid}} (signal: {{signal}})")
			return networks_found
		else:
			print("No networks found")
			return []
	except Exception as e:
		print(f"Scan failed: {{e}}")
		return []


def get_wifi():
	"""Get current network configuration"""
	wlan = network.WLAN(network.STA_IF)
	if wlan.isconnected():
		ip, subnet, gateway, dns = wlan.ifconfig()
		print(f"Connected to: {{wlan.config('ssid')}}")
		print(f"IP: {{ip}}")
		print(f"Gateway: {{gateway}}")
		print(f"Subnet: {{subnet}}")
		print(f"DNS: {{dns}}")
		return {{'ssid': wlan.config('ssid'), 'ip': ip, 'gateway': gateway, 'subnet': subnet, 'dns': dns}}
	else:
		print("Not connected")
		return None

def connect_wifi():
	"""Connect to WiFi with retry logic"""
	print("Connecting WiFi")
	wlan = network.WLAN(network.STA_IF)
	ssid = "{ssid}"
	password = "{wifi_password}"

	# Initialize WiFi interface first
	wlan.active(True)

	# Try up to 3 times
	for attempt in range(3):
		# Reset WiFi before each retry to avoid internal errors
		if attempt > 0:
			wlan.active(False)
			time.sleep(2)
			wlan.active(True)
			time.sleep(2)

		try:
			wlan.connect(ssid, password)

			# Wait for connection with timeout
			timeout = 15
			while not wlan.isconnected() and timeout > 0:
				time.sleep(1)
				timeout -= 1

			if wlan.isconnected():
				return True

		except OSError:
			pass

		time.sleep(1)

	return False

# Connect to WiFi
if connect_wifi():
	webrepl.start(password="{webrepl_password}")
'''

    # Write to boot.py
    with open('boot.py', 'w') as f:
        f.write(boot_template)

    print(f"Generated boot.py for network: {ssid}")
    print(f"WebREPL password: {webrepl_password}")
    return True

def main():
    if len(sys.argv) != 4:
        print("Usage: ./generate_boot.py <ssid> <wifi_password> <webrepl_password>")
        print("Example: ./generate_boot.py laptop cluecon.com cluecon")
        sys.exit(1)

    ssid = sys.argv[1]
    wifi_password = sys.argv[2]
    webrepl_password = sys.argv[3]

    generate_boot_py(ssid, wifi_password, webrepl_password)

if __name__ == '__main__':
    main()