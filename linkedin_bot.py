"""
LinkedIn Job Application Bot
Roda localmente no Windows. Configurações em config.json.
"""

import json
import time
import random
import logging
import csv
import os
from datetime import datetime
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.edge.options import Options
from selenium.webdriver.edge.service import Service
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, ElementClickInterceptedException
)
from webdriver_manager.microsoft import EdgeChromiumDriverManager

# ── Logging ──────────────────────────────────────────────────────────────────
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
log_file = LOG_DIR / f"bot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
CONFIG_FILE = Path("config.json")

def load_config():
    if not CONFIG_FILE.exists():
        log.error("config.json não encontrado. Execute setup.py primeiro.")
        raise FileNotFoundError("config.json não encontrado.")
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

# ── CSV de resultados ─────────────────────────────────────────────────────────
RESULTS_FILE = Path("candidaturas.csv")

def save_result(title, company, url, status, note=""):
    file_exists = RESULTS_FILE.exists()
    with open(RESULTS_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["data", "titulo", "empresa", "url", "status", "observacao"])
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            title, company, url, status, note
        ])

# ── Delay humano ──────────────────────────────────────────────────────────────
def human_delay(min_s=1.5, max_s=4.0):
    time.sleep(random.uniform(min_s, max_s))

def human_type(element, text):
    """Digita caractere por caractere simulando humano."""
    element.clear()
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(0.04, 0.12))

# ── Mapeamento de campos conhecidos ──────────────────────────────────────────
def get_known_answer(label_text: str, profile: dict) -> str | None:
    lt = label_text.lower()
    if any(k in lt for k in ["nome", "name", "full name"]):
        return profile.get("nome", "")
    if any(k in lt for k in ["telefone", "celular", "phone", "mobile"]):
        return profile.get("telefone", "")
    if any(k in lt for k in ["experiência", "anos de", "experience", "years of", "how many years"]):
        return str(profile.get("experiencia_anos", ""))
    if any(k in lt for k in ["salário", "pretensão", "salary", "compensation", "expectation", "gross"]):
        return str(profile.get("salario", ""))
    if any(k in lt for k in ["inglês", "english", "proficiency in english"]):
        # Mapeia nível de inglês para opções do LinkedIn em inglês
        nivel = profile.get("ingles", "Básico").lower()
        if any(k in nivel for k in ["básico", "basico", "none", "nenhum"]):
            return "None"
        if any(k in nivel for k in ["intermediário", "intermediario", "conversational", "básico avançado"]):
            return "Conversational"
        if any(k in nivel for k in ["avançado", "avancado", "professional", "profissional"]):
            return "Professional"
        if any(k in nivel for k in ["fluente", "fluent", "native", "bilingual", "nativo"]):
            return "Native or bilingual"
        return "Conversational"
    if any(k in lt for k in ["disponibilidade", "availability", "início", "start"]):
        return profile.get("disponibilidade", "")
    if any(k in lt for k in ["cidade", "localização", "city", "location"]):
        return profile.get("cidade", "")
    if any(k in lt for k in ["linkedin", "linkedin url", "linkedin profile", "profile url", "linkedin.com"]):
        return profile.get("linkedin_url", "")
    if any(k in lt for k in ["nível", "nivel", "senioridade", "seniority", "junior", "pleno", "senior",
                               "considera", "experiência profissional", "perfil profissional"]):
        nivel = profile.get("experiencia_anos", "5")
        try:
            anos = int(nivel)
        except Exception:
            anos = 5
        if anos <= 2:
            return "Júnior"
        elif anos <= 5:
            return "Pleno"
        else:
            return "Sênior"
    if any(k in lt for k in ["apresentação", "cover", "sobre", "about", "summary"]):
        return profile.get("cover_letter", "")
    # Perguntas Yes/No genéricas — responde Yes por padrão
    if any(k in lt for k in ["are you ", "do you ", "have you ", "can you ", "will you ",
                               "você ", "possui ", "tem experiência", "está "]):
        return "Yes"
    # Phone country code
    if any(k in lt for k in ["country code", "código do país", "phone country"]):
        return "Brazil"
    return None

# ── Driver ────────────────────────────────────────────────────────────────────
def create_driver(headless=False):
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--window-size=1366,768")

    # Usa perfil exclusivo do bot — não conflita com Edge aberto
    # Na primeira vez faz login manual; depois reutiliza a sessão
    import os as _os
    profile_dir = r"C:\Users\ruyju\Documents\dev\linkedin_bot\edge_profile"
    _os.makedirs(profile_dir, exist_ok=True)
    options.add_argument(f"--user-data-dir={profile_dir}")
    options.add_argument("--profile-directory=Default")

    # EdgeDriver já vem instalado com o Edge no Windows — não precisa baixar
    import os, glob
    possible_paths = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedgedriver.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedgedriver.exe",
    ]
    # Tenta encontrar msedgedriver.exe dentro da pasta de instalação do Edge
    edge_app = r"C:\Program Files (x86)\Microsoft\Edge\Application"
    if not os.path.exists(edge_app):
        edge_app = r"C:\Program Files\Microsoft\Edge\Application"
    found = glob.glob(os.path.join(edge_app, "**", "msedgedriver.exe"), recursive=True)
    if found:
        possible_paths.insert(0, found[0])

    driver_path = None
    for p in possible_paths:
        if os.path.exists(p):
            driver_path = p
            break

    if not driver_path:
        # Último recurso: tenta pelo PATH do sistema
        import shutil
        driver_path = shutil.which("msedgedriver") or shutil.which("msedgedriver.exe")

    if not driver_path:
        # Tenta na pasta do próprio projeto
        local = os.path.join(os.path.dirname(os.path.abspath(__file__)), "msedgedriver.exe")
        if os.path.exists(local):
            driver_path = local
        else:
            raise FileNotFoundError(
                "msedgedriver.exe não encontrado automaticamente.\n"
                "Solução: abra o Edge, vá em edge://settings/help e veja a versão (ex: 147.0.3912.xx)\n"
                "Baixe o driver correspondente em: https://msedgewebdriverstorage.blob.core.windows.net/edgewebdriver/LATEST_STABLE\n"
                "Descompacte e coloque o msedgedriver.exe na pasta: C:\\Users\\ruyju\\Documents\\dev\\linkedin_bot\\"
            )

    log.info(f"Usando EdgeDriver: {driver_path}")
    service = Service(executable_path=driver_path)
    driver = webdriver.Edge(service=service, options=options)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return driver

# ── Login ─────────────────────────────────────────────────────────────────────
def login(driver, email, password):
    log.info("Verificando sessão no LinkedIn...")
    driver.get("https://www.linkedin.com/feed/")
    human_delay(3, 5)

    # Já está logado se caiu no feed
    if "feed" in driver.current_url or "mynetwork" in driver.current_url:
        log.info("Sessão ativa — login não necessário.")
        return True

    # Não está logado — faz login normalmente
    log.info("Sessão expirada. Fazendo login...")
    driver.get("https://www.linkedin.com/login")
    wait = WebDriverWait(driver, 15)

    email_field = wait.until(EC.presence_of_element_located((By.ID, "username")))
    human_type(email_field, email)
    human_delay(0.5, 1.2)

    pass_field = driver.find_element(By.ID, "password")
    human_type(pass_field, password)
    human_delay(0.5, 1.0)

    pass_field.send_keys(Keys.RETURN)
    human_delay(3, 5)

    if "checkpoint" in driver.current_url or "challenge" in driver.current_url:
        log.warning("LinkedIn pediu verificação! Resolva manualmente na janela aberta.")
        input("Pressione ENTER aqui depois de resolver a verificação no navegador...")

    if "feed" in driver.current_url or "mynetwork" in driver.current_url:
        log.info("Login realizado com sucesso.")
        return True

    log.error(f"Falha no login. URL atual: {driver.current_url}")
    return False

# ── Busca de vagas ────────────────────────────────────────────────────────────
def search_jobs(driver, keywords, location, date_filter="r86400"):
    """
    Clica em cada card da lista e verifica Easy Apply no painel lateral.
    Mais confiável que confiar no filtro f_AL=true da URL.
    """
    from urllib.parse import quote_plus
    primary_kw = keywords[0] if keywords else "desenvolvedor"
    query = quote_plus(primary_kw)
    # LinkedIn aceita melhor o nome do país em português com geoId
    # Brasil = geoId 106057199
    url = (
        f"https://www.linkedin.com/jobs/search/"
        f"?keywords={query}"
        f"&geoId=106057199"
        f"&f_AL=true"
        f"&f_TPR={date_filter}"
        f"&sortBy=DD&start=0"
    )
    log.info(f"Buscando vagas: {url}")
    driver.get(url)
    human_delay(4, 6)

    wait = WebDriverWait(driver, 20)
    jobs = []

    try:
        wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR,
             "li.jobs-search-results__list-item, li.occludable-update, [data-job-id]")
        ))
        human_delay(2, 3)

        # Scroll para carregar todos os cards
        try:
            list_el = driver.find_element(
                By.CSS_SELECTOR, ".jobs-search__results-list, .scaffold-layout__list"
            )
            for _ in range(3):
                driver.execute_script("arguments[0].scrollTop += 800", list_el)
                human_delay(0.6, 1.0)
            driver.execute_script("arguments[0].scrollTop = 0", list_el)
            human_delay(1, 1.5)
        except Exception:
            pass

        cards = driver.find_elements(
            By.CSS_SELECTOR,
            "li.jobs-search-results__list-item, li.occludable-update"
        )
        log.info(f"{len(cards)} cards na lista. Filtrando por Easy Apply e relevância...")

        seen_ids = set()
        for i, card in enumerate(cards):
            try:
                # Extrai título e link diretamente do HTML do card — sem clicar
                title = ""
                job_link = ""
                company = ""

                for sel in [".job-card-list__title--link", ".job-card-container__link",
                             "a[href*='/jobs/view/']"]:
                    try:
                        el = card.find_element(By.CSS_SELECTOR, sel)
                        title = el.text.strip().split("\n")[0]
                        href = el.get_attribute("href") or ""
                        if href:
                            job_link = href.split("?")[0]
                        break
                    except NoSuchElementException:
                        continue

                for sel in [".artdeco-entity-lockup__subtitle",
                             ".job-card-container__primary-description",
                             ".job-card-container__company-name"]:
                    try:
                        company = card.find_element(By.CSS_SELECTOR, sel).text.strip()
                        break
                    except NoSuchElementException:
                        continue

                if not title or not job_link or job_link in seen_ids:
                    continue

                # Filtro de relevância no título antes de clicar
                title_lower = title.lower()
                relevant = any(kw.lower() in title_lower for kw in keywords)
                if not relevant:
                    log.debug(f"  Irrelevante: {title}")
                    continue

                # Verifica Easy Apply clicando no card
                seen_ids.add(job_link)
                driver.execute_script("arguments[0].scrollIntoView({block:'center'})", card)
                human_delay(0.3, 0.5)
                try:
                    card.click()
                except Exception:
                    driver.execute_script("arguments[0].click()", card)

                try:
                    WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, "button.jobs-apply-button, h1")
                        )
                    )
                except TimeoutException:
                    continue
                human_delay(0.3, 0.6)

                # Verifica botão Easy Apply no painel
                easy_apply_btn = None
                for aria in ["Candidatura simplificada", "Easy Apply", "Candidatura fácil"]:
                    try:
                        easy_apply_btn = driver.find_element(
                            By.CSS_SELECTOR,
                            f"button.jobs-apply-button[aria-label*='{aria}']"
                        )
                        break
                    except NoSuchElementException:
                        continue

                if not easy_apply_btn:
                    try:
                        for btn in driver.find_elements(By.CSS_SELECTOR, "button.jobs-apply-button"):
                            txt = (btn.text or "").lower()
                            aria_v = (btn.get_attribute("aria-label") or "").lower()
                            if any(k in txt or k in aria_v for k in ["simplificada", "easy", "fácil"]):
                                easy_apply_btn = btn
                                break
                    except Exception:
                        pass

                if not easy_apply_btn:
                    log.debug(f"  Sem Easy Apply: {title}")
                    continue

                log.info(f"  Confirmado: {title} @ {company}")
                jobs.append({"title": title, "company": company, "url": job_link})

            except Exception as e:
                log.debug(f"  Erro card {i+1}: {e}")
                continue

    except TimeoutException:
        log.warning("Timeout ao carregar vagas.")

    log.info(f"{len(jobs)} vagas com Easy Apply confirmado.")

    if not jobs:
        log.warning(
            "Nenhuma vaga com Easy Apply.\n"
            "  Dica 1: mude date_filter para 'semana' no config.json\n"
            "  Dica 2: tente keywords: ['TypeScript', 'React', 'frontend']\n"
            "  Dica 3: tente location: 'Sao Paulo' ou 'Remote'"
        )

    return jobs
# ── Preencher formulário Easy Apply ──────────────────────────────────────────
def get_label_for_field(driver, field):
    """Tenta obter o label de um campo de diversas formas."""
    field_id = field.get_attribute("id") or ""
    # pelo atributo for
    if field_id:
        labels = driver.find_elements(By.CSS_SELECTOR, f"label[for='{field_id}']")
        if labels:
            return labels[0].text.strip()
    # pelo aria-label do próprio campo
    aria = field.get_attribute("aria-label") or ""
    if aria:
        return aria.strip()
    # pelo label mais próximo no DOM
    try:
        lbl = field.find_element(By.XPATH, "./ancestor::div[1]//label")
        if lbl.text.strip():
            return lbl.text.strip()
    except Exception:
        pass
    try:
        lbl = field.find_element(By.XPATH, "./ancestor::div[2]//label")
        if lbl.text.strip():
            return lbl.text.strip()
    except Exception:
        pass
    return ""


def click_next_or_submit(driver):
    """
    Tenta clicar no botão primário do modal Easy Apply.
    Retorna: 'submit' se clicou em enviar, 'next' se avançou etapa, 'none' se não encontrou.
    """
    # Procura dentro do modal Easy Apply
    modal_sel = ".jobs-easy-apply-modal, .artdeco-modal, [role='dialog']"
    try:
        modal = driver.find_element(By.CSS_SELECTOR, modal_sel)
    except NoSuchElementException:
        modal = driver

    # Todos os botões primários visíveis no modal
    btns = modal.find_elements(By.CSS_SELECTOR, "button.artdeco-button--primary")
    btns_visible = [b for b in btns if b.is_displayed() and b.is_enabled()]

    for btn in btns_visible:
        try:
            txt = (btn.text or "").strip().lower()
            aria = (btn.get_attribute("aria-label") or "").lower()
        except Exception:
            continue
        combined = txt + " " + aria
        log.info(f"  Botão primário: '{txt[:40]}' | aria='{aria[:60]}' ")

        if any(k in combined for k in ["enviar", "submit", "concluir"]):
            try:
                driver.execute_script("arguments[0].scrollIntoView({block:'center'})", btn)
                human_delay(0.3, 0.6)
                driver.execute_script("arguments[0].click()", btn)
                log.info("  Clicou: ENVIAR")
                return "submit"
            except Exception as e:
                log.debug(f"  Erro clicar enviar: {e}")
                continue

        if any(k in combined for k in ["próximo", "avançar", "next", "continuar", "continue", "revisar", "review"]):
            try:
                driver.execute_script("arguments[0].scrollIntoView({block:'center'})", btn)
                human_delay(0.3, 0.6)
                driver.execute_script("arguments[0].click()", btn)
                log.info(f"  Clicou: AVANÇAR ('{txt[:30]}')")
                return "next"
            except Exception as e:
                log.debug(f"  Erro clicar avançar: {e}")
                continue

    # Fallback: clica no último botão primário visível
    for btn in reversed(btns_visible):
        try:
            txt = (btn.text or "").strip()
            driver.execute_script("arguments[0].scrollIntoView({block:'center'})", btn)
            human_delay(0.3, 0.6)
            driver.execute_script("arguments[0].click()", btn)
            log.info(f"  Clicou fallback: '{txt[:30]}'")
            return "next"
        except Exception:
            continue

    return "none"


def fill_easy_apply_form(driver, profile, unknown_action="pause"):
    """
    Navega por todas as etapas do formulário Easy Apply.
    Retorna True se submeteu, False se deve pular.
    """
    max_steps = 25

    last_step_signature = None
    for step in range(max_steps):
        human_delay(1.5, 2.5)
        log.info(f"  -- Etapa {step+1} --")
        # Detecta loop: compara assinatura da página (campos + botões visíveis)
        try:
            sel_ids = tuple(
                s.get_attribute("id") or s.get_attribute("name") or ""
                for s in driver.find_elements(By.CSS_SELECTOR, "select")
                if s.is_displayed()
            )
            inp_ids = tuple(
                f.get_attribute("id") or f.get_attribute("name") or ""
                for f in driver.find_elements(By.CSS_SELECTOR, "input[type='text'],input[type='number'],textarea")
                if f.is_displayed()
            )
            current_sig = sel_ids + inp_ids
        except Exception:
            current_sig = None
        # Só detecta loop se tiver conteúdo real E for igual à etapa anterior
        if current_sig and len(current_sig) > 0 and current_sig == last_step_signature:
            log.warning("  Loop detectado — mesma etapa repetindo. Encerrando formulário.")
            return False
        if current_sig:
            last_step_signature = current_sig

        # Trata checkboxes obrigatórios não marcados (ex: termos de uso)
        try:
            checkboxes = driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox']")
            for cb in checkboxes:
                if not cb.is_displayed() or not cb.is_enabled():
                    continue
                if not cb.is_selected():
                    # Verifica se é obrigatório ou parece termo/concordo
                    cb_id = cb.get_attribute("id") or ""
                    labels = driver.find_elements(By.CSS_SELECTOR, f"label[for='{cb_id}']")
                    lbl_txt = labels[0].text.lower() if labels else ""
                    if any(k in lbl_txt for k in ["concordo", "agree", "termo", "term", "follow", "certif"]):
                        driver.execute_script("arguments[0].click()", cb)
                        log.info(f'    Checkbox marcado: "{lbl_txt[:50]}"')
                        human_delay(0.2, 0.4)
        except Exception as e:
            log.debug(f"    Erro checkbox: {e}")

        # Preenche campos de texto/número/tel/textarea
        fields = driver.find_elements(
            By.CSS_SELECTOR,
            "input[type='text'], input[type='number'], input[type='tel'], "
            "input[type='email'], textarea"
        )
        for field in fields:
            if not field.is_displayed() or not field.is_enabled():
                continue
            try:
                current_val = (field.get_attribute("value") or "").strip()
                if current_val:
                    continue  # já preenchido

                label_text = get_label_for_field(driver, field)
                answer = get_known_answer(label_text, profile)

                if answer:
                    human_type(field, answer)
                    log.info(f'    Campo "{label_text}" → "{answer}"')
                elif label_text:
                    if unknown_action == "skip":
                        log.warning(f'    Campo desconhecido "{label_text}" — pulando vaga.')
                        return False
                    elif unknown_action == "blank":
                        log.warning(f'    Campo desconhecido "{label_text}" — em branco.')
                    else:
                        log.warning(f'    Campo desconhecido: "{label_text}"')
                        answer = input(f'    >> Responda: "{label_text}": ').strip()
                        if answer:
                            human_type(field, answer)
                        else:
                            return False
            except Exception as e:
                log.debug(f"    Erro campo: {e}")

        # Preenche selects
        for sel_el in driver.find_elements(By.CSS_SELECTOR, "select"):
            if not sel_el.is_displayed():
                continue
            try:
                sel = Select(sel_el)
                label_text = get_label_for_field(driver, sel_el)

                # Verifica se já tem valor selecionado (ignora placeholder vazio)
                try:
                    cur_val = sel.first_selected_option.get_attribute("value") or ""
                    cur_txt = sel.first_selected_option.text.strip()
                except Exception:
                    cur_val = ""
                    cur_txt = ""

                # Considera preenchido se o TEXTO da opção selecionada não é placeholder
                placeholder_hints = ["select an option", "selecione", "select", "escolha", "choose", "-- "]
                is_placeholder = (
                    not cur_txt
                    or cur_txt.strip() == ""
                    or any(h in cur_txt.lower() for h in placeholder_hints)
                )
                if not is_placeholder:
                    log.debug(f'    Select "{label_text}" já preenchido: "{cur_txt}"')
                    continue
                log.info(f'    Select não preenchido: "{label_text[:60]}" | atual="{cur_txt}"')

                # Loga todas as opções para debug
                opts_txt = [o.text.strip() for o in sel.options if o.text.strip()]
                log.info(f'    Select "{label_text}" — opções: {opts_txt}')

                answer = get_known_answer(label_text, profile)
                if answer:
                    matched = False
                    for opt in sel.options:
                        if answer.lower() in opt.text.lower():
                            sel.select_by_visible_text(opt.text)
                            driver.execute_script(
                                "arguments[0].dispatchEvent(new Event('change', {bubbles:true}))",
                                sel_el
                            )
                            matched = True
                            log.info(f'    Select "{label_text[:50]}" → "{opt.text.strip()}"')
                            human_delay(0.2, 0.4)
                            break
                    if not matched:
                        placeholder_hints = ["select an option", "selecione", "select", "escolha", "choose", "-- "]
                        for opt in sel.options:
                            opt_txt = opt.text.strip()
                            opt_val = opt.get_attribute("value") or ""
                            if opt_txt and not any(h in opt_txt.lower() for h in placeholder_hints) and opt_val:
                                sel.select_by_visible_text(opt_txt)
                                driver.execute_script(
                                    "arguments[0].dispatchEvent(new Event('change', {bubbles:true}))",
                                    sel_el
                                )
                                log.info(f'    Select fallback: "{opt_txt}" para "{label_text[:50]}"')
                                human_delay(0.2, 0.4)
                                break
                        else:
                            log.warning(f'    Select "{label_text[:50]}": nenhuma opção válida')


                if not answer:
                    if unknown_action == "skip":
                        log.warning(f'    Select desconhecido "{label_text}" — pulando vaga.')
                        return False
                    elif unknown_action == "pause":
                        log.warning(f'    Select desconhecido: "{label_text}" — opções: {opts_txt}')
                        answer = input(f'    >> Escolha para "{label_text}" (copie uma das opções): ').strip()
                        if answer:
                            for opt in sel.options:
                                if answer.lower() in opt.text.lower():
                                    sel.select_by_visible_text(opt.text)
                                    log.info(f'    Select manual: "{opt.text.strip()}"')
                                    break
                        else:
                            return False
                    else:
                        # blank ou qualquer outro: seleciona primeira opção real (não placeholder)
                        placeholder_hints = ["select an option", "selecione", "select", "escolha", "choose", "-- "]
                        for opt in sel.options:
                            opt_txt = opt.text.strip()
                            opt_val = opt.get_attribute("value") or ""
                            if opt_txt and not any(h in opt_txt.lower() for h in placeholder_hints) and opt_val:
                                sel.select_by_visible_text(opt_txt)
                                driver.execute_script(
                                    "arguments[0].dispatchEvent(new Event('change', {bubbles:true}))",
                                    sel_el
                                )
                                log.info(f'    Select primeira opção: "{opt_txt}" para "{label_text[:50]}"')
                                human_delay(0.2, 0.4)
                                break
            except Exception as e:
                log.debug(f"    Erro select: {e}")

        # Clica próximo ou enviar
        result = click_next_or_submit(driver)

        if result == "submit":
            human_delay(1.5, 2.5)
            # Trata modal "Salvar candidatura?" que às vezes aparece após o envio
            try:
                modal_btns = driver.find_elements(By.CSS_SELECTOR, "button.artdeco-button")
                for btn in modal_btns:
                    txt = (btn.text or "").strip().lower()
                    if any(k in txt for k in ["não enviar", "descartar", "discard", "not now"]):
                        driver.execute_script("arguments[0].click()", btn)
                        log.info("  Modal 'Salvar' fechado.")
                        break
            except Exception:
                pass
            return True

        if result == "none":
            log.warning("  Nenhum botão primário encontrado — encerrando etapas.")
            break

        # Se avançou, continua o loop

    log.warning("  Máximo de etapas atingido sem enviar.")
    return False

# ── Candidatura em uma vaga ───────────────────────────────────────────────────
def apply_to_job(driver, job, profile, unknown_action):
    title = job["title"]
    company = job["company"]
    url = job["url"]

    log.info(f"Candidatando: {title} @ {company}")

    # Se o botão já foi encontrado na fase de busca e ainda está visível, usa ele
    # Caso contrário, navega para a URL da vaga
    easy_btn = None
    try:
        # Tenta encontrar o botão no painel lateral atual (sem recarregar)
        for aria in ["Candidatura simplificada", "Easy Apply", "Candidatura fácil"]:
            try:
                btn = driver.find_element(
                    By.CSS_SELECTOR,
                    f"button.jobs-apply-button[aria-label*='{aria}']"
                )
                if btn.is_displayed() and btn.is_enabled():
                    easy_btn = btn
                    break
            except NoSuchElementException:
                continue

        # Fallback pelo texto
        if not easy_btn:
            for btn in driver.find_elements(By.CSS_SELECTOR, "button.jobs-apply-button"):
                txt = (btn.text or "").lower()
                aria_val = (btn.get_attribute("aria-label") or "").lower()
                if any(k in txt or k in aria_val for k in ["simplificada", "easy apply", "fácil"]):
                    if btn.is_displayed():
                        easy_btn = btn
                        break
    except Exception:
        pass

    # Se não encontrou no painel atual, abre a URL
    if not easy_btn:
        log.info(f"  Painel não disponível, abrindo URL...")
        driver.get(url)
        human_delay(3, 5)
        wait = WebDriverWait(driver, 12)
        try:
            easy_btn = wait.until(EC.element_to_be_clickable(
                (By.CSS_SELECTOR,
                 "button.jobs-apply-button[aria-label*='Candidatura simplificada'], "
                 "button.jobs-apply-button[aria-label*='Easy Apply'], "
                 "button.jobs-apply-button")
            ))
        except TimeoutException:
            # Última tentativa: qualquer botão apply visível
            try:
                for btn in driver.find_elements(By.CSS_SELECTOR, "button.jobs-apply-button"):
                    txt = (btn.text or "").lower()
                    aria_val = (btn.get_attribute("aria-label") or "").lower()
                    if any(k in txt or k in aria_val for k in ["simplificada", "easy", "candidat"]):
                        easy_btn = btn
                        break
            except Exception:
                pass

    if not easy_btn:
        log.info(f"  Sem Easy Apply. Pulando: {title}")
        save_result(title, company, url, "sem_easy_apply")
        return False

    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'})", easy_btn)
        human_delay(0.5, 1)
        easy_btn.click()
        human_delay(2, 3)
    except ElementClickInterceptedException:
        driver.execute_script("arguments[0].click();", easy_btn)
        human_delay(2, 3)

    # Preenche formulário
    success = fill_easy_apply_form(driver, profile, unknown_action)

    if not success:
        # Fecha o modal
        try:
            driver.find_element(By.CSS_SELECTOR, "button[aria-label='Fechar'], button[aria-label='Dismiss']").click()
        except Exception:
            pass
        save_result(title, company, url, "pulada", "campo desconhecido ou sem resposta")
        return False

    # fill_easy_apply_form já submeteu — se chegou aqui, candidatura enviada
    log.info(f"  Candidatura enviada: {title} @ {company}")
    save_result(title, company, url, "enviada")
    return True

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    config = load_config()
    profile = config["profile"]
    search = config["search"]
    settings = config["settings"]

    log.info("=" * 60)
    log.info(f"Bot iniciado — {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    log.info(f"Palavras-chave: {search['keywords']}")
    log.info(f"Limite: {settings['max_applications']} candidaturas")
    log.info("=" * 60)

    driver = create_driver(headless=False)

    try:
        if not login(driver, config["email"], config["password"]):
            log.error("Login falhou. Encerrando.")
            return

        date_map = {"24h": "r86400", "semana": "r604800", "mes": "r2592000", "any": ""}
        date_filter = date_map.get(search.get("date_filter", "24h"), "r86400")

        jobs = search_jobs(
            driver,
            search["keywords"],
            search["location"],
            date_filter
        )

        if not jobs:
            log.warning("Nenhuma vaga encontrada. Encerrando.")
            return

        applied = 0
        limit = settings["max_applications"]
        delay_min = settings.get("delay_min", 5)
        delay_max = settings.get("delay_max", 12)
        unknown_action = settings.get("unknown_field_action", "pause")

        for job in jobs:
            if applied >= limit:
                log.info(f"Limite de {limit} candidaturas atingido.")
                break

            result = apply_to_job(driver, job, profile, unknown_action)
            if result:
                applied += 1
                log.info(f"  [{applied}/{limit}] candidaturas enviadas")

            human_delay(delay_min, delay_max)

        log.info(f"Sessão finalizada. Total enviado: {applied}")

    except KeyboardInterrupt:
        log.warning("Interrompido pelo usuário.")
    except Exception as e:
        log.exception(f"Erro inesperado: {e}")
    finally:
        driver.quit()
        log.info("Navegador fechado.")

if __name__ == "__main__":
    main()
