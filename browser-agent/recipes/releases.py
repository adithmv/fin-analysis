from urllib.parse import urljoin
from bs4 import BeautifulSoup


def links(html,base,selector):
    soup=BeautifulSoup(html,"html.parser")
    found=list(dict.fromkeys(urljoin(base,a["href"]) for a in soup.select(selector) if a.get("href")))
    if not found:
        raise ValueError("Recipe found zero links; check the listing selector")
    return found
