# -*- coding: utf-8 -*-
"""
Battery Sites Monitor - STRICT denominator version
- Reads site list and expected totals from config.json
- Logs into Contel and, for each site, extracts ONLY ratios of the form N/expected_total
- No CSV output, no optional "recommended" guard in the loop
"""

import os
import json
import re
import time
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
def _extract_exact_ratio(text: str, expected_total: int):

    pairs = re.findall(r'\b(\d+)\s*/\s*(\d+)\b', text or '')
    exact = [(int(n), int(d)) for n, d in pairs if int(d) == expected_total]
    if not exact:
        return None
    sane = [p for p in exact if p[0] <= expected_total]
    n, d = max(sane or exact, key=lambda p: p[0])
    return f"{n}/{d}"


def log(msg):
    """Logger with timestamp."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}")


def script_dir() -> str:
    """Get the directory where this script is located."""
    return os.path.dirname(os.path.abspath(__file__))


def load_config(filename: str = "config.json") -> dict:
    """Load configuration from JSON file."""
    config_path = os.path.join(script_dir(), filename)
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def setup_driver(headless: bool = True) -> webdriver.Chrome:
    """Setup Chrome WebDriver with stable headless settings."""
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1440,900")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-search-engine-choice-screen")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)


def _click_visible_text(wait: WebDriverWait, label: str):
    """Click first visible element with exact text."""
    btn = wait.until(EC.element_to_be_clickable((By.XPATH, f"//*[normalize-space(text())='{label}']")))
    btn.click()
    return btn


def _screenshot(driver, name: str):
    """Save a full-page screenshot (helps when parsing fails)."""
    try:
        out_dir = os.path.join(script_dir(), "screenshots")
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, f"{datetime.now():%Y%m%d_%H%M%S}_{name}.png")
        driver.save_screenshot(path)
        log(f"📸 Saved screenshot: {path}")
    except Exception as e:
        log(f"⚠️ Screenshot failed: {e}")


def login(driver, auth, timeout=30):
    """
    Login flow:
      - Optional 'CONTINUE TO LOG IN'
      - username -> CONTINUE -> password -> CONTINUE
      - optional PIN
    """
    log("🔐 Starting login process...")
    wait = WebDriverWait(driver, timeout)
    driver.get(auth["url"])

    # Optional "CONTINUE TO LOG IN"
    try:
        _click_visible_text(wait, "CONTINUE TO LOG IN")
        log("✅ Clicked 'CONTINUE TO LOG IN'")
    except Exception:
        log("ℹ️  No 'CONTINUE TO LOG IN' button found")

    # Username
    log(f"👤 Entering username: {auth['username']}")
    user_xp = "//input[@name='username' or @type='text' or @autocomplete='username']"
    username_field = wait.until(EC.visibility_of_element_located((By.XPATH, user_xp)))
    username_field.clear()
    username_field.send_keys(auth["username"])

    # First CONTINUE
    _click_visible_text(wait, "CONTINUE")

    # Password
    log("🔑 Entering password...")
    pwd_xp = "//input[@name='password' or (@type='password' and not(@placeholder='PIN'))]"
    password_field = wait.until(EC.visibility_of_element_located((By.XPATH, pwd_xp)))
    password_field.clear()
    password_field.send_keys(auth["password"])

    # Second CONTINUE
    _click_visible_text(wait, "CONTINUE")

    # Optional PIN
    log("🔢 Checking for PIN field...")
    try:
        pin_xp = ("//input[contains(translate(@placeholder,'pin','PIN'),'PIN') "
                  "or contains(translate(@aria-label,'pin','PIN'),'PIN')]")
        pin_field = WebDriverWait(driver, 5).until(EC.visibility_of_element_located((By.XPATH, pin_xp)))
        log("✅ Found PIN field, entering PIN")
        pin_field.clear()
        pin_field.send_keys(auth.get("pin", ""))
        pin_field.send_keys(Keys.RETURN)
    except Exception:
        log("ℹ️  No PIN field found")

    # Let dashboard render
    log("⏳ Waiting for dashboard to load...")
    time.sleep(5)
    log("✅ Login completed successfully!")


def _find_site_card(driver, site_name, timeout=20):
    """
    Find the DOM element that contains the site's label (case-insensitive),
    then climb to the closest container/card ancestor.
    """
    wait = WebDriverWait(driver, timeout)
    site_el = wait.until(EC.presence_of_element_located((
        By.XPATH,
        f"//*[contains(translate(normalize-space(text()),"
        f"'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),"
        f"'{site_name.lower()}')]"
    )))
    card = site_el.find_element(
        By.XPATH,
        "./ancestor::*[contains(@class,'card') or contains(@class,'container') or "
        "contains(@class,'box') or self::li or self::section or self::div][1]"
    )
    return card


def _extract_exact_ratio(text: str, expected_total: int):
    """
    Return 'N/expected_total' found in text (exact denominator match).
    Prefer the largest N <= expected_total; if none, pick the largest N overall.
    """
    if not text:
        return None
    pairs = [(int(n), int(d)) for n, d in re.findall(r'\b(\d+)\s*/\s*(\d+)\b', text)]
    exact = [(n, d) for (n, d) in pairs if d == expected_total]
    if not exact:
        return None
    sane = [p for p in exact if p[0] <= expected_total]
    n, d = max(sane or exact, key=lambda p: p[0])
    return f"{n}/{d}"


def check_site_batteries(driver, site_name, expected_total, timeout=20):
    """
    מאתר את כרטיס/קונטיינר האתר, וקורא ממנו יחס רק בצורת N/expected_total.
    אם לא נמצא — מעלה TimeoutException (במקום להחזיר טקסט שגוי).
    """
    wait = WebDriverWait(driver, timeout)

    try:
        # חיפוש שם האתר (לא תלוי רישיות)
        site_el = wait.until(EC.presence_of_element_located((
            By.XPATH,
            f"//*[contains(translate(normalize-space(text()),"
            f"'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),"
            f"'{site_name.lower()}')]"
        )))

        # ננסה לטפס לאב שנראה כמו "כרטיס"/"קונטיינר"
        try:
            parent = site_el.find_element(
                By.XPATH,
                "./ancestor::*[contains(@class,'container') or contains(@class,'card') or "
                "contains(@class,'box') or self::div][1]"
            )
        except:
            parent = site_el

        # 1) נסה את כל הטקסט של הכרטיס
        text = (parent.get_attribute("innerText") or parent.text or "")
        ratio = _extract_exact_ratio(text, expected_total)
        if ratio:
            return ratio

        # 2) נסה את כל הצאצאים בתוך הכרטיס
        for el in parent.find_elements(By.XPATH, ".//*"):
            val = (el.get_attribute("innerText") or el.text or "").strip()
            if not val:
                continue
            ratio = _extract_exact_ratio(val, expected_total)
            if ratio:
                return ratio

        # 3) מוצא אחרון: חפש בכל העמוד אלמנטים שמכילים "/expected_total" אבל אמת דרך ה-regex
        cand_elems = driver.find_elements(By.XPATH, f"//*[contains(normalize-space(), '/{expected_total}')]")
        for el in cand_elems:
            val = (el.get_attribute("innerText") or el.text or "").strip()
            ratio = _extract_exact_ratio(val, expected_total)
            if ratio:
                return ratio

        # אם לא מצאנו יחס מתאים — נכשיל (כדי שלא נחזיר ערך לא נכון)
        raise TimeoutException(f"Site '{site_name}': could not find N/{expected_total}")

    except TimeoutException:
        # נפילה רכה כמו אצלך: נסה התאמת שם חלקית, אבל עדיין הכרחה למכנה מדויק
        try:
            all_divs = driver.find_elements(By.XPATH, "//div[text()]")
            for div in all_divs:
                try:
                    t = (div.text or "").strip()
                    if site_name.lower() in t.lower():
                        try:
                            parent = div.find_element(
                                By.XPATH,
                                "./ancestor::*[contains(@class,'container') or contains(@class,'card') or "
                                "contains(@class,'box') or self::div][1]"
                            )
                        except:
                            parent = div

                        val = (parent.get_attribute("innerText") or parent.text or "")
                        ratio = _extract_exact_ratio(val, expected_total)
                        if ratio:
                            return ratio

                        for el in parent.find_elements(By.XPATH, ".//*"):
                            v = (el.get_attribute("innerText") or el.text or "")
                            ratio = _extract_exact_ratio(v, expected_total)
                            if ratio:
                                return ratio
                except:
                    continue
        except:
            pass

        # אם גם זה לא הצליח — נכשיל כמו במקור
        raise



def check_all_sites_once(driver, sites, timeout=20):
    """Check all sites once and return results list."""
    results = []

    log(f"\n🔍 Starting battery check for {len(sites)} sites...")

    for i, site in enumerate(sites, 1):
        site_name = site["label"]
        expected = int(site["expected_total"])

        log(f"\n[{i:2d}/{len(sites)}] Checking {site_name} (expected: {expected})")

        try:
            ratio = check_site_batteries(driver, site_name, expected, timeout=timeout)

            if "/" in ratio:
                current, total = ratio.split("/")
                current_num = int(current)
                total_num = int(total)

                status = "✅ All connected" if current_num == total_num else "⚠️  Some disconnected"

                results.append({
                    "site": site_name,
                    "ratio": ratio,
                    "status": "success",
                    "current": current_num,
                    "total": total_num,
                    "all_connected": current_num == total_num
                })
                print(f"{site_name}: {ratio} - {status}")

            else:
                results.append({
                    "site": site_name,
                    "ratio": ratio,
                    "status": "success",
                    "current": None,
                    "total": None,
                    "all_connected": None
                })
                print(f"{site_name}: {ratio}")

        except Exception as e:
            results.append({
                "site": site_name,
                "ratio": None,
                "status": "error",
                "error": str(e),
                "current": None,
                "total": None,
                "all_connected": None
            })
            print(f"{site_name}: ❌ ERROR - {e}")

    return results


def print_summary(results):
    """Print a summary of all results."""
    successful = len([r for r in results if r["status"] == "success"])
    failed = len([r for r in results if r["status"] == "error"])
    all_connected = len([r for r in results if r.get("all_connected") is True])
    some_disconnected = len([r for r in results if r.get("all_connected") is False])

    log("\n" + "=" * 50)
    log("📊 SUMMARY REPORT")
    log("=" * 50)
    log(f"✅ Successful checks: {successful}")
    log(f"❌ Failed checks: {failed}")
    log(f"🔋 Sites fully connected: {all_connected}")
    log(f"⚠️  Sites with disconnections: {some_disconnected}")

    if some_disconnected > 0:
        log(f"\n⚠️  Sites with battery disconnections:")
        for result in results:
            if result.get("all_connected") is False:
                log(f"   - {result['site']}: {result['ratio']}")

    if failed > 0:
        log(f"\n❌ Sites with check failures:")
        for result in results:
            if result["status"] == "error":
                log(f"   - {result['site']}: {result.get('error', 'Unknown error')}")


def main():
    """Main function - single run mode."""
    log("🚀 Battery Monitor Starting...")

    try:
        # Load configuration
        config = load_config("config.json")
        auth = config["auth"]
        settings = config.get("settings", {})
        sites = config["sites"]

        timeout = int(settings.get("timeout_sec", 30))
        headless = bool(settings.get("headless", True))

        log(f"📋 Configuration loaded: {len(sites)} sites, timeout={timeout}s, headless={headless}")

        # Setup driver and login
        driver = setup_driver(headless=headless)
        try:
            login(driver, auth, timeout=timeout)

            # Check all sites once
            results = check_all_sites_once(driver, sites, timeout=timeout)

            # Print summary
            print_summary(results)

        finally:
            log("🔚 Closing browser...")
            driver.quit()

    except Exception as e:
        log(f"💥 FATAL ERROR: {type(e).__name__}: {e}")

    log("✅ Battery Monitor finished!")


def main_continuous():
    """Main function - continuous monitoring mode."""
    log("🚀 Battery Monitor Starting (Continuous Mode)...")

    try:
        config = load_config("config.json")
        auth = config["auth"]
        settings = config.get("settings", {})
        sites = config["sites"]

        timeout = int(settings.get("timeout_sec", 30))
        headless = bool(settings.get("headless", True))
        interval = int(settings.get("interval_sec", 300))  # 5 minutes default

        log(f"📋 Configuration: {len(sites)} sites, interval={interval}s")

        while True:
            driver = setup_driver(headless=headless)
            try:
                login(driver, auth, timeout=timeout)
                results = check_all_sites_once(driver, sites, timeout=timeout)
                print_summary(results)
            except Exception as e:
                log(f"💥 Error in monitoring cycle: {e}")
            finally:
                driver.quit()

            log(f"⏸️  Waiting {interval} seconds for next check...")
            time.sleep(interval)

    except KeyboardInterrupt:
        log("🛑 Monitor stopped by user")
    except Exception as e:
        log(f"💥 FATAL ERROR: {e}")


if __name__ == "__main__":
    # Run once by default
    # For continuous monitoring, call main_continuous() instead
    main()

    # Uncomment the line below for continuous monitoring every 5 minutes:
    # main_continuous()
