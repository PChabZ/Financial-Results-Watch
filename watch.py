#!/usr/bin/env python3
"""IR Watch : détecte les nouveaux documents sur des pages "résultats" et publie un flux RSS.

Principe : pour chaque page, on relève tous les liens vers des documents ; tout lien
jamais vu auparavant = nouvelle publication. Premier passage sur une page = référence
(aucune alerte). Un passage qui ne trouve aucun document ne touche pas à l'historique
et génère une alerte "à vérifier" (page cassée, refonte, blocage).
"""
import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from urllib.parse import urljoin, urldefrag
from xml.sax.saxutils import escape

import requests
import yaml
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
DEFAULT_INCLUDE = r"\.(pdf|xlsx?|xlsm)(\?|$)"
MAX_ITEMS = 150
UA = "Mozilla/5.0 (compatible; ir-watch/1.0; personal RSS generator)"


def now():
    return datetime.now(timezone.utc)


def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")


def fetch(url, timeout=30):
    r = requests.get(url, headers={"User-Agent": UA, "Accept-Language": "fr,en;q=0.8"}, timeout=timeout)
    r.raise_for_status()
    return r.text


def extract_links(html, base_url, include, exclude=None, scope=None):
    """Retourne {url_absolue: libellé} pour les liens documents de la page."""
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one(scope) if scope else soup
    if root is None:
        return {}
    inc = re.compile(include, re.I)
    exc = re.compile(exclude, re.I) if exclude else None
    out = {}
    for a in root.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("mailto:", "javascript:", "#")):
            continue
        url = urldefrag(urljoin(base_url, href))[0]
        if not inc.search(url) or (exc and (exc.search(url) or exc.search(a.get_text(" ")))):
            continue
        label = " ".join(a.get_text(" ").split()) or a.get("title", "") or url.rsplit("/", 1)[-1]
        # garde le libellé le plus parlant si le lien apparaît plusieurs fois
        if url not in out or (len(label) > len(out[url]) and not label.startswith("http")):
            out[url] = label
    return out


def make_item(site, title, body_html, link, ts):
    guid = hashlib.sha1(f"{site['slug']}|{title}|{ts.isoformat()}".encode()).hexdigest()
    return {"guid": guid, "slug": site["slug"], "site": site["name"], "title": title,
            "link": link, "body": body_html, "date": ts.isoformat()}


def check_site(site, state, ts, fetcher=fetch):
    """Met à jour state[slug] et renvoie la liste des items à publier."""
    slug = site["slug"]
    s = state.setdefault(slug, {"seen": {}, "healthy": True, "baseline_done": False})
    try:
        links = extract_links(fetcher(site["url"]), site["url"],
                              site.get("include", DEFAULT_INCLUDE), site.get("exclude"), site.get("scope"))
        error = None if links else "aucun document trouvé sur la page"
    except Exception as e:  # réseau, 403, timeout...
        links, error = {}, f"{type(e).__name__}: {e}"[:200]

    if error:
        print(f"[{slug}] ERREUR : {error}")
        s["last_error"] = error
        if s.get("healthy", True):          # alerte une seule fois, pas à chaque passage
            s["healthy"] = False
            return [make_item(site, f"⚠️ {site['name']} : page à vérifier",
                              f"<p>Le relevé a échoué ({escape(error)}). L'historique est conservé ; "
                              f"le suivi reprendra automatiquement.</p>", site["url"], ts)]
        return []

    items = []
    if not s.get("healthy", True):
        items.append(make_item(site, f"✅ {site['name']} : suivi rétabli", "<p>La page est de nouveau lisible.</p>", site["url"], ts))
    s["healthy"] = True
    s.pop("last_error", None)

    new = {u: l for u, l in links.items() if u not in s["seen"]}
    for u, l in links.items():
        s["seen"].setdefault(u, {"label": l, "first_seen": ts.isoformat()})
    s["last_ok"] = ts.isoformat()
    s["count"] = len(links)

    if not s.get("baseline_done"):
        s["baseline_done"] = True
        print(f"[{slug}] référence enregistrée : {len(links)} documents")
        return items
    if new:
        print(f"[{slug}] {len(new)} nouveau(x) document(s)")
        lis = "".join(f'<li><a href="{escape(u)}">{escape(l)}</a></li>' for u, l in new.items())
        first_label = next(iter(new.values()))
        title = f"{site['name']} : {first_label}" if len(new) == 1 else f"{site['name']} : {len(new)} nouveaux documents — {first_label}"
        note = "<p><em>Volume inhabituel : possible refonte de la page.</em></p>" if len(new) > 25 else ""
        items.append(make_item(site, title, f"{note}<ul>{lis}</ul><p>Page : <a href=\"{escape(site['url'])}\">{escape(site['url'])}</a></p>",
                               next(iter(new)) if len(new) == 1 else site["url"], ts))
    else:
        print(f"[{slug}] rien de nouveau ({len(links)} documents)")
    return items


def render_rss(items, title, link, path):
    rows = []
    for it in items:
        d = format_datetime(datetime.fromisoformat(it["date"]))
        rows.append(
            f"<item><title>{escape(it['title'])}</title><link>{escape(it['link'])}</link>"
            f"<guid isPermaLink=\"false\">{it['guid']}</guid><pubDate>{d}</pubDate>"
            f"<category>{escape(it['site'])}</category>"
            f"<description>{escape(it['body'])}</description></item>")
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel>'
           f"<title>{escape(title)}</title><link>{escape(link)}</link>"
           "<description>Nouvelles publications financières détectées</description>"
           f"<lastBuildDate>{format_datetime(now())}</lastBuildDate>" + "".join(rows) + "</channel></rss>\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(xml, encoding="utf-8")


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--config", default=ROOT / "sites.yaml", type=Path)
    p.add_argument("--state", default=ROOT / "state", type=Path)
    p.add_argument("--out", default=ROOT / "docs", type=Path)
    p.add_argument("--only", help="slug d'un seul site (test)")
    args = p.parse_args(argv)

    sites = yaml.safe_load(args.config.read_text(encoding="utf-8"))["sites"]
    if args.only:
        sites = [s for s in sites if s["slug"] == args.only]
    state = load_json(args.state / "sites.json", {})
    history = load_json(args.state / "items.json", [])
    ts = now()

    new_items = []
    for site in sites:
        new_items += check_site(site, state, ts)

    history = (new_items + history)[:MAX_ITEMS]
    save_json(args.state / "sites.json", state)
    save_json(args.state / "items.json", history)

    render_rss(history, "IR Watch — toutes les entreprises", "https://github.com", args.out / "feed.xml")
    for site in yaml.safe_load(args.config.read_text(encoding="utf-8"))["sites"]:
        render_rss([i for i in history if i["slug"] == site["slug"]], f"IR Watch — {site['name']}",
                   site["url"], args.out / f"{site['slug']}.xml")
    print(f"{len(new_items)} item(s) publiés ce passage.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
