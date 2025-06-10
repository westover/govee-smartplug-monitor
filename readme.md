

# Govee Smart Plug Monitor

This tool monitors the status and power state of Govee smart plugs using the Govee Developer API. It can check whether plugs are responsive, verify power states, and optionally send Pushcut notifications if any devices go offline or deviate from expected behavior.

## Features

- Automatic configuration from your Govee API account
- Detection of online/offline devices
- Optional power state verification per plug
- Pushcut notification integration
- Systemd service generation
- CLI usage with configurable polling interval and failure behavior

---

## Setup Instructions

### 1. Install Dependencies

This project uses [PDM](https://pdm.fming.dev) for Python package and environment management.

```bash
pip install pdm
pdm install
```

### 2. Obtain Govee API Key

1. Visit [https://developer.govee.com](https://developer.govee.com)
2. Sign in or create an account
3. Navigate to **API Key** and copy your token

### 3. Configure the Monitor

Run the interactive configuration tool:

```bash
pdm run config
```

You'll be prompted to:
- Enter your Govee API key
- Choose to monitor all responsive devices (default yes)
- Choose to monitor any currently unresponsive devices (default no)
- Enter a Pushcut URL (optional) to send notifications
- Optionally configure expected power state (`on`/`off`) for each device

This will generate or update a `config.json` file with your settings.

---

## Running the Monitor

Use the following command to start the monitor loop:

```bash
pdm run run
```

This will:
- Poll your configured devices every 60 seconds (default)
- Log their online status
- Optionally validate expected power state
- Trigger a Pushcut notification for any failed check (if configured)
- Exit with non-zero status if a device fails (depending on `fail_mode`)

### Optional CLI flags

| Flag           | Description                            |
|----------------|----------------------------------------|
| `--interval`   | How often to poll (in seconds)         |
| `--fail-mode`  | `"any"` (default), `"all"`, or `"none"` |

---

## Manual Checks

To run a one-time check:

```bash
pdm run check
```

This displays the status of all Govee devices linked to your account and highlights which ones are being monitored.

---

## Systemd Service (Optional)

You can install and launch the monitor as a systemd service:

```bash
pdm run install-systemd
```

This will:
- Create a `govee-monitor.service` unit file
- Install it to `/etc/systemd/system/`
- Reload the systemd daemon
- Enable the service to start on boot
- Start the service immediately

### ✅ Verifying It’s Running

To check the status:

```bash
systemctl status govee-monitor.service
```

To see the logs:

```bash
journalctl -u govee-monitor.service -f
```

To stop or restart the service:

```bash
sudo systemctl stop govee-monitor.service
sudo systemctl restart govee-monitor.service
```

---

## License

MIT License