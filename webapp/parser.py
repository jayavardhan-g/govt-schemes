#!/usr/bin/env python3
"""
HTML parsing module for government scheme websites.

Scans output/raw_html/ for .html files and extracts:
- Scheme title
- Eligibility criteria/description
- Geographic state (if detectable)

Uses BeautifulSoup with heuristics to identify eligibility sections.
Outputs parsed data as Python module for database seeding.
"""

import os
import csv
import re
import hashlib
from urllib.parse import urlparse
from bs4 import BeautifulSoup

# ===== CONFIGURATION =====

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_HTML_DIR = os.path.join(SCRIPT_DIR, "output", "raw_html")
SEED_CSV = os.path.join(SCRIPT_DIR, "seedurls.csv")
OUTPUT_PY = os.path.join(SCRIPT_DIR, "output", "sample_schemes.py")

# Keywords to identify eligibility sections in HTML
HEADING_KEYWORDS = [
    "eligibility", "eligibility criteria", "who can apply", "who is eligible",
    "conditions for eligibility", "eligible", "applicants"
]

# Fallback keywords for when structured headings aren't found
FALLBACK_KEYWORDS = [
    "eligible", "not eligible", "income", "annual income", "age", "years", "resident",
    "citizen", "widow", "women", "household", "beneficiary", "ownership", "landholding", "student"
]

# List of Indian states for geographic detection
STATES = [
    "Andhra Pradesh","Arunachal Pradesh","Assam","Bihar","Chhattisgarh",
    "Goa","Gujarat","Haryana","Himachal Pradesh","Jharkhand","Karnataka",
    "Kerala","Madhya Pradesh","Maharashtra","Manipur","Meghalaya","Mizoram",
    "Nagaland","Odisha","Punjab","Rajasthan","Sikkim","Tamil Nadu",
    "Telangana","Tripura","Uttar Pradesh","Uttarakhand","West Bengal",
    "Delhi","Jammu and Kashmir","Ladakh"
]


def url_to_filename(url: str) -> str:
    """Convert URL to filesystem-safe key (matching fetcher.py output)."""
    parsed = urlparse(url)
    domain = parsed.netloc.replace(":", "_")
    path_part = parsed.path.strip("/").replace("/", "_") or "index"
    base = f"{domain}__{path_part}"
    h = hashlib.sha1(url.encode("utf-8")).hexdigest()[:8]
    url_key = "".join(c if c.isalnum() or c in ("-", "_", ".") else "_" for c in f"{base}__{h}")
    return url_key


def load_seed_map(csv_path=SEED_CSV):
    """
    Load URL mapping from seedurls.csv for linking HTML files back to original URLs.
    Returns dict mapping filename -> URL.
    """
    mapping = {}
    if not os.path.exists(csv_path):
        print(f"Warning: Seed file not found at {csv_path}")
        return mapping
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Accept 'url' header or first column fallback
            url = ""
            if "url" in row and row["url"].strip():
                url = row["url"].strip()
            else:
                first = next(iter(row.values()), "").strip()
                if first:
                    url = first
            if url:
                key = url_to_filename(url)
                mapping[key] = url
    return mapping


def read_html(path):
    """Read HTML file safely, returning None if failed."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return None


def clean_text(s):
    """Normalize text: fix line endings, remove special bullets, collapse whitespace."""
    if not s:
        return ""
    # Normalize line endings
    s = re.sub(r"\r\n?", "\n", s)
    # Replace bullet characters with dashes
    s = re.sub(r"\u2022|\u2023|\u25E6|\u2043|\u2219", "-", s)
    # Collapse multiple blank lines
    s = re.sub(r"\n\s*\n+", "\n", s)
    # Collapse multiple spaces
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()


def extract_title(soup, fallback):
    """Extract page title from <title>, <h1>, or use fallback."""
    tag = soup.find("title")
    if tag and tag.get_text(strip=True):
        return tag.get_text(strip=True)
    h1 = soup.find(re.compile(r"^h[1-3]$"))
    if h1 and h1.get_text(strip=True):
        return h1.get_text(strip=True)
    return fallback


def find_heading_candidates(soup):
    """Find heading tags that mention eligibility."""
    heads = []
    for level in ["h1", "h2", "h3", "h4", "strong", "b"]:
        for tag in soup.find_all(level):
            txt = tag.get_text(" ", strip=True).lower()
            for kw in HEADING_KEYWORDS:
                if kw in txt:
                    heads.append(tag)
                    break
    return heads


def extract_block_after_heading(tag):
    """Extract text block following a heading until next heading."""
    parts = []
    for sib in tag.find_next_siblings():
        # Stop at next heading
        if sib.name and re.match(r"h[1-4]", sib.name, re.I):
            break
        if sib.name in ("p", "div", "ul", "ol", "table", "dl"):
            parts.append(sib.get_text("\n", strip=True))
        else:
            t = sib.get_text(" ", strip=True)
            if t:
                parts.append(t)
    return "\n".join(p for p in parts if p)


def fallback_search_for_eligibility(soup):
    """Search for eligibility keywords as fallback extraction method."""
    candidates = []
    nodes = soup.find_all(["p", "li", "div", "td"])
    for node in nodes:
        txt = node.get_text(" ", strip=True)
        if any(k in txt.lower() for k in FALLBACK_KEYWORDS):
            candidates.append(txt)
    if candidates:
        return "\n".join(candidates[:6])
    return ""


def detect_state(text):
    """Detect state from text using keyword matching."""
    if not text:
        return ""
    # Try exact state name match
    for s in STATES:
        if s.lower() in text.lower():
            return s
    # Try matching first word of state names
    tokens = re.findall(r"\b[A-Za-z]+\b", text)
    for tok in tokens:
        for s in STATES:
            if tok.lower() == s.split()[0].lower():
                return s
    return ""


def build_entry(title, description, state, source_url):
    """Build a scheme entry dict with safety checks."""
    return {
        "title": title if title is not None else "",
        "description": description if description is not None else "",
        "state": state if state is not None else "",
        "source_url": source_url if source_url is not None else ""
    }


def write_output_py(entries, out_path=OUTPUT_PY):
    """Write parsed entries as Python module for database seeding."""
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("# Auto-generated scheme data from web scraping\n")
        f.write("# # DEBUG: Verify this data looks correct before database import\n")
        f.write("SAMPLE_SCHEMES = [\n")
        for e in entries:
            title = repr(e["title"])
            desc = repr(e["description"])
            state = repr(e["state"])
            src = repr(e["source_url"])
            f.write(f"    {{'title': {title}, 'description': {desc}, 'state': {state}, 'source_url': {src}}},\n")
        f.write("]\n")
    print(f"Wrote {len(entries)} entries to: {out_path}")


def parse_all_html():
    """Main parsing pipeline: read HTML files and extract scheme data."""
    # Load URL mapping for scheme source links
    seed_map = load_seed_map()

    if not os.path.isdir(RAW_HTML_DIR):
        print(f"No raw HTML directory found: {RAW_HTML_DIR}")
        write_output_py([])
        return

    # Get all HTML files sorted for consistent output
    files = sorted(f for f in os.listdir(RAW_HTML_DIR) if f.lower().endswith(".html"))
    if not files:
        print("No .html files found under raw_html.")
        write_output_py([])
        return

    entries = []
    for fname in files:
        path = os.path.join(RAW_HTML_DIR, fname)
        html = read_html(path)
        if not html:
            print(f"[skip] could not read: {fname}")
            # # DEBUG: Log read failures
            # print(f"[DEBUG] Failed to read {path}")
            continue
        
        soup = BeautifulSoup(html, "html.parser")
        fallback_name = os.path.splitext(fname)[0]  # This is the url_key from fetcher
        title = extract_title(soup, fallback_name)

        # Try structured heading-based extraction first
        description = ""
        heading_tags = find_heading_candidates(soup)
        if heading_tags:
            for h in heading_tags:
                blk = extract_block_after_heading(h)
                if blk and len(blk.strip()) > 20:
                    description = blk
                    break

        # Fall back to keyword search if structured extraction didn't work
        if not description:
            description = fallback_search_for_eligibility(soup)

        # Clean up extracted text
        description = clean_text(description)
        # Detect state from combined title and description
        state = detect_state(" ".join([title, description]))

        # Try to find source URL via seed map
        url_key = os.path.splitext(fname)[0]
        source_url = seed_map.get(url_key, "")

        entries.append(build_entry(title=title, description=description, state=state, source_url=source_url))
        print(f"[ok] parsed {fname} -> title: {title} (state='{state}')")

    # Write final output for database import
    write_output_py(entries)


if __name__ == "__main__":
    parse_all_html()
