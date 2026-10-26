from bs4 import BeautifulSoup
import re
import html

def parse_text(html: str) -> str:
    text = BeautifulSoup(html, "html.parser").get_text("\n", strip=True)
    return text


# our own inline tags (produced by the docx converter) must not be escaped
TAG_RE = re.compile(r"(</?(?:span|u|mark)\b[^>]*>)")


# a title/description downloaded from the constructor is already html: <p>...</p> or <h1>...</h1>
READY_HTML_RE = re.compile(r"^\s*<(p|h[1-6])\b[^>]*>.*</\1>\s*$", re.S)


def md_to_html(text: str) -> str:
    if READY_HTML_RE.match(text):
        return text.strip()

    # heading prefix "# ", "## " ... -> <h1>, <h2> ...
    tag = "p"
    m = re.match(r"^(#{1,6})\s+(.*)$", text, re.S)
    if m:
        tag = f"h{len(m.group(1))}"
        text = m.group(2)

    # escape &, <, > in plain text only, keep span/u/mark tags as they are
    parts = TAG_RE.split(text)
    parts = [p if i % 2 else html.escape(p, quote=False) for i, p in enumerate(parts)]
    s = "".join(parts)

    # markdown -> html (order matters: *** before ** before *)
    s = re.sub(r"\*\*\*(.+?)\*\*\*", r"<strong><em>\1</em></strong>", s, flags=re.S)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s, flags=re.S)
    s = re.sub(r"\*(.+?)\*", r"<em>\1</em>", s, flags=re.S)
    s = re.sub(r"~~(.+?)~~", r"<s>\1</s>", s, flags=re.S)

    s = s.replace("\n", "<br>")  # multi-paragraph table cells
    return f"<{tag}>{s}</{tag}>"


def md_html_serializer(self: "BaseModel", value: str) -> str:
    return md_to_html(value)