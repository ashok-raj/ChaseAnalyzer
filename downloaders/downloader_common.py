"""
Shared Selenium driver setup and file-management helpers for the statement
downloaders (chase_business, chase_personal, bofa).

Mirrors the approach used in ../../KeyBank/keybank_statement_downloader.py:
- Fresh temp Chrome profile per run (no leftover cookies/history)
- Anti-automation-fingerprint tweaks (bot detection on bank sites is real)
- Silent downloads: no Save-As dialog, files land straight in a temp dir
- Caller moves/renames the downloaded file into the correct dated folder
  and skips the download entirely if the target file already exists
"""

import logging
import platform
import shutil
import sys
import tempfile
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.service import Service

try:
    import chromedriver_autoinstaller
except ImportError:
    chromedriver_autoinstaller = None


def setup_driver(temp_download_dir: Path, headless: bool = False, profile_dir: Path = None):
    """Launch a Chrome instance with silent downloads into temp_download_dir.

    If profile_dir is given, that persistent profile is reused across runs so
    the bank's site remembers this as a known device (skipping repeat MFA
    challenges) instead of treating every run as a brand-new device. Falls
    back to a throwaway temp profile if not given.
    """
    options = webdriver.ChromeOptions()
    options.add_argument('--start-maximized')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-software-rasterizer')
    if headless:
        options.add_argument('--headless=new')

    if profile_dir:
        profile_dir.mkdir(parents=True, exist_ok=True)
        options.add_argument(f'--user-data-dir={profile_dir}')
        logging.info(f"Using persistent Chrome profile at {profile_dir}")
    else:
        temp_profile_dir = tempfile.mkdtemp(prefix="bank-chrome-profile-")
        options.add_argument(f'--user-data-dir={temp_profile_dir}')
        logging.info(f"Using fresh Chrome profile at {temp_profile_dir}")

    # Strip obvious Selenium fingerprints to avoid bot-detection blocks
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    prefs = {
        "download.default_directory": str(temp_download_dir),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": True,
        "safebrowsing.enabled": True,
        "savefile.default_directory": str(temp_download_dir),
    }
    options.add_experimental_option("prefs", prefs)

    try:
        if chromedriver_autoinstaller:
            # Prefer this over a system/Homebrew chromedriver: it always
            # matches the installed Chrome version and isn't subject to
            # Homebrew cask deprecation/Gatekeeper issues.
            driver_path = chromedriver_autoinstaller.install()
            service = Service(driver_path)
            driver = webdriver.Chrome(service=service, options=options)
        else:
            system_chromedriver = shutil.which("chromedriver")
            if not system_chromedriver:
                raise RuntimeError("No chromedriver found on PATH and chromedriver_autoinstaller not installed")
            service = Service(system_chromedriver)
            driver = webdriver.Chrome(service=service, options=options)

        logging.info(f"Chrome driver initialized (OS: {platform.system()})")

        try:
            driver.execute_cdp_cmd(
                "Page.addScriptToEvaluateOnNewDocument",
                {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"},
            )
        except Exception as cdp_err:
            logging.warning(f"navigator.webdriver patch failed (non-fatal): {cdp_err}")

        return driver
    except Exception as e:
        logging.error(f"Failed to initialize Chrome driver: {e}")
        sys.exit(1)


def wait_for_download(temp_dir: Path, before_files: set, timeout: int = 60) -> Path:
    """Poll temp_dir until a new, fully-written (non .crdownload) file appears."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        current = set(temp_dir.iterdir())
        new_files = current - before_files
        finished = [f for f in new_files if not f.name.endswith('.crdownload')]
        if finished:
            # Make sure it's stable (not still being written)
            f = finished[0]
            size1 = f.stat().st_size
            time.sleep(0.5)
            if f.exists() and f.stat().st_size == size1 and size1 > 0:
                return f
        time.sleep(0.5)
    raise TimeoutError(f"No completed download appeared in {temp_dir} within {timeout}s")


def move_into_place(src: Path, dest: Path, overwrite: bool = False):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and not overwrite:
        logging.info(f"Target already exists, skipping move: {dest}")
        src.unlink(missing_ok=True)
        return False
    shutil.move(str(src), str(dest))
    logging.info(f"Saved: {dest}")
    return True
