# -*- coding: utf-8 -*-
"""
Battery Sites Monitor - Complete Version
Based on working Warburg3 script logic, extended for all sites
Monitors all 20 battery sites and reports their connection status
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


def log(msg):
    """Logger with timestamp"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}")


def script_dir() -> str:
    """Get the directory where this script is located"""
    return os.path.dirname(os.path.abspath(__file__))


def load_config(filename: str = "config.json") -> dict:
    """Load configuration from JSON file"""
    config_path = os.path.join(script_dir(), filename)
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def setup_driver(headless: bool = True) -> webdriver.Chrome:
    """Setup Chrome WebDriver with optimal settings"""
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1440,900")

    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)


def login(driver, auth, timeout=30):
    """
    Login using the exact same logic as the working Warburg3 script
    """
    log("🔐 Starting login process...")
    wait = WebDriverWait(driver, timeout)
    driver.get(auth["url"])

    # Click "CONTINUE TO LOG IN" if present
    try:
        login_button = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//*[text()='CONTINUE TO LOG IN']"))
        )
        login_button.click()
        log("✅ Clicked 'CONTINUE TO LOG IN'")
    except:
        log("ℹ️  No 'CONTINUE TO LOG IN' button found")

    # Enter username
    log(f"👤 Entering username: {auth['username']}")
    username_field = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@name='username']")))
    username_field.send_keys(auth["username"])

    # Click first CONTINUE
    log("➡️  Clicking first CONTINUE...")
    continue_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[text()='CONTINUE']")))
    continue_button.click()

    # Enter password
    log("🔑 Entering password...")
    password_field = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@name='password']")))
    password_field.send_keys(auth["password"])

    # Click second CONTINUE
    log("➡️  Clicking second CONTINUE...")
    continue_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[text()='CONTINUE']")))
    continue_button.click()

    # Enter PIN if required
    log("🔢 Checking for PIN field...")
    try:
        pin_field = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, "//input[@placeholder='PIN' or @type='password']"))
        )
        log(f"✅ Found PIN field, entering PIN: {auth.get('pin', 'N/A')}")
        pin_field.send_keys(auth.get("pin", ""))
        pin_field.send_keys(Keys.RETURN)
    except:
        log("ℹ️  No PIN field found")

    log("⏳ Waiting for dashboard to load...")
    time.sleep(5)
    log("✅ Login completed successfully!")


def check_site_batteries(driver, site_name, expected_total, timeout=20):
    """
    Check battery status for a specific site
    Uses the same logic as the working Warburg3 script
    """
    wait = WebDriverWait(driver, timeout)

    try:
        # Find the site container/box
        site_box = wait.until(
            EC.presence_of_element_located((By.XPATH, f"//div[contains(text(), '{site_name}')]"))
        )

        # Look for the battery ratio with the expected total
        batteries = wait.until(
            EC.presence_of_element_located((By.XPATH, f"//*[contains(text(), '/{expected_total}')]"))
        )

        value = batteries.text.strip()

        # Extract just the ratio part (e.g., "65/66" from longer text)
        ratio_match = re.search(r'\d+/\d+', value)
        if ratio_match:
            return ratio_match.group(0)
        else:
            return value

    except TimeoutException:
        # If exact site name not found, try partial matching
        try:
            all_divs = driver.find_elements(By.XPATH, "//div[text()]")
            for div in all_divs:
                try:
                    text = div.text.strip()
                    if site_name.lower() in text.lower():
                        log(f"Found partial match for {site_name}: '{text}'")
                        # Try to find battery ratio near this element
                        parent = div.find_element(By.XPATH,
                                                  "./ancestor::*[contains(@class, 'container') or contains(@class, 'card') or contains(@class, 'box')][1]")
                        battery_elements = parent.find_elements(By.XPATH,
                                                                f".//*[contains(text(), '/{expected_total}')]")
                        if battery_elements:
                            value = battery_elements[0].text.strip()
                            ratio_match = re.search(r'\d+/\d+', value)
                            return ratio_match.group(0) if ratio_match else value
                except:
                    continue
        except:
            pass

        raise TimeoutException(f"Site '{site_name}' not found")


def check_all_sites_once(driver, sites, timeout=20):
    """Check all sites once and return results"""
    results = []

    log(f"\n🔍 Starting battery check for {len(sites)} sites...")

    for i, site in enumerate(sites, 1):
        site_name = site["label"]
        expected = int(site["expected_total"])

        log(f"\n[{i:2d}/{len(sites)}] Checking {site_name} (expected: {expected})")

        try:
            ratio = check_site_batteries(driver, site_name, expected, timeout=timeout)

            # Parse the ratio to check status
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
    """Print a summary of all results"""
    successful = len([r for r in results if r["status"] == "success"])
    failed = len([r for r in results if r["status"] == "error"])
    all_connected = len([r for r in results if r.get("all_connected") == True])
    some_disconnected = len([r for r in results if r.get("all_connected") == False])

    log(f"\n" + "=" * 50)
    log(f"📊 SUMMARY REPORT")
    log(f"=" * 50)
    log(f"✅ Successful checks: {successful}")
    log(f"❌ Failed checks: {failed}")
    log(f"🔋 Sites fully connected: {all_connected}")
    log(f"⚠️  Sites with disconnections: {some_disconnected}")

    if some_disconnected > 0:
        log(f"\n⚠️  Sites with battery disconnections:")
        for result in results:
            if result.get("all_connected") == False:
                log(f"   - {result['site']}: {result['ratio']}")

    if failed > 0:
        log(f"\n❌ Sites with check failures:")
        for result in results:
            if result["status"] == "error":
                log(f"   - {result['site']}: {result.get('error', 'Unknown error')}")


def main():
    """Main function - single run mode"""
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
    """Main function - continuous monitoring mode"""
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