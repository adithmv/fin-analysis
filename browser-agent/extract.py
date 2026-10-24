"""Bounded text extraction; PDF parsing runs in a killable subprocess."""

import hashlib
from pathlib import Path
import subprocess
import sys
from bs4 import BeautifulSoup


def html_text(body,selector,maximum):
    soup=BeautifulSoup(body,"html.parser")
    node=soup.select_one(selector)
    if node is None:
        raise ValueError("Recipe content selector matched nothing")
    for child in node.select("script,style,nav,footer,form"):
        child.decompose()
    text=" ".join(node.stripped_strings)
    if not text:
        raise ValueError("Recipe extracted no text")
    return text[:maximum],len(text)>maximum


def pdf_text(body,folder,maximum):
    folder=Path(folder).resolve()
    folder.mkdir(parents=True,exist_ok=True)
    target=folder/(hashlib.sha256(body).hexdigest()+".pdf")
    target.write_bytes(body)
    result=subprocess.run([sys.executable,__file__,str(target),str(maximum)],capture_output=True,
        text=True,encoding="utf-8",timeout=25,check=True)
    return result.stdout[:maximum],str(target)


if __name__=="__main__":
    from pypdf import PdfReader

    reader=PdfReader(sys.argv[1],strict=True)
    if reader.is_encrypted or len(reader.pages)>100:
        raise ValueError("Encrypted or oversized PDF")
    remaining=int(sys.argv[2])
    for page in reader.pages:
        text=(page.extract_text() or "")[:remaining]
        print(text)
        remaining-=len(text)
        if remaining<=0:
            break
