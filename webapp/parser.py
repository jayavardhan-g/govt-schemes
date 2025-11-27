import os
import csv
import re
import hashlib
from urllib.parse import urlparse
from bs4 import BeautifulSoup

script_dr = os.path.dirname(os.path.abspath(__file__))
html_save = os.path.join(script_dr, "output", "raw_html")
urlss = os.path.join(script_dr, "seedurls.csv")
op_file = os.path.join(script_dr, "output", "sample_schemes.py")

h_keywords = [
    "eligibility", "eligibility criteria", "who can apply", "who is eligible",
    "conditions for eligibility", "eligible", "applicants"
]

fb_words = [
    "eligible", "not eligible", "income", "annual income", "age", "years", "resident",
    "citizen", "widow", "women", "household", "beneficiary", "ownership", "landholding", "student"
]

states = [
    "Andhra Pradesh","Arunachal Pradesh","Assam","Bihar","Chhattisgarh",
    "Goa","Gujarat","Haryana","Himachal Pradesh","Jharkhand","Karnataka",
    "Kerala","Madhya Pradesh","Maharashtra","Manipur","Meghalaya","Mizoram",
    "Nagaland","Odisha","Punjab","Rajasthan","Sikkim","Tamil Nadu",
    "Telangana","Tripura","Uttar Pradesh","Uttarakhand","West Bengal",
    "Delhi","Jammu and Kashmir","Ladakh"
]


def url_to_filename(url: str) -> str:
    parsed = urlparse(url)
    domain = parsed.netloc.replace(":", "_")
    path_part = parsed.path.strip("/").replace("/", "_") or "index"
    base = f"{domain}__{path_part}"
    h = hashlib.sha1(url.encode("utf-8")).hexdigest()[:8]
    url_key = "".join(c if c.isalnum() or c in ("-", "_", ".") else "_" for c in f"{base}__{h}")
    return url_key


def load_seed_map(csv_path=urlss):
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
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return None


def clean_text(s):
    if not s:
        return ""
    s = re.sub(r"\r\n?", "\n", s)
    s = re.sub(r"\u2022|\u2023|\u25E6|\u2043|\u2219", "-", s)
    s = re.sub(r"\n\s*\n+", "\n", s)
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()


def extract_title(soup, fallback):
    tag = soup.find("title")
    if tag and tag.get_text(strip=True):
        return tag.get_text(strip=True)
    h1 = soup.find(re.compile(r"^h[1-3]$"))
    if h1 and h1.get_text(strip=True):
        return h1.get_text(strip=True)
    return fallback


def find_heading_candidates(soup):
    heads = []
    for level in ["h1", "h2", "h3", "h4", "strong", "b"]:
        for tag in soup.find_all(level):
            txt = tag.get_text(" ", strip=True).lower()
            for kw in h_keywords:
                if kw in txt:
                    heads.append(tag)
                    break
    return heads


def extract_block_after_heading(tag):
    parts = []
    for sib in tag.find_next_siblings():
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
    candidates = []
    nodes = soup.find_all(["p", "li", "div", "td"])
    for node in nodes:
        txt = node.get_text(" ", strip=True)
        if any(k in txt.lower() for k in fb_words):
            candidates.append(txt)
    if candidates:
        return "\n".join(candidates[:6])
    return ""


def detect_state(text):
    if not text:
        return ""
    for s in states:
        if s.lower() in text.lower():
            return s
    tokens = re.findall(r"\b[A-Za-z]+\b", text)
    for tok in tokens:
        for s in states:
            if tok.lower() == s.split()[0].lower():
                return s
    return ""


def build_entry(title, description, state, source_url):
    return {
        "title": title if title is not None else "",
        "description": description if description is not None else "",
        "state": state if state is not None else "",
        "source_url": source_url if source_url is not None else ""
    }


def write_output_py(entries, out_path=op_file):
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
    seed_map = load_seed_map()

    if not os.path.isdir(html_save):
        print(f"No raw HTML directory found: {html_save}")
        write_output_py([])
        return

    files = sorted(f for f in os.listdir(html_save) if f.lower().endswith(".html"))
    if not files:
        print("No .html files found under raw_html.")
        write_output_py([])
        return

    entries = []
    for fname in files:
        path = os.path.join(html_save, fname)
        html = read_html(path)
        if not html:
            print(f"[skip] could not read: {fname}")
            continue
        
        soup = BeautifulSoup(html, "html.parser")
        fallback_name = os.path.splitext(fname)[0]
        title = extract_title(soup, fallback_name)

        description = ""
        heading_tags = find_heading_candidates(soup)
        if heading_tags:
            for h in heading_tags:
                blk = extract_block_after_heading(h)
                if blk and len(blk.strip()) > 20:
                    description = blk
                    break

        if not description:
            description = fallback_search_for_eligibility(soup)

        description = clean_text(description)
        state = detect_state(" ".join([title, description]))

        url_key = os.path.splitext(fname)[0]
        source_url = seed_map.get(url_key, "")

        entries.append(build_entry(title=title, description=description, state=state, source_url=source_url))
        print(f"[ok] parsed {fname} -> title: {title} (state='{state}')")

    write_output_py(entries)

if __name__ == "__main__":
    parse_all_html()