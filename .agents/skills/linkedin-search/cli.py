#!/usr/bin/env python3
"""
LinkedIn Guest Job Search CLI (Pure Python, Zero External Dependencies)
Ported from ai-job-search with 100% native urllib compatibility.
"""
import argparse
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
DETAIL_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "X-Requested-With": "XMLHttpRequest",
}


def html_fetch(url: str, max_retries: int = 4) -> str:
    delay = 1.0
    for attempt in range(max_retries + 1):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return ""
            if e.code in (429, 500, 502, 503, 504) and attempt < max_retries:
                time.sleep(delay)
                delay *= 2
                continue
            raise
        except Exception:
            if attempt < max_retries:
                time.sleep(delay)
                delay *= 2
                continue
            raise
    return ""


def jobage_to_tpr(days: int) -> Optional[str]:
    mapping = {1: "r86400", 7: "r604800", 14: "r1209600", 30: "r2592000"}
    return mapping.get(days)


def worktype_flag(mode: Optional[str]) -> Optional[str]:
    if not mode:
        return None
    mode = mode.lower()
    if mode == "onsite":
        return "1"
    if mode == "remote":
        return "2"
    if mode == "hybrid":
        return "3"
    return None


def parse_job_cards(raw_html: str) -> List[Dict[str, Any]]:
    cards = []
    # Match card containers
    parts = re.split(r'<li[^>]*>', raw_html)
    for part in parts:
        if 'base-card' not in part:
            continue
        
        # ID
        id_m = re.search(r'data-entity-urn="urn:li:jobPosting:(\d+)"', part)
        job_id = id_m.group(1) if id_m else ""
        
        # Link & ID fallback
        link_m = re.search(r'<a class="base-card__full-link[^"]*" href="([^"?]+)', part)
        link = link_m.group(1).strip() if link_m else ""
        if not job_id and link:
            fallback_id = re.search(r'-(\d+)$', link)
            if fallback_id:
                job_id = fallback_id.group(1)

        # Title
        title_m = re.search(r'<h3 class="base-search-card__title">([^<]+)</h3>', part)
        title = html.unescape(title_m.group(1).strip()) if title_m else ""

        # Company
        comp_m = re.search(r'<h4 class="base-search-card__subtitle">.*?<a[^>]*>([^<]+)</a>', part, re.DOTALL)
        if not comp_m:
            comp_m = re.search(r'<h4 class="base-search-card__subtitle">([^<]+)</h4>', part)
        company = html.unescape(comp_m.group(1).strip()) if comp_m else "Confidential Employer"

        # Location
        loc_m = re.search(r'<span class="job-search-card__location">([^<]+)</span>', part)
        loc = html.unescape(loc_m.group(1).strip()) if loc_m else ""

        # Date
        date_m = re.search(r'<time class="job-search-card__listdate"[^>]*>([^<]+)</time>', part)
        date_str = date_m.group(1).strip() if date_m else ""

        if title and (job_id or link):
            cards.append({
                "id": job_id,
                "title": title,
                "company": company,
                "location": loc,
                "date": date_str,
                "url": link,
            })
    return cards


def extract_job_detail(raw_html: str, job_id: str, job_url: str = "") -> Dict[str, Any]:
    title_m = re.search(r'<h2 class="top-card-layout__title[^"]*">([^<]+)</h2>', raw_html)
    if not title_m:
        title_m = re.search(r'<h1 class="top-card-layout__title[^"]*">([^<]+)</h1>', raw_html)
    title = html.unescape(title_m.group(1).strip()) if title_m else ""

    comp_m = re.search(r'<a class="topcard__org-name-link[^"]*"[^>]*>([^<]+)</a>', raw_html)
    if not comp_m:
        comp_m = re.search(r'<span class="topcard__flavor">([^<]+)</span>', raw_html)
    company = html.unescape(comp_m.group(1).strip()) if comp_m else ""

    loc_m = re.search(r'<span class="topcard__flavor topcard__flavor--bullet">([^<]+)</span>', raw_html)
    location = html.unescape(loc_m.group(1).strip()) if loc_m else ""

    # Clean description body
    desc_raw = ""
    desc_m = re.search(r'<div class="show-more-less-html__markup[^"]*"[^>]*>(.*?)</div>', raw_html, re.DOTALL)
    if desc_m:
        desc_raw = desc_m.group(1)
    else:
        desc_m = re.search(r'<section class="description">(.*?)</section>', raw_html, re.DOTALL)
        if desc_m:
            desc_raw = desc_m.group(1)

    clean_desc = re.sub(r'<[^>]+>', ' ', desc_raw)
    clean_desc = html.unescape(re.sub(r'\s+', ' ', clean_desc).strip())

    return {
        "id": job_id,
        "title": title,
        "company": company,
        "location": location,
        "url": job_url or f"https://www.linkedin.com/jobs/view/{job_id}",
        "description": clean_desc,
        "isActive": "This job is no longer accepting applications" not in raw_html,
    }


def cmd_search(args) -> int:
    params = {}
    if args.query:
        params["keywords"] = args.query
    if args.location:
        params["location"] = args.location
    if args.jobage:
        tpr = jobage_to_tpr(args.jobage)
        if tpr:
            params["f_TPR"] = tpr
    if args.remote:
        wt = worktype_flag(args.remote)
        if wt:
            params["f_WT"] = wt
    
    page = max(1, args.page)
    params["start"] = str((page - 1) * 10)

    url = f"{SEARCH_URL}?{urllib.parse.urlencode(params)}"
    raw_html = html_fetch(url)
    cards = parse_job_cards(raw_html)
    if args.limit:
        cards = cards[:args.limit]

    if args.format == "table":
        if not cards:
            print("No results found.")
            return 0
        header = f"{'ID'.ljust(12)} {'TITLE'.ljust(40)} {'COMPANY'.ljust(25)} {'LOCATION'.ljust(22)} DATE"
        print(header)
        print("-" * len(header))
        for c in cards:
            t = (c['title'][:38] + '..') if len(c['title']) > 40 else c['title']
            cp = (c['company'][:23] + '..') if len(c['company']) > 25 else c['company']
            lc = (c['location'][:20] + '..') if len(c['location']) > 22 else c['location']
            print(f"{c['id'].ljust(12)} {t.ljust(40)} {cp.ljust(25)} {lc.ljust(22)} {c['date']}")
    elif args.format == "plain":
        for c in cards:
            print(f"{c['title']}\n  {c['company']} · {c['location']} · {c['date']}\n  id: {c['id']}\n  {c['url']}\n")
    else:
        print(json.dumps({"meta": {"count": len(cards), "page": page}, "results": cards}, indent=2, ensure_ascii=False))
    return 0


def cmd_detail(args) -> int:
    target = args.id_or_url.strip()
    match_id = re.search(r'(\d{8,})', target)
    if not match_id:
        sys.stderr.write(json.dumps({"error": "Invalid job ID or LinkedIn URL", "code": "INVALID_ID"}) + "\n")
        return 1
    job_id = match_id.group(1)
    url = f"{DETAIL_URL}/{job_id}"
    raw_html = html_fetch(url)
    if not raw_html:
        sys.stderr.write(json.dumps({"error": "Job posting not found", "code": "NOT_FOUND"}) + "\n")
        return 1

    detail = extract_job_detail(raw_html, job_id, target if "http" in target else "")
    if args.format == "plain":
        print(f"Title: {detail['title']}")
        print(f"Company: {detail['company']}")
        print(f"Location: {detail['location']}")
        print(f"URL: {detail['url']}")
        print(f"Active: {'Yes' if detail['isActive'] else 'No'}")
        print("\n--- Description ---")
        print(detail['description'])
    else:
        print(json.dumps(detail, indent=2, ensure_ascii=False))
    return 0


def main():
    parser = argparse.ArgumentParser(description="LinkedIn Guest Search CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Search command
    s_parser = subparsers.add_parser("search", help="Search job listings")
    s_parser.add_argument("-l", "--location", required=True, help="Location (e.g. 'Australia', 'Canada', 'Remote')")
    s_parser.add_argument("-q", "--query", default="", help="Search query keywords")
    s_parser.add_argument("--jobage", type=int, choices=[1, 7, 14, 30], default=None, help="Posted within days")
    s_parser.add_argument("--remote", choices=["remote", "hybrid", "onsite"], default=None, help="Workplace type")
    s_parser.add_argument("--page", type=int, default=1, help="Page number (1-based)")
    s_parser.add_argument("-n", "--limit", type=int, default=15, help="Result limit")
    s_parser.add_argument("--format", choices=["json", "table", "plain"], default="json", help="Output format")

    # Detail command
    d_parser = subparsers.add_parser("detail", help="Fetch job details")
    d_parser.add_argument("id_or_url", help="Job ID or LinkedIn posting URL")
    d_parser.add_argument("--format", choices=["json", "plain"], default="json", help="Output format")

    args = parser.parse_args()
    if args.command == "search":
        sys.exit(cmd_search(args))
    elif args.command == "detail":
        sys.exit(cmd_detail(args))


if __name__ == "__main__":
    main()
