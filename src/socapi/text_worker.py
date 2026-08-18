from bs4 import BeautifulSoup

def parse_text(html: str) -> str:
    text = BeautifulSoup(html, "html.parser").get_text("\n", strip=True)
    return text