# -*- coding: utf-8 -*-
"""
Battery sites monitor — SIMPLE
- Reads config.json (username/password/pin/url + sites with labels + expected_total)
- Logs in with straightforward selectors
- For each site: finds ONLY the batteries "N/M" inside that site's card
- Prints: "<Site>: N/M"
- Single pass, then exit
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
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
from webdriver_manager.chrome import ChromeDriverManager


# -------- utils --------

def script_dir() -> str:
    return os.path.dirname(os.path.abspath(__file__))

def load_config(filename: str = "config.json") -> dict:
    with open(os.path.join(script_dir(), filename), "r", encoding="utf-8") as f:
        return json.load(f)

def setup_driver(headless: bool = True) -> webdriver.Chrome:
    opts = webdriver.ChromeOptions()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1440,900")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)


# -------- simple login --------

def login(driver: webdriver.Chrome, auth: dict, timeout: int = 20):
    w = WebDriverWait(driver, timeout)
    driver.get(auth["url"])

    # Optional splash
    try:
        btn = w.until(EC.element_to_be_clickable((By.XPATH, "//*[text()='CONTINUE TO LOG IN']")))
        btn.click()
    except Exception:
        pass

    # Username
    user = w.until(EC.presence_of_element_located((By.XPATH, "//input[@name='username' or @id='username']")))
    user.clear(); user.send_keys(auth["username"])
    w.until(EC.element_to_be_clickable((By.XPATH, "//*[text()='CONTINUE' or text()='Continue']"))).click()

    # Password
    pwd = w.until(EC.presence_of_element_located((By.XPATH, "//input[@name='password' or @type='password']")))
    pwd.clear(); pwd.send_keys(auth["password"])
    w.until(EC.element_to_be_clickable((By.XPATH, "//*[text()='CONTINUE' or text()='Continue']"))).click()

    # Optional PIN
    try:
        pin = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, "//input[@placeholder='PIN' or @name='pin' or @type='password']"))
        )
        pin.clear(); pin.send_keys(auth.get("pin", "")); pin.send_keys(Keys.RETURN)
    except Exception:
        pass

    time.sleep(3)  # let the dashboard render


# -------- N/M finder (simple, in-card) --------

_RATIO_RE = re.compile(r"\b(\d+)\s*/\s*(\d+)\b")

def parse_ratio(s: str):
    m = _RATIO_RE.search(s or "")
    return (int(m.group(1)), int(m.group(2))) if m else None

def get_nm_for_site(driver: webdriver.Chrome, label: str, expected_total: int, timeout: int = 12):
    """
    Find the site title exactly, climb to its card (ancestor),
    then inside that card pick the first clean 'N/M' text.
    Prefer one that includes '/expected_total' if present.
    """
    w = WebDriverWait(driver, timeout)

    # 1) exact title
    title = w.until(EC.presence_of_element_located(
        (By.XPATH, f"//*[normalize-space(text())='{label}']"))
    )
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", title)

    # 2) find a reasonable card ancestor (a bit larger than the title)
    card = None
    cur = title
    for _ in range(8):
        parent = cur.find_element(By.XPATH, "./ancestor::*[1]")
        r = getattr(parent, "rect", None) or {}
        if r.get("width", 0) > 220 and r.get("height", 0) > 140:
            card = parent
            break
        cur = parent
    if card is None:
        # fallback: use the title's direct parent
        card = title.find_element(By.XPATH, "./ancestor::*[1]")

    # 3) inside card: prefer '/expected_total', else first valid 'N/M'
    def candidates():
        items = []
        for el in card.find_elements(By.XPATH, ".//*[contains(normalize-space(.), '/')]"):
            try:
                txt = " ".join(el.text.split())
                val = parse_ratio(txt)
                if not val:
                    continue
                score = (0 if f"/{expected_total}" in txt else 1, len(txt))
                items.append((score, txt, val))
            except StaleElementReferenceException:
                continue
        items.sort()
        return items

    end = time.time() + 2.0  # small settle window
    best = None
    while time.time() < end:
        cands = candidates()
        if cands:
            best = cands[0]
            # if we already matched expected_total or connected != 0, accept early
            (_, txt, (n, m)) = best
            if m == expected_total or n != 0:
                break
        time.sleep(0.1)

    if not best:
        raise TimeoutException(f"No N/M found in card for '{label}'")

    _, txt, (n, m) = best
    return n, m, txt


# -------- main (single pass) --------

def main():
    cfg = load_config("config.json")
    auth = cfg["auth"]
    settings = cfg.get("settings", {})
    sites = cfg["sites"]

    timeout = int(settings.get("timeout_sec", 20))
    headless = bool(settings.get("headless", True))

    driver = setup_driver(headless=headless)
    try:
        login(driver, auth, timeout=timeout)

        print("\n===== Battery Status (single pass) =====")
        for site in sites:
            label = site["label"]
            expected = int(site["expected_total"])
            try:
                n, m, raw = get_nm_for_site(driver, label, expected, timeout=timeout)
                # Just print "<Site>: N/M"
                print(f"{label}: {n}/{m}")
            except Exception as e:
                print(f"{label}: ERROR — {e}")

    finally:
        driver.quit()


if __name__ == "__main__":
    main()
