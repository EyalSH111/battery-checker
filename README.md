Monitor how many batteries are online at each site by scraping your Contel (Ignition Perspective) dashboard.
The script reads a config.json, logs in, finds only the N / expected_total ratio per site, prints a summary, and (optionally) pops a Windows alert with a short beep when some batteries are disconnected.

✅ Built for Windows + Chrome. Uses Selenium and webdriver-manager (ChromeDriver auto-download).

Features

Strict parsing: extracts only ratios that match N/expected_total (prevents picking unrelated numbers on the card).

Per-site report: prints Site: N/M for each site.

Popup alerts (Windows): shows a top-most MessageBox + audible beep for sites with disconnected batteries.

Continuous mode: optional loop every 5 minutes (configurable).

Graceful stop: create a STOP file next to the script/EXE to end the loop after the current cycle.

Headless or visible Chrome (headless is default; switchable in config.json).

How it works

Logs into Contel (username → CONTINUE → password → CONTINUE → optional PIN).

For each site in config.json:

finds the site’s card by its label (case-insensitive),

scans only that card for ratios,

keeps only ratios whose denominator equals expected_total,

reports the largest numerator N ≤ expected_total found (safeguard against spurious matches).

Prints a summary and optionally pops a Windows alert for any site with disconnections.

Requirements

Windows 10/11

Chrome installed

Python 3.9+

Internet access to load the dashboard

The config.json file next to the script (or next to the EXE if you package it)

Install & Run (Python)
# 1) Clone / download this repo, then open PowerShell in the project folder
py -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2) Install deps
python -m pip install -U pip
pip install selenium webdriver-manager

# 3) Put your config.json next to the script (see sample below)

# 4) Run (single pass)
python "04.09 ALL site with popup.py"

Continuous mode (every 5 minutes)

Inside the script there’s a main_continuous() you can use. Easiest: keep settings.interval_sec in config.json (default is 300 seconds).

config.json (example)

Keep this next to the script (or EXE).
Credentials here are just placeholders—do not commit real passwords to Git.

{
  "auth": {
    "username": BLABLA,
    "password": "BLABLA",
    "pin": "**********",
    "url": "NOT_RELVENT"
  },
  "settings": {
    "timeout_sec": 30,
    "interval_sec": 300,
    "headless": true
  },
  "sites": [
    { "label": "BLABLA",  "expected_total": 66 },

}


Notes

headless: true runs Chrome in the background; set to false for debugging.

The script associates each site strictly with its expected_total. If the UI shows a different denominator, the script intentionally ignores it.

Windows Popup + Beep

When any site has N < M, the script raises a Windows MessageBox listing only those sites and plays a short beep.

If you run on a non-Windows OS, it falls back to printing the alert text to the console.

Build a Single-File EXE (PyInstaller)

Produces dist/BatteryMonitor.exe. Place config.json next to the EXE.

# From the project folder (PowerShell)
py -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install -U pip
pip install selenium webdriver-manager pyinstaller

pyinstaller --onefile --name BatteryMonitor "04.09 ALL site with popup.py"

# copy config next to the EXE
copy .\config.json .\dist\config.json
start .\dist

Run / Stop the EXE

Run: double-click BatteryMonitor.exe (ensure config.json is in the same folder).

Stop gracefully: create a file named STOP (no extension) next to the EXE.
The app exits after the current cycle (or immediately between cycles).

Emergency stop: close the console, press Ctrl+C, or kill the process in Task Manager.

Troubleshooting

ElementNotInteractable / No password field

Set "headless": false to watch the login flow.

The login page can change; the script tries common selectors and optional PIN. If your org’s SSO differs (iframes, captchas), you may need to adjust the XPaths in login().

Always returns 0/M or wrong site data

The dashboard sometimes shows multiple / values (e.g., power, irradiance). This tool only accepts N/expected_total in the same site card as the label. If your layout changes, update _find_site_card() or broaden the ancestor class filters.

Chrome/Driver mismatch

webdriver-manager auto-installs a compatible driver. Ensure Chrome is up-to-date.

Security

Do not commit real credentials. Add config.json to .gitignore or keep a redacted sample (config.sample.json).

Consider storing secrets securely (Windows Credential Manager, environment variables, or a vault) and loading them at runtime.

Roadmap

Optional CSV logging per run

Headless screenshots on failures

Email/Slack notifications

Docker image (non-Windows popup alternatives)
