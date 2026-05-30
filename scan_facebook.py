import argparse
import csv
import re
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

PROFILE_DIR = Path("browser_profile").resolve()
OUTPUT_DIR = Path("output")
OUTPUT_FILE = OUTPUT_DIR / "storm_candidates.csv"

DAMAGE_CATEGORIES = {
    "wind_damage": [
        "tree down", "trees down", "limbs down", "branches down", "power line",
        "power lines", "wires down", "roof damage", "shingles", "siding",
        "soffit", "awning", "carport", "barn", "shed", "outbuilding",
        "roof torn", "structural damage", "pole snapped", "utility pole",
        "power pole", "collapsed", "flattened", "toppled", "ripped off",
        "tree on house", "tree on car", "blocking road", "road blocked",
    ],
    "tornado_possible": [
        "tornado", "funnel", "wall cloud", "rotating", "rotation",
        "debris cloud", "debris", "power flash",
    ],
    "hail": [
        "hail", "pea hail", "marble", "dime", "nickel", "quarter",
        "half dollar", "ping pong", "golf ball", "tennis ball",
        "baseball", "large hail", "damaging hail", "hail accumulation",
        "covered the ground",
    ],
    "flooding": [
        "flash flood", "flash flooding", "flooding", "river flooding",
        "creek overflow", "bankfull", "washout", "road washed out",
        "underpass", "culvert", "impassable", "water over road",
        "high water", "water in house", "water in business",
    ],
    "lightning": [
        "lightning strike", "struck by lightning", "transformer", "substation", "arcing",
    ],
    "wind_measured": [
        "measured gust", "estimated gust", "mph", "kts",
    ],
}

LOCATION_HINT_RE = re.compile(
    r"\b(?:on|at|near|by|around|along|between|off)\s+([A-Z0-9][A-Za-z0-9 .'\-]{2,80})",
    re.IGNORECASE,
)

def load_keywords(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()

def find_matches(text: str, keywords: list[str]) -> list[str]:
    lower = text.lower()
    return sorted({kw for kw in keywords if kw.lower() in lower}, key=len, reverse=True)

def categorize(matches: list[str]) -> str:
    found = []
    mset = {m.lower() for m in matches}
    for category, terms in DAMAGE_CATEGORIES.items():
        if any(term.lower() in mset for term in terms):
            found.append(category)
    return ";".join(found) if found else "unknown"

def confidence_score(matches: list[str], text: str) -> str:
    lower = text.lower()
    score = 0

    high_value = [
        "tree down", "trees down", "tree on house", "tree on car", "power lines",
        "wires down", "roof torn", "structural damage", "tornado", "funnel",
        "water over road", "road washed out", "golf ball", "baseball",
        "measured gust",
    ]

    if any(term in lower for term in high_value):
        score += 3
    if len(matches) >= 2:
        score += 1
    if LOCATION_HINT_RE.search(text):
        score += 1
    if re.search(r"\b\d{2,3}\s?(?:mph|kts|kt)\b", lower):
        score += 2
    if re.search(r"\b(?:hwy|highway|road|rd|street|st|ave|blvd|parish|county|near|at|on)\b", lower):
        score += 1

    if score >= 5:
        return "high"
    if score >= 3:
        return "medium"
    return "low"

def possible_location(text: str) -> str:
    match = LOCATION_HINT_RE.search(text)
    if not match:
        return ""
    loc = match.group(1)
    loc = re.split(r"\b(?:and|but|with|after|because|from|when)\b", loc, maxsplit=1, flags=re.IGNORECASE)[0]
    return loc.strip(" .,-")

def expand_buttons(page):
    labels = [
        "See more",
        "View more comments",
        "View previous comments",
        "More comments",
        "Most relevant",
        "All comments",
    ]
    for label in labels:
        try:
            for locator in [
                page.get_by_text(label, exact=False),
                page.locator(f"text={label}"),
            ]:
                count = min(locator.count(), 5)
                for i in range(count):
                    try:
                        locator.nth(i).click(timeout=1200)
                        time.sleep(0.5)
                    except Exception:
                        pass
        except Exception:
            pass

def extract_candidate_lines(text: str, keywords: list[str]) -> list[dict]:
    # Facebook text is messy. Start with line chunks, then score chunks with keywords.
    raw_lines = [normalize_text(x) for x in text.splitlines()]
    lines = [x for x in raw_lines if len(x) >= 20]

    candidates = []
    seen = set()

    for line in lines:
        matches = find_matches(line, keywords)
        if not matches:
            continue
        key = line[:300].lower()
        if key in seen:
            continue
        seen.add(key)

        candidates.append({
            "comment_or_text": line[:1000],
            "matched_keywords": ";".join(matches),
            "damage_category": categorize(matches),
            "possible_location": possible_location(line),
            "confidence": confidence_score(matches, line),
        })

    return candidates

def scan_source(page, source: dict, keywords: list[str], scrolls: int) -> list[dict]:
    url = source["url"]
    print(f"\nScanning: {source['name']} -> {url}")

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        time.sleep(4)
    except PlaywrightTimeoutError:
        print("  Timeout loading page.")
        return []

    for _ in range(scrolls):
        expand_buttons(page)
        page.mouse.wheel(0, 1800)
        time.sleep(2)

    expand_buttons(page)

    try:
        text = page.locator("body").inner_text(timeout=10000)
    except Exception:
        text = page.content()

    candidates = extract_candidate_lines(text, keywords)

    scan_time = datetime.now().isoformat(timespec="seconds")
    for item in candidates:
        item.update({
            "scan_time": scan_time,
            "source_name": source.get("name", ""),
            "source_region": source.get("region", ""),
            "source_category": source.get("category", ""),
            "source_url": url,
        })

    print(f"  Found {len(candidates)} candidate text chunks.")
    return candidates

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", default="sources.csv")
    parser.add_argument("--keywords", default="keywords.txt")
    parser.add_argument("--max-sources", type=int, default=5)
    parser.add_argument("--scrolls", type=int, default=5)
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(exist_ok=True)
    PROFILE_DIR.mkdir(exist_ok=True)

    sources_df = pd.read_csv(args.sources).fillna("")
    keywords = load_keywords(Path(args.keywords))

    if "url" not in sources_df.columns:
        raise ValueError("sources.csv must have a url column")

    sources = sources_df.to_dict("records")
    sources = [s for s in sources if "facebook.com" in str(s.get("url", "")).lower()]
    sources = sources[: args.max_sources]

    fieldnames = [
        "scan_time",
        "confidence",
        "damage_category",
        "possible_location",
        "matched_keywords",
        "comment_or_text",
        "source_name",
        "source_region",
        "source_category",
        "source_url",
    ]

    all_rows = []

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            viewport={"width": 1400, "height": 900},
            slow_mo=80,
        )
        page = context.new_page()

        for source in sources:
            try:
                all_rows.extend(scan_source(page, source, keywords, args.scrolls))
            except Exception as exc:
                print(f"  Error scanning {source.get('url')}: {exc}")

        context.close()

    with OUTPUT_FILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\nDone. Wrote {len(all_rows)} rows to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
