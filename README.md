# CS456 Mini Group Project 1

This project contains a small authentication service and a separate heartbeat monitor. The service sends one UDP heartbeat each second and crashes after a random delay. The monitor notices the missing heartbeats, prints an alert, and saves the incident to a JSON log. An attack script shows that fake or replayed heartbeats can fool the basic monitor.

## Requirements

- Python 3.10 or later
- Three terminal windows
- No third-party packages

All commands below start in the repository root.

## Standard execution

Terminal 1 starts the monitor:

```bash
python3 heartbeat_monitor.py
```

Terminal 2 starts the authentication service with its default random crash window of 12 to 24 seconds:

```bash
python3 critical_service.py
```

Terminal 3 sends a valid dummy authentication request:

```bash
python3 auth_client.py --username alice --password wonderland
```

The other test account is `bob` with password `builder`. Both accounts are only for this demo.

After the service exits, the monitor raises an alert once three expected beats are missing and 3.5 seconds have passed since the last valid datagram. The incident is appended to `monitor_incidents.jsonl`.

## Adversarial audit

For a spoofing test, start the monitor and service as above. In Terminal 3, begin injecting forged heartbeats before the service crashes:

```bash
python3 adversarial_audit.py --mode spoof --duration 30
```

The monitor still reports the service as healthy after the real process exits because it checks the message format but does not verify who sent it.

For a replay test, wait until the service has written `last_heartbeat.json`, then run:

```bash
python3 adversarial_audit.py --mode replay --capture-file last_heartbeat.json --duration 30
```

The monitor labels the repeated number as `duplicate-or-reordered`, but it still resets the timer. This is the replay weakness being demonstrated.

## Automated demonstration

This command runs a short two-part demo. Part 1 shows normal crash detection. Part 2 starts the attacker before the crash, shows fake heartbeats hiding the outage, and then shows the monitor alert after the attacker stops.

```bash
python3 run_demo.py
```

The demo uses shorter timing values so it finishes quickly. The normal settings are still one-second heartbeats and a 3.5-second timeout.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

The tests cover successful and failed authentication and structural heartbeat validation. The end-to-end behavior is exercised by `run_demo.py`.

## Architecture and parameters

The authentication service listens for TCP requests on port 5050. A background thread sends UDP heartbeat messages to the monitor on port 5051. Another background thread chooses a random crash time and shuts down the service with exit code 70.

The standard timing values are:

- Heartbeat interval T: 1.0 second
- Missed-beat threshold N: 3
- Timeout window W: 3.5 seconds
- Expected detection time: about 3.5 seconds after the last valid heartbeat

The extra half second allows for small timing delays. All of these values can be changed with command-line options.

## Security finding

The basic protocol is vulnerable to spoofing and replay because its messages are not signed. A stronger version should use an HMAC, reject old or repeated sequence numbers, check timestamps, and create a new session value after each restart.
