import argparse
import json
import os
import requests
import time

CONFIG_FILE = "config.json"

def write_config():
    print("Setting up Govee Plug Monitor Configuration\n")
    print("To use this tool, you need a Govee API key.")
    print("1. Visit https://developer.govee.com")
    print("2. Log in with your Govee account or register if needed.")
    print("3. Navigate to the 'API Key' section on the Developer site and follow the instructions to obtain your key.")
    print("4. Once you have your API key, paste it below.\n")
    # Load existing config if present
    existing_config = {}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            existing_config = json.load(f)
        print(f"\nLoaded existing configuration from {CONFIG_FILE}")
    default_api_key = existing_config.get("govee_api_key", "")
    user_input = input(f"Enter your Govee API key [{default_api_key}]: ").strip()
    api_key = user_input if user_input else default_api_key
    headers = {"Govee-API-Key": api_key}

    existing_plugs = {
        p.get("device_id"): p for p in existing_config.get("plugs", []) if "device_id" in p
    }

    # Fetch devices and check responsiveness immediately after API key input
    try:
        response = requests.get("https://developer-api.govee.com/v1/devices", headers=headers)
        response.raise_for_status()
        devices = response.json().get("data", {}).get("devices", [])
        if not devices:
            print("No devices were found in your Govee account. Please ensure your account is linked to devices in the Govee app.")
            return
    except Exception as e:
        print(f"Error fetching devices with provided API key: {e}")
        return

    # Check responsiveness for all devices
    device_status_map = {}
    responsive_devices = []
    unresponsive_devices = []
    for device in devices:
        device_id = device.get("device")
        model = device.get("model")
        try:
            state_response = requests.get(
                "https://developer-api.govee.com/v1/devices/state",
                headers=headers,
                params={"device": device_id, "model": model},
                timeout=10
            )
            state_data = state_response.json().get("data", {})
            props = {p: v for d in state_data.get("properties", []) for p, v in d.items()}
            online_status = props.get("online", True)
        except Exception:
            online_status = False
        device_status_map[device_id] = online_status
        if online_status is False:
            unresponsive_devices.append(device)
        else:
            responsive_devices.append(device)

    # Summary
    print(f"\nFound {len(devices)} devices: {len(responsive_devices)} responsive, {len(unresponsive_devices)} unresponsive.\n")

    # Prompt for monitoring all responsive devices
    monitor_all_resp = input("Monitor all responsive devices? (y/n, default=y): ").strip().lower() or "y"
    if monitor_all_resp != "y":
        print("No devices selected for monitoring. Aborting.")
        return

    # Prompt for monitoring unresponsive devices
    monitor_unresp = input("Monitor unresponsive devices? (y/n, default=n): ").strip().lower() or "n"
    monitor_unresponsive_devices = []
    if monitor_unresp == "y" and unresponsive_devices:
        for device in unresponsive_devices:
            name = device.get("deviceName")
            confirm = input(f"Monitor '{name}'? (UNRESPONSIVE) (y/n, default=n): ").strip().lower() or "n"
            if confirm == "y":
                monitor_unresponsive_devices.append(device)

    # Compose list of monitored devices
    monitored_devices = []
    monitored_devices.extend(responsive_devices)
    monitored_devices.extend(monitor_unresponsive_devices)

    if not monitored_devices:
        print("No devices selected for monitoring. Aborting.")
        return

    # Prompt for shared Pushcut URL for all monitored plugs
    pushcut_url = input(f"Enter a Pushcut URL to use for all monitored plugs (leave blank to skip) [{existing_config.get('pushcut_url', '')}]: ").strip() or existing_config.get("pushcut_url", "")

    # Ask if expected power states should be configured
    configure_expected_power = input("Configure expected power states per device? (y/n, default=n): ").strip().lower() or "n"
    configure_expected_power = (configure_expected_power == "y")

    plugs = []
    for device in monitored_devices:
        name = device.get("deviceName")
        model = device.get("model")
        device_id = device.get("device")
        existing = existing_plugs.get(device_id, {})
        # Get current state for observed_power
        try:
            state_response = requests.get(
                "https://developer-api.govee.com/v1/devices/state",
                headers=headers,
                params={"device": device_id, "model": model},
                timeout=10
            )
            state_data = state_response.json().get("data", {})
            props = {p: v for d in state_data.get("properties", []) for p, v in d.items()}
            observed_power = props.get("powerState", "unknown")
        except Exception:
            props = {}
            observed_power = "unknown"
        # Set expected_power
        if configure_expected_power:
            print(f"Expected power state for '{name}' (on/off/ignore) [default: ignore, current: {observed_power}]: ", end="")
            power_input = input().strip().lower() or "ignore"
        else:
            power_input = "ignore"
        # Always monitor responsiveness for all monitored devices
        monitor_responsiveness = True
        plugs.append({
            "device_id": device_id,
            "name": name,
            "model": model,
            "pushcut_url": pushcut_url,
            "monitor_responsiveness": monitor_responsiveness,
            "expected_power": power_input
        })

    config = {
        "govee_api_key": api_key,
        "pushcut_url": pushcut_url,
        "plugs": plugs
    }
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
    print(f"\nConfiguration saved to {CONFIG_FILE}")

def send_pushcut(url, title, message):
    try:
        requests.post(url, json={"title": title, "text": message}, timeout=5)
    except Exception as e:
        print(f"⚠️  Failed to send Pushcut notification: {e}")

def check_config(send_notifications: bool = False):
    if not os.path.exists(CONFIG_FILE):
        print(f"No config found at {CONFIG_FILE}. Please run 'config' first.")
        return

    with open(CONFIG_FILE) as f:
        config = json.load(f)

    api_key = config.get("govee_api_key")
    headers = {"Govee-API-Key": api_key}

    print("Fetching device list from Govee...")
    try:
        response = requests.get("https://developer-api.govee.com/v1/devices", headers=headers)
        response.raise_for_status()
        devices = response.json().get("data", {}).get("devices", [])
        if not devices:
            print("No devices found. Is your API key correct?")
            return
        print("\nAvailable Devices:")
        for device in devices:
            print(f"- Name: {device.get('deviceName')}, Model: {device.get('model')}, ID: {device.get('device')}")
        # Show configured plugs
        plugs = config.get("plugs", [])
        if plugs:
            print("\nConfigured plugs to monitor:")
            for p in plugs:
                print(f"- Name: {p.get('name')}, Pushcut URL: {p.get('pushcut_url')}")

        # Enhancement: Check and display device states, responsiveness, and expected power state
        print("\nChecking device states...")
        # Get set of monitored device IDs from config, and build expected-power dict
        monitored_ids = {p["device_id"] for p in config.get("plugs", [])}
        monitored = {
            p["device_id"]: {
                "name": p.get("name", p["device_id"]),
                "expected_power": p.get("expected_power", "ignore"),
                "pushcut_url": p.get("pushcut_url", config.get("pushcut_url", "")),
            }
            for p in config.get("plugs", [])
        }
        any_monitored_offline = False
        for device in devices:
            device_id = device.get("device")
            model = device.get("model")
            try:
                state_response = requests.get(
                    "https://developer-api.govee.com/v1/devices/state",
                    headers=headers,
                    params={"device": device_id, "model": model},
                    timeout=10
                )
                if state_response.status_code == 200:
                    state_data = state_response.json().get("data", {})
                    props = {p: v for d in state_data.get("properties", []) for p, v in d.items()}
                    online_status = props.get("online")
                    if online_status is False:
                        print(f"- {device.get('deviceName')} is UNRESPONSIVE (online=False)")
                        if device_id in monitored:
                            any_monitored_offline = True
                            if send_notifications and monitored[device_id].get("pushcut_url"):
                                send_pushcut(
                                    monitored[device_id]["pushcut_url"],
                                    f"Govee Alert: {device.get('deviceName')}",
                                    "Device is unresponsive or power state mismatch"
                                )
                    else:
                        print(f"- {device.get('deviceName')} is responsive. State: {state_data.get('properties')}")
                        # Check expected power state if monitored
                        power_status = None
                        for prop in state_data.get("properties", []):
                            if "powerState" in prop:
                                power_status = prop["powerState"]
                                break
                        if device_id in monitored:
                            expected_power = monitored[device_id]["expected_power"]
                            if expected_power != "ignore" and power_status != expected_power:
                                print(f"- {device.get('deviceName')} power mismatch: expected {expected_power}, got {power_status}")
                                any_monitored_offline = True
                                if send_notifications and monitored[device_id].get("pushcut_url"):
                                    send_pushcut(
                                        monitored[device_id]["pushcut_url"],
                                        f"Govee Alert: {device.get('deviceName')}",
                                        "Device is unresponsive or power state mismatch"
                                    )
                else:
                    print(f"- {device.get('deviceName')} is UNRESPONSIVE (status code {state_response.status_code})")
                    if device_id in monitored:
                        any_monitored_offline = True
                        if send_notifications and monitored[device_id].get("pushcut_url"):
                            send_pushcut(
                                monitored[device_id]["pushcut_url"],
                                f"Govee Alert: {device.get('deviceName')}",
                                "Device is unresponsive or power state mismatch"
                            )
            except Exception as e:
                print(f"- {device.get('deviceName')} error: {e}")
                if device_id in monitored:
                    any_monitored_offline = True
                    if send_notifications and monitored[device_id].get("pushcut_url"):
                        send_pushcut(
                            monitored[device_id]["pushcut_url"],
                            f"Govee Alert: {device.get('deviceName')}",
                            "Device is unresponsive or power state mismatch"
                        )
        if any_monitored_offline:
            print("\nError: One or more monitored devices are unresponsive or have incorrect power state.")
            exit(1)
    except Exception as e:
        print(f"Error accessing Govee API: {e}")

def run_monitor(fail_mode="any"):
    if not os.path.exists(CONFIG_FILE):
        print(f"No config found at {CONFIG_FILE}. Please run 'config' first.")
        return

    with open(CONFIG_FILE) as f:
        config = json.load(f)

    api_key = config.get("govee_api_key")
    monitored_plugs = config.get("plugs", [])
    headers = {"Govee-API-Key": api_key}

    # Print monitored devices at start
    print(f"{time.ctime()}: Beginning monitoring of {len(monitored_plugs)} devices:")
    for plug in monitored_plugs:
        print(f" - {plug.get('name')} ({plug.get('device_id')})")

    fail_count = 0
    threshold = 3
    interval = 60

    print(f"Monitoring all configured plugs every {interval} seconds with fail mode '{fail_mode}'...")

    while True:
        try:
            all_fail = True
            for plug in monitored_plugs:
                device_id = plug.get("device_id")
                model = plug.get("model")
                name = plug.get("name")
                pushcut_url = plug.get("pushcut_url", config.get("pushcut_url", ""))
                try:
                    state_response = requests.get(
                        "https://developer-api.govee.com/v1/devices/state",
                        headers=headers,
                        params={"device": device_id, "model": model},
                        timeout=10
                    )
                    if state_response.status_code == 200:
                        state_data = state_response.json().get("data", {})
                        props = {p: v for d in state_data.get("properties", []) for p, v in d.items()}
                        online_status = props.get("online", True)
                        if online_status:
                            print(f"{time.ctime()}: Plug '{name}' is online.")
                            all_fail = False
                        else:
                            print(f"{time.ctime()}: Plug '{name}' is UNRESPONSIVE.")
                    else:
                        print(f"{time.ctime()}: Plug '{name}' response error (status {state_response.status_code})")
                except Exception as e:
                    print(f"{time.ctime()}: Plug '{name}' error: {e}")

            # Print check completion message at the end of the monitoring loop, before sleep
            print(f"{time.ctime()}: Check complete for all devices. Run marked successful.\n")

            should_alert = (all_fail if fail_mode == "all" else all_fail == False)
            if not should_alert:
                fail_count += 1
                if fail_count >= threshold:
                    print(f"{time.ctime()}: ALERT - Failure condition met for {threshold * interval} seconds.")
                    for plug in monitored_plugs:
                        pushcut_url = plug.get("pushcut_url", config.get("pushcut_url", ""))
                        if pushcut_url:
                            try:
                                r = requests.post(pushcut_url, timeout=10)
                                print(f"{time.ctime()}: Pushcut triggered for '{plug.get('name')}': {r.status_code}")
                            except Exception as ex:
                                print(f"{time.ctime()}: Error triggering Pushcut for '{plug.get('name')}': {ex}")
                    fail_count = 0
            else:
                fail_count = 0

            time.sleep(interval)
        except Exception as e:
            print(f"{time.ctime()}: Error during monitoring loop: {e}")
            time.sleep(interval)


# Generate systemd unit file for the monitor
def generate_systemd_unit(service_name="govee-smartplug-monitor.service", dry_run=True):
    """
    Generate a systemd unit file for running the monitor.
    """
    import os
    unit_file = f"""[Unit]
Description=Govee Smart Plug Monitor
After=network.target

[Service]
Type=simple
WorkingDirectory={os.getcwd()}
ExecStart=pdm run run
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
"""
    if dry_run:
        print(f"\n--- {service_name} ---\n{unit_file}\n--- End of {service_name} ---\n")
        print("To enable the service:")
        print("  sudo systemctl daemon-reexec")
        print(f"  sudo systemctl enable {service_name}")
        print(f"  sudo systemctl start {service_name}")
    else:
        with open(service_name, "w") as f:
            f.write(unit_file)
        print(f"Systemd unit file written to {service_name}")
        print("To enable the service:")
        print("  sudo systemctl daemon-reexec")
        print(f"  sudo systemctl enable {service_name}")
        print(f"  sudo systemctl start {service_name}")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Govee Smart Plug Monitor")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("config", help="Setup configuration")
    check_parser = subparsers.add_parser("check", help="Check configuration and show device states")
    check_parser.add_argument("--notify", action="store_true", help="Send Pushcut notifications on check failures")

    run_parser = subparsers.add_parser("run", help="Run the monitoring loop")
    run_parser.add_argument("--fail-mode", choices=["any", "all"], default="any", help="Fail if 'any' or 'all' plugs are unreachable")

    sysd_parser = subparsers.add_parser("generate-systemd", help="Generate a systemd unit file for the monitor")
    sysd_parser.add_argument("--dry-run", action="store_true", help="If set, only print the unit file (default)")

    args = parser.parse_args()

    if args.command == "config":
        write_config()
    elif args.command == "check":
        check_config(getattr(args, "notify", False))
    elif args.command == "run":
        run_monitor(fail_mode=args.fail_mode)
    elif args.command == "generate-systemd":
        # Default service name
        generate_systemd_unit(dry_run=args.dry_run)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()