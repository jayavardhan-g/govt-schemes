import csv
import hashlib
import os
import time
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

script_folder = Path(__file__).resolve().parent
seed_csv = script_folder / "seedurls.csv"
OUT_DIR = script_folder / "output" / "raw_html"
OUT_DIR.mkdir(parents=True, exist_ok=True)
NAV_TIMEOUT_MS = 45_000
WAIT_AFTER_NETWORK_IDLE_S = 1.0
MAX_RETRIES = 2
BROWSER_VIEWPORT = {"width": 1280, "height": 900}
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


def url_to_filename(url: str) -> str:
    parsed = urlparse(url)
    domain = parsed.netloc.replace(":", "_")
    path_part = parsed.path.strip("/").replace("/", "_") or "index"
    base = f"{domain}__{path_part}"
    h = hashlib.sha1(url.encode("utf-8")).hexdigest()[:8]

    url_key = "".join(
        c if c.isalnum() or c in ("-", "_", ".") else "_"
        for c in f"{base}__{h}"
    )
    return url_key


def read_seed_urls(csv_path: Path):
    if not csv_path.exists():
        print(f"seedurls.csv not found at: {csv_path}")
        return []

    urls = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if "url" in row and row["url"].strip():
                urls.append(row["url"].strip())
            else:
                first = next(iter(row.values()), "").strip()
                if first:
                    urls.append(first)
    return urls


def scroll_page_slowly(page):
    page.evaluate(
        """() => {
            return new Promise(resolve => {
              const total = document.body.scrollHeight;
              let pos = 0;
              const step = Math.max(Math.floor(total / 8), 200);
              const t = setInterval(() => {
                pos = Math.min(pos + step, total);
                window.scrollTo(0, pos);
                if (pos >= total) {
                  clearInterval(t);
                  setTimeout(resolve, 300);
                }
              }, 150);
            });
        }"""
    )


def fetch_single_page(page, url: str, out_path: Path) -> bool:
    try:
        page.set_viewport_size(BROWSER_VIEWPORT)
        page.set_extra_http_headers({"User-Agent": USER_AGENT})
        page.goto(url, wait_until="networkidle", timeout=NAV_TIMEOUT_MS)

        time.sleep(WAIT_AFTER_NETWORK_IDLE_S)
        try:
            scroll_page_slowly(page)
        except Exception:
            pass

        time.sleep(0.2)

        html = page.content()
        out_path.write_text(html, encoding="utf-8")
        return True

    except PlaywrightTimeoutError as te:
        print(f"[timeout] {url} -> {te}")
        return False

    except Exception as e:
        print(f"[error] {url} -> {e}")
        return False


def main():
    urls = read_seed_urls(seed_csv)
    if not urls:
        print("No URLs found in seedurls.csv")
        return

    print(f"[INFO] Starting fetch of {len(urls)} URLs...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            java_script_enabled=True,
            user_agent=USER_AGENT
        )

        try:
            for idx, url in enumerate(urls, start=1):
                print(f"[{idx}/{len(urls)}] Fetching: {url}")
                url_key = url_to_filename(url)
                out_file = OUT_DIR / f"{url_key}.html"

                success = False
                attempt = 0
                while attempt <= MAX_RETRIES and not success:
                    attempt += 1
                    page = context.new_page()

                    try:
                        success = fetch_single_page(page, url, out_file)
                        if success:
                            print(f"  -> saved: {out_file}")
                        else:
                            print(f"  -> attempt {attempt} failed")
                            # Exponential backoff before retry
                            time.sleep(1.5 ** attempt)

                    finally:
                        try:
                            page.close()
                        except Exception:
                            pass

                if not success:
                    print(f"  -> FAILED after {MAX_RETRIES + 1} attempts: {url}")

        finally:
            context.close()
            browser.close()

    print("Fetching complete!")


if __name__ == "__main__":
    main()
