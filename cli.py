import argparse
import json
import os
import requests
import time

# Helper: send pushcut notification
def send_pushcut_notification(pushcut_url, title, text):
    if not pushcut_url:
        print("Pushcut URL is missing; cannot send notification.")
        return

    message = {
        "title": title,
        "text": text,
    }

    try:
        response = requests.post(pushcut_url, json=message)
        if response.ok:
            print("Pushcut notification sent successfully.")
        else:
            print(f"Failed to send Pushcut notification: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"Error sending Pushcut notification: {e}")

def test_pushcut():
    if not os.path.exists(CONFIG_FILE):
        print(f"No config found at {CONFIG_FILE}. Please run 'config' first.")
        return

    with open(CONFIG_FILE) as f:
        config = json.load(f)

    pushcut_url = config.get("pushcut_url")
    if not pushcut_url:
        print("No Pushcut URL configured.")
        return

    send_pushcut_notification(pushcut_url, "Pushcut Test Notification", "This is a test from your Govee monitor setup.")
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

    # Prompt for polling interval and fail strategy
    interval = input("Polling interval in seconds (default 60): ").strip()
    if not interval.isdigit():
        interval = 60
    else:
        interval = int(interval)

    fail_mode = input("Fail strategy (any/all) [default: any]: ").strip().lower()
    if fail_mode not in {"any", "all"}:
        fail_mode = "any"

    config = {
        "govee_api_key": api_key,
        "pushcut_url": pushcut_url,
        "plugs": plugs,
        "interval": interval,
        "fail_mode": fail_mode
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

    # Load interval and fail_mode from config if available
    interval = config.get("interval", 60)
    fail_mode = config.get("fail_mode", fail_mode)

    # Print monitored devices at start
    print(f"{time.ctime()}: Beginning monitoring of {len(monitored_plugs)} devices:")
    for plug in monitored_plugs:
        print(f" - {plug.get('name')} ({plug.get('device_id')})")

    fail_count = 0
    threshold = 3

    print(f"Monitoring all configured plugs every {interval} seconds with fail mode '{fail_mode}'...")

    while True:
        try:
            all_fail = True
            for plug in monitored_plugs:
                device_id = plug.get("device_id")
                model = plug.get("model")
                name = plug.get("name")
                pushcut_url = plug.get("pushcut_url", config.get("pushcut_url", ""))
                power_expected = plug.get("expected_power", "ignore")
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
                        state = props.get("powerState", None)
                        failure = False
                        if online_status:
                            print(f"{time.ctime()}: Plug '{name}' is online.")
                            all_fail = False
                        else:
                            print(f"{time.ctime()}: Plug '{name}' is UNRESPONSIVE.")
                            failure = True
                            send_pushcut_notification(pushcut_url, "Govee Plug Alert", f"{name} is unresponsive or failed power check.")
                        # Power state check and Pushcut notification for mismatch
                        if power_expected != "ignore":
                            if state != power_expected:
                                print(f"{name} is in wrong power state (expected {power_expected}, got {state})")
                                failure = True
                                if pushcut_url:
                                    send_pushcut_notification(
                                        pushcut_url,
                                        "Govee Power State Alert",
                                        f"{name} is {str(state).upper()} but expected to be {str(power_expected).upper()}"
                                    )
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
                        send_pushcut_notification(pushcut_url, "Govee Plug Alert", f"{plug.get('name')} is unresponsive or failed power check.")
                    fail_count = 0
            else:
                fail_count = 0

            time.sleep(interval)
        except Exception as e:
            print(f"{time.ctime()}: Error during monitoring loop: {e}")
            time.sleep(interval)



# Generate and install the systemd unit file for the monitor
def generate_systemd_unit():
    import os
    import subprocess
    service_name = "govee-monitor.service"
    systemd_path = f"/etc/systemd/system/{service_name}"
    working_dir = os.getcwd()

    unit_file = f"""[Unit]
Description=Govee Smart Plug Monitor
After=network.target

[Service]
Type=simple
WorkingDirectory={working_dir}
ExecStart=pdm run run
Environment=PYTHONUNBUFFERED=1
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
"""

    try:
        with open("govee-monitor.service", "w") as f:
            f.write(unit_file)
        print("Local systemd unit file created: govee-monitor.service")

        print(f"Attempting to install systemd unit to {systemd_path}...")

        subprocess.run(["sudo", "cp", "govee-monitor.service", systemd_path], check=True)
        subprocess.run(["sudo", "systemctl", "daemon-reexec"], check=True)
        subprocess.run(["sudo", "systemctl", "enable", service_name], check=True)
        subprocess.run(["sudo", "systemctl", "start", service_name], check=True)

        print(f"Systemd service {service_name} installed and started.")
    except Exception as e:
        print(f"Error setting up systemd service: {e}")

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

    test_parser = subparsers.add_parser("test-pushcut", help="Send a test notification to Pushcut")
    test_parser.set_defaults(func=test_pushcut)

    args = parser.parse_args()

    if hasattr(args, "func"):
        args.func()
    elif args.command == "config":
        write_config()
    elif args.command == "check":
        check_config(getattr(args, "notify", False))
    elif args.command == "run":
        run_monitor(fail_mode=args.fail_mode)
    elif args.command == "generate-systemd":
        generate_systemd_unit()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()