

import os
import sys
import json
import re
import time
from pathlib import Path
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException, ElementNotInteractableException

# -------------- utils --------------

def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")

def script_dir() -> str:
    """Folder of script/EXE (works under PyInstaller)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def load_config(filename: str = "config.json") -> dict:
    with open(os.path.join(script_dir(), filename), "r", encoding="utf-8") as f:
        return json.load(f)

def setup_driver(headless: bool = True) -> webdriver.Chrome:
    """
    Prefer Selenium Manager (no external download). Fall back to webdriver_manager if needed.
    """
    from selenium.webdriver.chrome.options import Options
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1440,900")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--disable-extensions")
    opts.add_argument("--lang=en-US")
    # optional: block images to reduce noise
    opts.add_experimental_option("prefs", {
        "profile.managed_default_content_settings.images": 2
    })
    try:
        # Selenium Manager (Chrome must be installed)
        return webdriver.Chrome(options=opts)
    except Exception:
        # Fallback to webdriver_manager
        from webdriver_manager.chrome import ChromeDriverManager
        return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)

# -------------- login helpers --------------

def _click_visible_text(wait: WebDriverWait, label: str):
    """Click first visible element with EXACT visible text."""
    el = wait.until(EC.element_to_be_clickable((By.XPATH, f"//*[normalize-space(text())='{label}']")))
    el.click()
    return el

def _safe_type(driver, el, value: str):
    """
    Type reliably; if element not interactable, set via JS and dispatch events.
    """
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
    except Exception:
        pass
    try:
        el.clear()
    except Exception:
        try:
            el.send_keys(Keys.CONTROL, "a")
            el.send_keys(Keys.DELETE)
        except Exception:
            pass
    try:
        el.send_keys(value)
        return
    except ElementNotInteractableException:
        pass
    except Exception:
        pass
    # JS fallback
    driver.execute_script("""
        const el = arguments[0], v = arguments[1];
        if (el) {
          try { el.focus(); } catch(e) {}
          try { el.value = v; } catch(e) {}
          try { el.setAttribute('value', v); } catch(e) {}
          try { el.dispatchEvent(new Event('input', {bubbles:true})); } catch(e) {}
          try { el.dispatchEvent(new Event('change', {bubbles:true})); } catch(e) {}
        }
    """, el, value)

def login(driver: webdriver.Chrome, auth: dict, timeout: int = 30):

    log("🔐 Logging in...")
    w = WebDriverWait(driver, timeout)
    driver.get(auth["url"])

    # Optional splash
    try:
        _click_visible_text(w, "CONTINUE TO LOG IN")
        log("… clicked CONTINUE TO LOG IN")
    except Exception:
        pass

    # Username
    u = w.until(EC.visibility_of_element_located((By.XPATH, "//input[@name='username' or @type='text' or @autocomplete='username' or @id='username']")))
    _safe_type(driver, u, auth["username"])
    _click_visible_text(w, "CONTINUE")

    # Password
    p = w.until(EC.visibility_of_element_located((By.XPATH, "//input[@name='password' or (@type='password' and not(@placeholder='PIN'))]")))
    _safe_type(driver, p, auth["password"])
    _click_visible_text(w, "CONTINUE")

    # Optional PIN
    try:
        pin = WebDriverWait(driver, 5).until(EC.visibility_of_element_located((By.XPATH, "//input[contains(translate(@placeholder,'pin','PIN'),'PIN') or contains(translate(@aria-label,'pin','PIN'),'PIN')]")))
        _safe_type(driver, pin, auth.get("pin", ""))
        pin.send_keys(Keys.RETURN)
    except Exception:
        pass

    time.sleep(3)  # let dashboard render
    log("✅ Login OK")

# -------------- ratio extraction (STRICT, card-scoped) --------------

_RATIO_RE = re.compile(r"\b(\d+)\s*/\s*(\d+)\b")

def _extract_exact_ratio(text: str, expected_total: int):
    """
    Return 'N/expected_total' found in text (exact denominator match).
    Prefer the largest N <= expected_total; if none, pick the largest N overall.
    """
    if not text:
        return None
    pairs = [(int(n), int(d)) for n, d in _RATIO_RE.findall(text)]
    exact = [(n, d) for (n, d) in pairs if d == expected_total]
    if not exact:
        return None
    sane = [p for p in exact if p[0] <= expected_total]
    n, d = max(sane or exact, key=lambda p: p[0])
    return f"{n}/{d}"

def check_site_batteries(driver: webdriver.Chrome, site_name: str, expected_total: int, timeout: int = 20) -> str:
    """
    Find the site by EXACT title text; search ONLY inside its card/container
    for ratios matching N/expected_total. Returns 'N/expected_total' or raises TimeoutException.
    """
    w = WebDriverWait(driver, timeout)

    # exact title (avoid cross-picking)
    title = w.until(EC.presence_of_element_located((By.XPATH, f"//*[normalize-space(text())='{site_name}']")))
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", title)
    except Exception:
        pass

    # climb to a reasonable card ancestor (size/class heuristic)
    card = None
    cur = title
    for _ in range(10):
        parent = cur.find_element(By.XPATH, "./ancestor::*[1]")
        r = getattr(parent, "rect", None) or {}
        if r.get("width", 0) > 220 and r.get("height", 0) > 140:
            card = parent
            break
        cur = parent
    if card is None:
        card = title.find_element(By.XPATH, "./ancestor::*[1]")

    # 1) try full card text
    txt = (card.get_attribute("innerText") or card.text or "")
    ratio = _extract_exact_ratio(txt, expected_total)
    if ratio:
        return ratio

    # 2) try descendants (still scoped to the card)
    for el in card.find_elements(By.XPATH, ".//*[contains(normalize-space(.), '/')]"):
        try:
            val = (el.get_attribute("innerText") or el.text or "").strip()
            if not val:
                continue
            ratio = _extract_exact_ratio(val, expected_total)
            if ratio:
                return ratio
        except StaleElementReferenceException:
            continue

    raise TimeoutException(f"Site '{site_name}': could not find N/{expected_total} in its card")

# -------------- one cycle + summary --------------

def check_all_sites_once(driver, sites, timeout=20):
    results = []
    log(f"\n===== Battery Status: checking {len(sites)} sites =====")
    for i, site in enumerate(sites, 1):
        label = site["label"]
        expected = int(site["expected_total"])
        log(f"[{i:02d}/{len(sites)}] {label} (expected {expected})")
        try:
            ratio = check_site_batteries(driver, label, expected, timeout=timeout)
            n, m = map(int, ratio.split("/"))
            all_ok = (n == m)
            results.append({
                "site": label,
                "ratio": ratio,
                "status": "success",
                "current": n,
                "total": m,
                "all_connected": all_ok
            })
            print(f"{label}: {ratio} — {'✅ All connected' if all_ok else '⚠️ Some disconnected'}")
        except Exception as e:
            results.append({
                "site": label,
                "ratio": None,
                "status": "error",
                "error": str(e),
                "current": None,
                "total": None,
                "all_connected": None
            })
            print(f"{label}: ❌ ERROR — {e}")
    return results

def print_summary(results):
    ok = sum(1 for r in results if r.get("all_connected") is True)
    err = sum(1 for r in results if r.get("status") == "error")
    disc = sum(1 for r in results if r.get("all_connected") is False)
    log("\n----- SUMMARY -----")
    log(f"✅ Fully connected: {ok}")
    log(f"⚠️ With disconnections: {disc}")
    log(f"❌ Errors: {err}")
    if disc:
        log("Disconnected sites:")
        for r in results:
            if r.get("all_connected") is False:
                log(f"  - {r['site']}: {r['current']}/{r['total']} (disc: {r['total'] - r['current']})")

# -------------- popup + beep --------------

def popup_disconnected(results, title="Battery Alerts", beep=True):
    """
    Windows popup for only disconnected sites. Plays a short system beep first.
    Returns True if a popup was shown, False otherwise.
    """
    lines = []
    for r in results:
        if r.get("status") == "success" and r.get("all_connected") is False:
            disc = r["total"] - r["current"]
            lines.append(f"{r['site']}: {r['current']}/{r['total']} (disconnected: {disc})")

    if not lines:
        return False

    msg = "\n".join(lines)

    # Beep (Windows)
    if beep:
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        except Exception:
            try:
                import ctypes
                ctypes.windll.user32.MessageBeep(0x00000030)  # MB_ICONWARNING
            except Exception:
                pass

    # Popup (Windows, topmost)
    try:
        import ctypes
        MB_OK = 0x00000000
        MB_TOPMOST = 0x00040000
        MB_ICONWARNING = 0x00000030
        ctypes.windll.user32.MessageBoxW(None, msg, title, MB_OK | MB_TOPMOST | MB_ICONWARNING)
        return True
    except Exception:
        print("[POPUP]\n" + msg)
        return False

# -------------- STOP support --------------

def stop_file_path() -> Path:
    return Path(script_dir()) / "STOP"

def should_stop() -> bool:
    return stop_file_path().exists()

def sleep_with_stop(wait_seconds: int):
    """Sleep in 1s steps so we can react quickly to STOP file."""
    for _ in range(int(wait_seconds)):
        if should_stop():
            break
        time.sleep(1)

# -------------- main (continuous) --------------

def main_continuous():
    """Run forever, sleeping settings.interval_sec between cycles. Create 'STOP' file to exit."""
    try:
        cfg = load_config("config.json")
        auth = cfg["auth"]
        settings = cfg.get("settings", {})
        sites = cfg["sites"]

        timeout = int(settings.get("timeout_sec", 30))
        headless = bool(settings.get("headless", True))
        interval = int(settings.get("interval_sec", 300))  # default 5 min

        log(f"🚀 Monitor starting — {len(sites)} sites, interval={interval}s, headless={headless}")
        log(f"ℹ️ To stop gracefully, create file: {stop_file_path()}")

        while True:
            if should_stop():
                log("🛑 STOP file detected before cycle — exiting.")
                break

            driver = setup_driver(headless=headless)
            cycle_start = time.time()
            try:
                login(driver, auth, timeout=timeout)
                results = check_all_sites_once(driver, sites, timeout=timeout)
                print_summary(results)
                popup_disconnected(results)
                log(f"✅ Finished full check at {datetime.now():%Y-%m-%d %H:%M:%S}")
            except Exception as e:
                log(f"💥 Cycle error: {e}")
            finally:
                try:
                    driver.quit()
                except Exception:
                    pass

            # wait to next cycle (early exit if STOP appears)
            elapsed = time.time() - cycle_start
            wait_sec = max(0, interval - int(elapsed))
            log(f"⏸️ Waiting up to {wait_sec} seconds… (create 'STOP' file to exit)")
            sleep_with_stop(wait_sec)

            if should_stop():
                log("🛑 STOP file detected during wait — exiting.")
                break

    except KeyboardInterrupt:
        log("🛑 Stopped by user (Ctrl+C)")
    except Exception as e:
        log(f"💥 FATAL: {e}")

# -------------- optional single pass --------------

def main():
    cfg = load_config("config.json")
    auth = cfg["auth"]
    settings = cfg.get("settings", {})
    sites = cfg["sites"]

    timeout = int(settings.get("timeout_sec", 30))
    headless = bool(settings.get("headless", True))

    driver = setup_driver(headless=headless)
    try:
        login(driver, auth, timeout=timeout)
        results = check_all_sites_once(driver, sites, timeout=timeout)
        print_summary(results)
        popup_disconnected(results)
    finally:
        driver.quit()

if __name__ == "__main__":
    # Continuous mode (every 5 min by default)
    main_continuous()
    # For a single pass instead, comment the line above and uncomment:
    # main()
