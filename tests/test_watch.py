"""Tests hors-ligne : simule deux passages sur des pages type (sans réseau)."""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import watch  # noqa: E402

REXEL_V1 = """<html><body><nav><a href="/fr/investisseurs">Investisseurs</a></nav>
<h3>Ventes du T2 2026 et résultats S1 2026</h3>
<a href="https://www.rexel.com/app/uploads/2026/05/CP-Ventes-du-T2-2026-et-resultats-S1-2026-.pdf">Communiqué de presse – Ventes du T2 2026</a>
<a href="/app/uploads/2026/07/Rexel-Etats-Financiers-2026-06-def.pdf">Rapport financier – 1er semestre 2026</a>
</body></html>"""
REXEL_V2 = REXEL_V1.replace("<h3>", """<h3>Ventes du T3 2026</h3>
<a href="/app/uploads/2026/09/CP-Ventes-du-T3-2026.pdf">Communiqué de presse – Ventes du T3 2026</a>
<a href="/app/uploads/2026/09/Presentation-Q3-2026-sales.pdf#page=2">Présentation – Ventes du T3 2026</a>
<h3>""", 1)

SCHNEIDER = """<a href="/ww/fr/assets/pdf/communique-T3-2026">/ww/fr/assets/pdf/communique-T3-2026</a>
<a href="/ww/fr/assets/342/document/44667/22-communique-adoption-de-wiztrust.pdf">Wiztrust</a>
<a href="/ww/fr/about-us/investor-relations/">Accueil</a>"""

SITE = {"slug": "rexel", "name": "Rexel", "url": "https://www.rexel.com/fr/investisseurs/resultats-financiers"}
SE = {"slug": "schneider", "name": "Schneider Electric", "url": "https://www.se.com/ww/fr/about-us/investor-relations/financial-results/",
      "include": r"(/assets/pdf/|p_Doc_Ref=|\.pdf(\?|$))", "exclude": "wiztrust"}
TS = datetime(2026, 10, 27, 8, 0, tzinfo=timezone.utc)


def test_baseline_then_new_docs_grouped():
    state = {}
    assert watch.check_site(SITE, state, TS, fetcher=lambda u: REXEL_V1) == []   # référence : pas d'alerte
    assert state["rexel"]["count"] == 2
    assert watch.check_site(SITE, state, TS, fetcher=lambda u: REXEL_V1) == []   # rien de neuf
    items = watch.check_site(SITE, state, TS, fetcher=lambda u: REXEL_V2)
    assert len(items) == 1 and "2 nouveaux documents" in items[0]["title"]
    assert "Presentation-Q3-2026-sales.pdf" in items[0]["body"] and "#page" not in items[0]["body"]
    assert watch.check_site(SITE, state, TS, fetcher=lambda u: REXEL_V2) == []   # pas de doublon


def test_failure_keeps_history_and_alerts_once():
    state = {}
    watch.check_site(SITE, state, TS, fetcher=lambda u: REXEL_V1)
    def boom(u): raise watch.requests.HTTPError("403 Forbidden")
    a = watch.check_site(SITE, state, TS, fetcher=boom)
    assert len(a) == 1 and "à vérifier" in a[0]["title"]
    assert watch.check_site(SITE, state, TS, fetcher=lambda u: "<html></html>") == []  # pas de 2e alerte
    assert len(state["rexel"]["seen"]) == 2                                            # historique intact
    back = watch.check_site(SITE, state, TS, fetcher=lambda u: REXEL_V2)
    assert any("rétabli" in i["title"] for i in back) and any("nouveaux" in i["title"] for i in back)


def test_schneider_patterns():
    links = watch.extract_links(SCHNEIDER, SE["url"], SE["include"], SE["exclude"])
    assert list(links) == ["https://www.se.com/ww/fr/assets/pdf/communique-T3-2026"]


def test_rss_is_valid_xml(tmp_path):
    import xml.etree.ElementTree as ET
    state = {}
    watch.check_site(SITE, state, TS, fetcher=lambda u: REXEL_V1)
    items = watch.check_site(SITE, state, TS, fetcher=lambda u: REXEL_V2)
    out = tmp_path / "feed.xml"
    watch.render_rss(items, "t", "https://x", out)
    root = ET.parse(out).getroot()
    assert root.find("channel/item/title").text.startswith("Rexel")


def test_issue_notifications_only_for_publications_and_alerts():
    state, sent = {}, []
    watch.check_site(SITE, state, TS, fetcher=lambda u: REXEL_V1)
    items = watch.check_site(SITE, state, TS, fetcher=lambda u: REXEL_V2)
    items.append(watch.make_item(SITE, "✅ Rexel : suivi rétabli", "", SITE["url"], TS))  # info : pas d'e-mail
    n = watch.notify_issues(items, "o/r", "t", post=lambda url, payload: sent.append((url, payload)))
    assert n == 1 and sent[0][0] == "https://api.github.com/repos/o/r/issues"
    assert "[Communiqué de presse – Ventes du T3 2026](https://www.rexel.com/app/uploads/2026/09/CP-Ventes-du-T3-2026.pdf)" in sent[0][1]["body"]
