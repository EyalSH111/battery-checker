from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
from datetime import datetime

# ====== פרטי התחברות ======
USERNAME = "BL_monitoring"
PASSWORD = "9C9wEJ7>i2Uy"
PIN_CODE = "192837"
URL = "https://view.contelsmart.com/data/perspective/client/Energynie"
TIMEOUT = 20

# ====== פונקציית התחברות ======
def login(driver):
    wait = WebDriverWait(driver, TIMEOUT)
    driver.get(URL)

    try:
        login_button = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//*[text()='CONTINUE TO LOG IN']"))
        )
        login_button.click()
    except:
        pass

    username_field = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@name='username']")))
    username_field.send_keys(USERNAME)

    continue_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[text()='CONTINUE']")))
    continue_button.click()

    password_field = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@name='password']")))
    password_field.send_keys(PASSWORD)

    continue_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[text()='CONTINUE']")))
    continue_button.click()

    try:
        pin_field = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, "//input[@placeholder='PIN' or @type='password']"))
        )
        pin_field.send_keys(PIN_CODE)
        pin_field.send_keys(Keys.RETURN)
    except:
        pass

    time.sleep(5)

# ====== בדיקת Warburg3 ======
def check_warburg3(driver):
    wait = WebDriverWait(driver, TIMEOUT)
    try:
        warburg_box = wait.until(
            EC.presence_of_element_located((By.XPATH, "//div[contains(text(), 'Warburg3')]"))
        )
        batteries = wait.until(
            EC.presence_of_element_located((By.XPATH, "//*[contains(text(), '/66')]"))
        )
        value = batteries.text.strip()

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] 🔎 Battery status-Warburg3: {value}")

        if value == "66/66":
            print("✅ All connected \n")
        else:
            print(f"⚠️Some have disconnect:num of battery is:  {value}\n")

    except Exception as e:
        print("⚠️ Warburg3 check failed:", e)

# ====== פונקציה ראשית ======
def main():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")   # מצב ללא חלון
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    try:
        login(driver)

        while True:
            check_warburg3(driver)
            print("⏸️ Wait 5 minute for next run\n")
            time.sleep(300)  # 5 דקות
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
