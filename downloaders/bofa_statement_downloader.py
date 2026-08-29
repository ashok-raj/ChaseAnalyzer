#!/usr/bin/env python3
"""
Bank of America statement downloader for the Atmos Rewards Ascent Visa
Signature card (...1250).

Usage:
    python3 bofa_statement_downloader.py [--year 2026] [--all-years] [--fresh-profile]

Credentials come from bank_credentials.py (Keychain first, .env fallback,
interactive prompt as last resort).

Downloads land silently (no Save-As dialog) into a temp dir via Chrome
download prefs, then get moved into place as:
    ChaseAnalyzer/<year>/1250/eStmt_<YYYY-MM-DD>.pdf
skipping any statement whose target file already exists.

Selectors here were captured from a live DOM inspection (BofA doesn't use
shadow DOM or heavy obfuscation like Chase -- plain ids/classes throughout).
"""

import argparse
import logging
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bank_credentials import get_or_prompt_credentials
from downloader_common import setup_driver, wait_for_download, move_into_place

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('bofa_statement_download.log'), logging.StreamHandler()],
)

REPO_ROOT = Path(__file__).resolve().parent.parent
BANK_KEY = "bofa"
CARD_SUFFIX = "1250"

SELECTORS = {
    "username_field": (By.ID, "oid"),
    "password_field": (By.ID, "pass"),
    "signin_button": (By.ID, "secure-signin-submit"),
    "year_dropdown": (By.ID, "yearDropDown"),
}


def login(driver, wait, username, password):
    logging.info("Navigating to bankofamerica.com...")
    driver.get("https://www.bankofamerica.com")
    time.sleep(2)

    username_field = wait.until(EC.presence_of_element_located(SELECTORS["username_field"]))
    username_field.clear()
    username_field.send_keys(username)

    password_field = driver.find_element(*SELECTORS["password_field"])
    password_field.clear()
    password_field.send_keys(password)

    driver.find_element(*SELECTORS["signin_button"]).click()
    logging.info("Submitted login, waiting for dashboard or a security challenge...")

    # BofA doesn't always challenge; when it does the flow/selectors are
    # unknown, so just poll for a known post-login element (real, visible
    # browser window -- a human can clear any challenge directly in it).
    deadline = time.time() + 300
    while True:
        if time.time() > deadline:
            raise RuntimeError(
                "Did not reach the account dashboard within 300s of login. "
                "Complete any pending verification in the browser window and rerun."
            )
        try:
            driver.find_element(By.LINK_TEXT, "Log Out")
            break
        except NoSuchElementException:
            time.sleep(3)

    logging.info("Logged in.")


def find_visible(wait, xpath):
    """BofA's markup often duplicates an element (one hidden mobile/alt copy,
    one visible) sharing the same text -- a plain By.XPATH lookup returns
    whichever comes first in document order, which is frequently the hidden
    one. Poll until one of the matches is actually visible."""
    def _find(driver):
        for el in driver.find_elements(By.XPATH, xpath):
            if el.is_displayed():
                return el
        return False
    return wait.until(_find)


def dismiss_interstitial_modals(driver, attempts: int = 3):
    """BofA shows various promo/informational modals unpredictably ('review
    your profile', 'You asked. We listened.', etc.) that block the page.
    Best-effort: repeatedly look for and click any visible close/dismiss
    control."""
    xpath = (
        "//button[@aria-label='Close' or contains(@class,'close') or normalize-space(text())='Got it'] "
        "| //a[contains(@class,'close') or normalize-space(text())='Close']"
    )
    for _ in range(attempts):
        closed_any = False
        # A click can mutate/replace the DOM, invalidating the rest of the
        # list -- handle one element at a time and re-query afterwards
        # rather than iterating a stale snapshot.
        try:
            for el in driver.find_elements(By.XPATH, xpath):
                if el.is_displayed():
                    el.click()
                    closed_any = True
                    time.sleep(1)
                    break
        except StaleElementReferenceException:
            closed_any = True  # DOM changed mid-check; assume something closed, loop again
        if not closed_any:
            break


def open_statements(driver, wait):
    """From the dashboard, click into the ...1250 card and open Statements & Documents."""
    dismiss_interstitial_modals(driver)

    card_link = wait.until(EC.presence_of_element_located((
        By.XPATH,
        f"//a[contains(text(), '- {CARD_SUFFIX}') and not(contains(@class,'quick-view')) "
        f"and not(contains(@class,'alert')) and not(contains(@class,'inline-offer'))]"
    )))
    card_link.click()
    time.sleep(2)
    logging.info(f"Clicked card ...{CARD_SUFFIX}, now at: {driver.current_url}")

    docs_tab = find_visible(wait, "//a[contains(text(), 'Statements & Documents')]")
    docs_tab.click()
    time.sleep(2)
    logging.info(f"Clicked Statements & Documents, now at: {driver.current_url}")

    # Expand the "Statements" accordion under "View All" to see the full list
    # (not just the single "Most Recent" card).
    statements_toggle = find_visible(wait, "//*[normalize-space(text())='Statements']")
    statements_toggle.click()
    time.sleep(2)


def select_year(driver, wait, year: str):
    dropdown_el = wait.until(EC.presence_of_element_located(SELECTORS["year_dropdown"]))
    select = Select(dropdown_el)
    if select.first_selected_option.text.strip() == year:
        return
    select.select_by_visible_text(year)
    time.sleep(2)


def get_statement_cards(driver):
    """Return list of (date_text, card_element) for the expanded statements list."""
    cards = driver.find_elements(By.CSS_SELECTOR, "div.card.squeezebox-panel.DISPFLD001")
    out = []
    for card in cards:
        text = card.text
        import re
        m = re.search(r"[A-Za-z]{3,9} \d{1,2}, \d{4}", text)
        if m:
            out.append((m.group(0), card))
    return out


def parse_statement_date(date_text: str) -> str:
    """'Aug 24, 2026' -> '2026-08-24'"""
    dt = datetime.strptime(date_text.strip(), "%b %d, %Y")
    return dt.strftime("%Y-%m-%d")


def download_statements(driver, temp_dir: Path):
    cards = get_statement_cards(driver)
    logging.info(f"Found {len(cards)} statements for this year.")

    downloaded, skipped = 0, 0
    for date_text, card in cards:
        iso_date = parse_statement_date(date_text)
        year = iso_date[:4]
        target = REPO_ROOT / year / CARD_SUFFIX / f"eStmt_{iso_date}.pdf"

        if target.exists():
            logging.info(f"Already have {target.name}, skipping.")
            skipped += 1
            continue

        try:
            download_link = card.find_element(By.CSS_SELECTOR, "a#downloadPDFLink, a.download-pdf-link")
        except NoSuchElementException:
            logging.warning(f"No download link found for statement dated {date_text}, skipping.")
            continue

        before = set(temp_dir.iterdir())
        # The card is a flip-card UI -- the download link sits behind a
        # ".front" face div until hovered/flipped, so a real click lands on
        # that overlay instead. A JS click bypasses the visual hit-test.
        driver.execute_script("arguments[0].click();", download_link)
        try:
            new_file = wait_for_download(temp_dir, before, timeout=60)
        except TimeoutError as e:
            logging.error(f"Download failed for {date_text}: {e}")
            continue

        if move_into_place(new_file, target):
            downloaded += 1
        time.sleep(1)

    logging.info(f"Done. Downloaded {downloaded}, skipped {skipped} (already present).")


def main():
    parser = argparse.ArgumentParser(description="Download Bank of America statements")
    parser.add_argument("--year", default=str(datetime.now().year), help="Statement year to fetch (default: current year)")
    parser.add_argument("--all-years", action="store_true", help="Fetch all available years instead of just --year")
    parser.add_argument("--fresh-profile", action="store_true",
                         help="Use a throwaway Chrome profile instead of the persistent, "
                              "trusted one. For testing only.")
    args = parser.parse_args()

    username, password = get_or_prompt_credentials(BANK_KEY)

    temp_dir = Path(tempfile.mkdtemp(prefix="bofa-downloads-"))
    profile_dir = None if args.fresh_profile else (
        Path(__file__).resolve().parent / ".chrome_profiles" / BANK_KEY
    )
    driver = setup_driver(temp_dir, profile_dir=profile_dir)
    wait = WebDriverWait(driver, 30)

    try:
        login(driver, wait, username, password)
        open_statements(driver, wait)

        if args.all_years:
            dropdown_el = wait.until(EC.presence_of_element_located(SELECTORS["year_dropdown"]))
            years = [o.text.strip() for o in Select(dropdown_el).options]
            for year in years:
                logging.info(f"=== Year {year} ===")
                select_year(driver, wait, year)
                download_statements(driver, temp_dir)
        else:
            select_year(driver, wait, args.year)
            download_statements(driver, temp_dir)

    except Exception:
        try:
            shot_path = Path(__file__).resolve().parent / "failure-bofa.png"
            driver.save_screenshot(str(shot_path))
            logging.error(f"Failed at URL {driver.current_url}; screenshot saved to {shot_path}")
        except Exception as shot_err:
            logging.error(f"Also failed to save failure screenshot: {shot_err}")
        raise
    finally:
        logging.info("Done. Closing browser.")
        driver.quit()


if __name__ == "__main__":
    main()
