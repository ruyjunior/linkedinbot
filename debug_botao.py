"""
Roda este script para descobrir o aria-label exato do botão Easy Apply.
Execute: python debug_botao.py
"""
import json, time, random
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

config = json.loads(Path("config.json").read_text(encoding="utf-8"))

options = Options()
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option("useAutomationExtension", False)
options.add_argument("--window-size=1366,768")

import os, zipfile, urllib.request, winreg

def get_driver():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Google\Chrome\BLBeacon")
        version, _ = winreg.QueryValueEx(key, "version")
        major = version.split(".")[0]
    except Exception:
        major = "124"
    cache_dir = os.path.expanduser(f"~/.wdm/drivers/chromedriver/win64/{major}")
    exe = os.path.join(cache_dir, "chromedriver.exe")
    if not os.path.exists(exe):
        print("ChromeDriver não encontrado no cache, baixando...")
        import json as _json
        with urllib.request.urlopen(
            "https://googlechromelabs.github.io/chrome-for-testing/latest-patch-versions-per-build.json",
            timeout=10
        ) as r:
            data = _json.loads(r.read())
        builds = data.get("builds", {})
        build_key = next((k for k in builds if k.startswith(major)), None)
        full_version = builds[build_key]["version"] if build_key else f"{major}.0.0.0"
        zip_url = f"https://storage.googleapis.com/chrome-for-testing-public/{full_version}/win64/chromedriver-win64.zip"
        os.makedirs(cache_dir, exist_ok=True)
        zip_path = os.path.join(cache_dir, "chromedriver-win64.zip")
        urllib.request.urlretrieve(zip_url, zip_path)
        with zipfile.ZipFile(zip_path, "r") as z:
            for member in z.namelist():
                if member.endswith("chromedriver.exe"):
                    z.extract(member, cache_dir)
                    os.rename(os.path.join(cache_dir, member), exe)
                    break
    return webdriver.Chrome(service=Service(executable_path=exe), options=options)

driver = get_driver()
wait = WebDriverWait(driver, 15)

# Login
print("Fazendo login...")
driver.get("https://www.linkedin.com/login")
time.sleep(2)
email_f = wait.until(EC.presence_of_element_located((By.ID, "username")))
email_f.send_keys(config["email"])
time.sleep(0.5)
driver.find_element(By.ID, "password").send_keys(config["password"])
time.sleep(0.5)
driver.find_element(By.ID, "password").send_keys(Keys.RETURN)
time.sleep(4)

if "checkpoint" in driver.current_url or "challenge" in driver.current_url:
    input("Resolva a verificação no navegador e pressione ENTER aqui...")

print(f"URL após login: {driver.current_url}")

# Busca
from urllib.parse import quote_plus
kws = config["search"]["keywords"]
loc = config["search"]["location"]
url = f"https://www.linkedin.com/jobs/search/?keywords={quote_plus(' '.join(kws))}&location={quote_plus(loc)}&f_AL=true&f_TPR=r604800&sortBy=DD"
print(f"\nAbrindo busca: {url}")
driver.get(url)
time.sleep(5)

# Clica no primeiro card
cards = driver.find_elements(By.CSS_SELECTOR, "li.jobs-search-results__list-item, li.occludable-update")
print(f"\n{len(cards)} cards encontrados.")

for i, card in enumerate(cards[:5]):
    print(f"\n--- Card {i+1} ---")
    driver.execute_script("arguments[0].scrollIntoView({block:'center'})", card)
    time.sleep(0.5)
    card.click()
    time.sleep(3)

    # Imprime TODOS os botões visíveis na página
    buttons = driver.find_elements(By.TAG_NAME, "button")
    print(f"Botões encontrados ({len(buttons)}):")
    for btn in buttons:
        try:
            txt = btn.text.strip()
            aria = btn.get_attribute("aria-label") or ""
            cls = btn.get_attribute("class") or ""
            if btn.is_displayed() and (txt or aria):
                print(f"  texto='{txt}' | aria-label='{aria}' | classes='{cls[:60]}'")
        except Exception:
            continue

    print("\nPressione ENTER para ver o próximo card (ou Ctrl+C para sair)...")
    input()

driver.quit()
print("Pronto!")
