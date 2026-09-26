#!/usr/bin/env python3
"""
Chase statement downloader (Business and Personal cards share the same
chase.com login/UI, just different account suffixes).

Usage:
    python3 chase_statement_downloader.py business [--year 2026] [--all-years]
    python3 chase_statement_downloader.py personal [--year 2026] [--all-years]

Credentials come from bank_credentials.py (Keychain first, .env fallback,
interactive prompt as last resort).

Downloads land silently (no Save-As dialog) into a temp dir via Chrome
download prefs, then get moved into place as:
    ChaseAnalyzer/<year>/<suffix>/<YYYYMMDD>-statements-<suffix>-.pdf
skipping any statement whose target file already exists.
"""

import argparse
import logging
import re
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    ElementNotInteractableException,
    StaleElementReferenceException,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bank_credentials import get_or_prompt_credentials
from downloader_common import setup_driver, wait_for_download, move_into_place

OTP_HANDOFF_DIR = Path(__file__).resolve().parent / ".otp_handoff"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('chase_statement_download.log'), logging.StreamHandler()],
)

REPO_ROOT = Path(__file__).resolve().parent.parent

ACCOUNTS = {
    "business": {"bank_key": "chase_business", "suffix": "0801"},
    "personal": {"bank_key": "chase_personal", "suffix": "5136"},
}

SELECTORS = {
    "username_field": (By.ID, "userId-text-input-field"),
    "password_field": (By.ID, "password-text-input-field"),
    "signin_button": (By.ID, "signin-button"),
    "year_dropdown": (By.ID, "filterstyledselect-0"),
    "year_list": (By.ID, "ul-list-container-filterstyledselect-0"),
}


def wait_for_otp_code(driver, bank_key: str, timeout: int = 240) -> str:
    """Poll for a code dropped by the operator into the handoff file, then consume it.
    Bails out early (returning "") if the browser has already moved off the
    OTP page -- e.g. the human typed the code and clicked Next manually."""
    OTP_HANDOFF_DIR.mkdir(exist_ok=True)
    handoff_file = OTP_HANDOFF_DIR / f"{bank_key}.txt"
    handoff_file.unlink(missing_ok=True)
    logging.info(f"Waiting for OTP code to be written to {handoff_file} "
                 f"(or enter it directly in the browser window)...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        if handoff_file.exists():
            code = handoff_file.read_text().strip()
            if code:
                handoff_file.unlink(missing_ok=True)
                return code
        if "caas=verifyOTP" not in driver.current_url:
            return ""  # human already handled it in the browser
        time.sleep(2)
    return ""


def dump_mfa_dom(driver, label: str):
    """One-time diagnostic: log every interactive-ish element on an MFA page,
    piercing open shadow roots recursively, so we can find real selectors
    instead of guessing (Chase's MFA flow is built from custom mds-* web
    components with closed-looking but open shadow roots)."""
    js = """
    function walk(root, path, out) {
        // Cast a wide net: Chase's list items are custom elements (e.g.
        // <mds-list-item>) that carry no role/tag hint, so filter by
        // "has its own visible text" instead of a fixed tag/role allowlist.
        root.querySelectorAll('*').forEach(el => {
            const text = (el.innerText || el.value || '').trim();
            const isLeafText = text && text.length < 120 &&
                (!el.children.length || [...el.children].every(c => !(c.innerText || '').trim()));
            if (isLeafText || ['INPUT','BUTTON','LI','A','SELECT'].includes(el.tagName)) {
                out.push({
                    path: path,
                    tag: el.tagName,
                    id: el.id,
                    name: el.name || '',
                    type: el.type || '',
                    role: el.getAttribute('role') || '',
                    cls: (el.className || '').toString().slice(0, 60),
                    text: text.slice(0, 100).replace(/\\n/g, ' | '),
                    visible: !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)
                });
            }
            if (el.shadowRoot) walk(el.shadowRoot, path + '>' + el.tagName + '#shadow', out);
        });
    }
    const out = [];
    walk(document, 'document', out);
    return out;
    """
    try:
        elements = driver.execute_script(js)
        logging.info(f"MFA DOM dump [{label}] ({len(elements)} elements):")
        for el in elements:
            logging.info(f"  {el}")
    except Exception as e:
        logging.warning(f"DOM dump failed: {e}")


def submit_otp_code(driver, code: str) -> bool:
    """Fill and submit Chase's OTP field. Verified via a live DOM dump: the
    field is input#otpInput-input inside a <mds-text-input-secure> shadow
    root, and the visible primary "Next" button lives inside an <mds-button>
    shadow root -- both invisible to plain (non-shadow-piercing) selectors."""
    js = """
    const code = arguments[0];
    function findInShadow(matchFn) {
        function walk(root) {
            for (const el of root.querySelectorAll('*')) {
                if (matchFn(el)) return el;
                if (el.shadowRoot) {
                    const found = walk(el.shadowRoot);
                    if (found) return found;
                }
            }
            return null;
        }
        return walk(document);
    }
    const input = findInShadow(el => el.id === 'otpInput-input');
    if (!input) return 'no-input';
    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
    setter.call(input, code);
    input.dispatchEvent(new Event('input', {bubbles: true}));
    input.dispatchEvent(new Event('change', {bubbles: true}));

    const nextBtn = findInShadow(el =>
        el.tagName === 'BUTTON' &&
        el.className.includes('button--primary') &&
        el.innerText.trim().startsWith('Next') &&
        (el.offsetWidth || el.offsetHeight)
    );
    if (!nextBtn) return 'no-button';
    nextBtn.click();
    return 'ok';
    """
    result = driver.execute_script(js, code)
    return result == "ok"


def find_all_shadow_hosts(driver):
    """Return every element in the document (and recursively, inside every
    open shadow root) as real Selenium WebElements, so callers can pierce
    Chase's mds-* shadow DOM without JS-synthesized (untrusted) clicks."""
    js = """
    function walk(root, out) {
        root.querySelectorAll('*').forEach(el => {
            out.push(el);
            if (el.shadowRoot) walk(el.shadowRoot, out);
        });
    }
    const out = [];
    walk(document, out);
    return out;
    """
    return driver.execute_script(js)


def select_text_option(driver) -> bool:
    """Click "Get a text" on Chase's MFA method-picker page. Verified via a
    live DOM dump: it's a <label>Get a text</label> inside an <mds-list>
    shadow root, with the containing <li> as the real click target.

    A JS-synthesized element.click() finds the right element but does NOT
    register the selection -- Chase's mds-list component almost certainly
    checks event.isTrusted, which is false for script-dispatched clicks. So
    this clicks via a real Selenium ActionChains click (a trusted OS-level
    event) on the WebElement instead."""
    for el in find_all_shadow_hosts(driver):
        if el.tag_name == "li" and "Get a text" in el.text:
            ActionChains(driver).move_to_element(el).pause(0.2).click(el).perform()
            return True
    return False


def select_phone_and_continue(driver, suffix: str) -> bool:
    """Pick the phone number ending in `suffix` on Chase's SMS page and click
    Next, via real (trusted) clicks -- see select_text_option for why JS
    clicks don't work on these components. Verified via a live DOM dump: the
    picker is <mds-select id="eligibleTextContacts">, its visible trigger is
    a <button id="select-eligibleTextContacts"> inside its shadow root, and
    the actual choices are light-DOM <mds-select-option> elements. "Next" is
    a primary <button> inside an <mds-button> shadow root."""
    elements = find_all_shadow_hosts(driver)

    trigger = next((el for el in elements if el.get_attribute("id") == "select-eligibleTextContacts"), None)
    if trigger is None:
        return False

    if suffix not in trigger.text:
        ActionChains(driver).move_to_element(trigger).pause(0.2).click(trigger).perform()
        time.sleep(0.5)
        options = driver.find_elements(By.TAG_NAME, "mds-select-option")
        option = next((o for o in options if suffix in o.text), None)
        if option is None:
            return False
        ActionChains(driver).move_to_element(option).pause(0.2).click(option).perform()
        time.sleep(0.5)
        elements = find_all_shadow_hosts(driver)  # DOM may have re-rendered after selection

    next_btn = next(
        (el for el in elements
         if el.tag_name == "button"
         and "button--primary" in (el.get_attribute("class") or "")
         and el.text.strip().startswith("Next")),
        None,
    )
    if next_btn is None:
        return False
    ActionChains(driver).move_to_element(next_btn).pause(0.2).click(next_btn).perform()
    return True


def try_automate_mfa(driver, bank_key: str, phone_suffix: str = "8963"):
    """Best-effort automation of Chase's SMS MFA challenge: picks "Get a
    text", then the phone number ending in `phone_suffix`, then submits the
    OTP code via the handoff file. Falls back to leaving the browser as-is
    (for a human to finish by hand) if any automated step doesn't find what
    it expects -- Chase's MFA markup has changed shape before.
    Returns True if it drove the flow forward, False otherwise."""
    url = driver.current_url

    if "step=confirmIdentity" in url and "caas=options" in url:
        time.sleep(2)  # let Chase finish lazily rendering the list items
        if select_text_option(driver):
            logging.info("Auto-selected 'Get a text' MFA option.")
            return True
        logging.warning("Could not auto-select 'Get a text'; dumping DOM and falling back to manual click.")
        dump_mfa_dom(driver, "options")
        return False

    if "step=confirmIdentity" in url and "caas=sms" in url:
        time.sleep(2)
        if select_phone_and_continue(driver, phone_suffix):
            logging.info(f"Auto-selected phone ending in {phone_suffix} and clicked Next.")
            return True
        logging.warning(f"Could not auto-select phone ending in {phone_suffix}; dumping DOM and falling back to manual click.")
        dump_mfa_dom(driver, "sms")
        return False

    if "step=confirmIdentity" in url and "caas=verifyOTP" in url:
        code = wait_for_otp_code(driver, bank_key)
        if not code:
            return False  # timed out or human already handled it; let poll path continue
        if submit_otp_code(driver, code):
            logging.info("Submitted OTP code.")
        else:
            logging.warning("Could not auto-submit OTP code; complete it manually in the browser.")
        return True

    return False


def login(driver, wait, username, password, bank_key: str):
    logging.info("Navigating to chase.com...")
    driver.get("https://www.chase.com")
    time.sleep(2)

    username_field = wait.until(EC.presence_of_element_located(SELECTORS["username_field"]))
    username_field.clear()
    username_field.send_keys(username)

    password_field = driver.find_element(*SELECTORS["password_field"])
    password_field.clear()
    password_field.send_keys(password)

    driver.find_element(*SELECTORS["signin_button"]).click()
    logging.info("Submitted login, waiting for dashboard or MFA challenge...")
    time.sleep(3)

    # Detect an MFA / identity-verification interstitial: URL won't be the
    # dashboard yet. Try to drive it automatically (select text option, pick
    # phone, submit OTP from the handoff file); fall back to polling so a
    # human can also just click through the real, visible browser window.
    deadline = time.time() + 600
    last_handled_url = None
    while "dashboard" not in driver.current_url:
        if time.time() > deadline:
            raise RuntimeError(
                "Did not reach the dashboard within 600s of login/MFA. "
                "Complete any pending verification in the browser window and rerun."
            )
        current_url = driver.current_url
        if current_url != last_handled_url:
            logging.info(f"Waiting for verification/dashboard... current URL: {current_url}")
            try_automate_mfa(driver, bank_key)
            last_handled_url = current_url
        time.sleep(3)

    logging.info("Logged in.")


def open_account_statements(driver, wait, suffix):
    """From the dashboard, click into the card ending in `suffix` and open Statements."""
    driver.get("https://secure.chase.com/web/auth/dashboard#/dashboard/overview")
    time.sleep(3)
    logging.info(f"On overview page: {driver.current_url}")

    card_link = wait.until(EC.presence_of_element_located(
        (By.XPATH, f"//*[contains(text(), '(...{suffix})')]")
    ))
    card_link.click()
    time.sleep(3)
    logging.info(f"Clicked card ...{suffix}, now at: {driver.current_url}")

    statements_btn = wait.until(EC.element_to_be_clickable(
        (By.XPATH, "//button[contains(., 'Statements')] | //a[contains(., 'Statements')]")
    ))
    statements_btn.click()
    time.sleep(3)
    logging.info(f"Clicked Statements, now at: {driver.current_url}")


def _dropdown_label(driver, el) -> str:
    """This "styled select" widget renders its current value inside a
    readonly <input>, whose value attribute .text (innerText-based) can't
    see -- read it directly via JS instead."""
    return driver.execute_script(
        "return (arguments[0].innerText || arguments[0].value || arguments[0].textContent || '').trim();",
        el,
    )


def click_when_ready(wait, get_element, retries: int = 5, delay: float = 1.5):
    """Click an element, retrying past the brief window where the
    Statements/Documents panel is still mid-load: `element_to_be_clickable`
    only checks visibility/enabled, not whether a loading overlay is still
    covering the element, so Selenium can still throw
    ElementNotInteractableException right after the wait succeeds."""
    for attempt in range(retries):
        try:
            get_element().click()
            return
        except (ElementNotInteractableException, StaleElementReferenceException):
            if attempt == retries - 1:
                raise
            time.sleep(delay)


def select_year(driver, wait, year: str):
    dropdown = wait.until(EC.element_to_be_clickable(SELECTORS["year_dropdown"]))
    wait.until(lambda d: _dropdown_label(driver, dropdown) != "")
    if year in _dropdown_label(driver, dropdown):
        return
    click_when_ready(wait, lambda: wait.until(EC.element_to_be_clickable(SELECTORS["year_dropdown"])))
    year_list = wait.until(EC.presence_of_element_located(SELECTORS["year_list"]))
    click_when_ready(wait, lambda: year_list.find_element(
        By.XPATH, f".//li[normalize-space(.)='{year}']"
    ))
    time.sleep(2)


def get_statement_rows(driver):
    """Return list of (date_text, download_element_id) for the current year's table."""
    table = driver.find_element(By.CSS_SELECTOR, "table.table-body")
    rows = table.find_elements(By.TAG_NAME, "tr")
    out = []
    for row in rows:
        links = row.find_elements(By.CSS_SELECTOR, "a.iconwrap-link")
        if not links:
            continue
        date_text = row.find_elements(By.TAG_NAME, "td")[0].text
        download_link = next((a for a in links if a.get_attribute("id") and a.get_attribute("id").endswith("-download")), None)
        if download_link is not None:
            out.append((date_text, download_link.get_attribute("id")))
    return out


def parse_statement_date(date_text: str) -> str:
    """'Aug 06, 2026' -> '20260806'"""
    dt = datetime.strptime(date_text.strip(), "%b %d, %Y")
    return dt.strftime("%Y%m%d")


def download_statements(driver, wait, suffix, temp_dir: Path):
    rows = get_statement_rows(driver)
    logging.info(f"Found {len(rows)} statements for this year.")

    downloaded, skipped = 0, 0
    for date_text, link_id in rows:
        yyyymmdd = parse_statement_date(date_text)
        year = yyyymmdd[:4]
        target = REPO_ROOT / year / suffix / f"{yyyymmdd}-statements-{suffix}-.pdf"

        if target.exists():
            logging.info(f"Already have {target.name}, skipping.")
            skipped += 1
            continue

        before = set(temp_dir.iterdir())
        link = driver.find_element(By.ID, link_id)
        link.click()
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
    parser = argparse.ArgumentParser(description="Download Chase statements")
    parser.add_argument("account", choices=list(ACCOUNTS))
    parser.add_argument("--year", default=str(datetime.now().year), help="Statement year to fetch (default: current year)")
    parser.add_argument("--all-years", action="store_true", help="Fetch all available years instead of just --year")
    parser.add_argument("--fresh-profile", action="store_true",
                         help="Use a throwaway Chrome profile instead of the persistent, "
                              "trusted one -- forces a fresh MFA challenge. For testing only.")
    args = parser.parse_args()

    account = ACCOUNTS[args.account]
    username, password = get_or_prompt_credentials(account["bank_key"])

    temp_dir = Path(tempfile.mkdtemp(prefix=f"chase-{args.account}-downloads-"))
    profile_dir = None if args.fresh_profile else (
        Path(__file__).resolve().parent / ".chrome_profiles" / account["bank_key"]
    )
    driver = setup_driver(temp_dir, profile_dir=profile_dir)
    wait = WebDriverWait(driver, 30)

    try:
        login(driver, wait, username, password, account["bank_key"])
        open_account_statements(driver, wait, account["suffix"])

        if args.all_years:
            dropdown = wait.until(EC.element_to_be_clickable(SELECTORS["year_dropdown"]))
            dropdown.click()
            time.sleep(1)
            year_list = driver.find_element(*SELECTORS["year_list"])
            years = [li.text.strip() for li in year_list.find_elements(By.TAG_NAME, "li") if li.text.strip()]
            dropdown.click()  # close dropdown
            time.sleep(1)
            for year in years:
                logging.info(f"=== Year {year} ===")
                select_year(driver, wait, year)
                download_statements(driver, wait, account["suffix"], temp_dir)
        else:
            select_year(driver, wait, args.year)
            download_statements(driver, wait, account["suffix"], temp_dir)

    except Exception:
        try:
            shot_path = Path(__file__).resolve().parent / f"failure-{args.account}.png"
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
