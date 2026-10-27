import json, requests, re
from watch import HEADERS
urls = {
 "euronext_bouygues": "https://live.euronext.com/fr/listview/company-press-release/003126",
 "euronext_schneider": "https://live.euronext.com/fr/listview/company-press-release/003751",
 "euronext_rss": "https://live.euronext.com/rss/company-pr-release",
 "dila_amf": "https://echanges.dila.gouv.fr/OPENDATA/AMF/",
 "se_press": "https://www.se.com/ww/fr/about-us/newsroom/news/press-releases/",
 "bouygues_cp": "https://www.bouygues.com/communiques-de-presse/",
}
out = {}
for k, u in urls.items():
    try:
        r = requests.get(u, headers=HEADERS, timeout=30)
        hrefs = re.findall(r'href="([^"]+)"', r.text)
        out[k] = {"status": r.status_code, "len": len(r.text), "n_href": len(hrefs),
                  "sample_href": [h for h in hrefs if re.search(r'(news|press|pr|\.zip|\.pdf|node|AMF|20\d\d)', h, re.I)][:40],
                  "head": r.text[:1500]}
    except Exception as e:
        out[k] = {"error": str(e)[:300]}
for k in ("euronext_bouygues", "euronext_schneider"):
    try:
        open(f"state/{k}.html", "w").write(requests.get(urls[k], headers=HEADERS, timeout=30).text)
    except Exception as e:
        print(k, e)
json.dump(out, open("state/probe.json", "w"), ensure_ascii=False, indent=1)
print({k: v.get("status", v.get("error")) for k, v in out.items()})
