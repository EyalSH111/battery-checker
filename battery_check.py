from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time

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

    # CONTINUE TO LOG IN אם מופיע
    try:
        login_button = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//*[text()='CONTINUE TO LOG IN']"))
        )
        login_button.click()
        print("✅ CONTINUE TO LOG IN clicked")
    except:
        print("ℹ️ No CONTINUE TO LOG IN screen")

    # שם משתמש
    username_field = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@name='username']")))
    username_field.send_keys(USERNAME)
    print("✅ Username entered")

    continue_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[text()='CONTINUE']")))
    continue_button.click()
    print("➡️ Continue after username")

    # סיסמה
    password_field = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@name='password']")))
    password_field.send_keys(PASSWORD)
    print("✅ Password entered")

    continue_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[text()='CONTINUE']")))
    continue_button.click()
    print("➡️ Continue after password")

    # PIN אם מופיע
    try:
        pin_field = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, "//input[@placeholder='PIN' or @type='password']"))
        )
        pin_field.send_keys(PIN_CODE)
        pin_field.send_keys(Keys.RETURN)
        print("✅ PIN entered automatically")
    except:
        print("ℹ️ No PIN screen detected")

    time.sleep(5)

# ====== בדיקת Warburg3 ======
def check_warburg3(driver):
    wait = WebDriverWait(driver, TIMEOUT)
    try:
        # חיפוש הקופסה של Warburg3
        warburg_box = wait.until(
            EC.presence_of_element_located((By.XPATH, "//div[contains(text(), 'Warburg3')]"))
        )
        print("✅ Warburg3 box found")

        # חיפוש הערך של הסוללות בכל הדף
        batteries = wait.until(
            EC.presence_of_element_located((By.XPATH, "//*[contains(text(), '/66')]"))
        )
        value = batteries.text.strip()

        print(f"🔎 מצב הסוללות ב-Warburg3: {value}")

        if value == "66/66":
            print("✅ הכל מחובר כהלכה")
        else:
            print(f"⚠️ התנתקו סוללות! הערך הנוכחי: {value}")

    except Exception as e:
        print("⚠️ Warburg3 check failed:", e)
        print("📄 נסה לבדוק את ה-XPath של המספר בעזרת Inspect")

# ====== פונקציה ראשית ======
def main():
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    try:
        login(driver)
        check_warburg3(driver)
        print("⏹ Stopping script after Warburg3 check.")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
