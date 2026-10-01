from __future__ import annotations

from typing import List, Type, TypeVar, TYPE_CHECKING, Optional
import orjson
from pydantic import BaseModel
from enum import StrEnum

from docx import Document
from docx.shared import RGBColor, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.style import WD_STYLE_TYPE
from docx.text.paragraph import Paragraph
from docx.table import Table, _Cell
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.enum.dml import MSO_COLOR_TYPE

import re
import html

# NOTE: the PyPI package literally named `html4docx` (0.0.3) does NOT
# export `HtmlToDocx` - it's an unrelated, seemingly abandoned docx-to-html
# converter (confirmed by installing it). The `HtmlToDocx` class with
# `add_html_to_document`/`add_html_to_cell` methods used below comes from
# a different project (e.g. the pqzx/html4docx GitHub repo, often installed
# via `pip install git+https://github.com/pqzx/html4docx.git`). Make sure
# your actual dependency pin points at that, not the PyPI package of the
# same name, or this import silently gets the wrong library.
from html4docx import HtmlToDocx
from bs4 import BeautifulSoup
import re

if TYPE_CHECKING:
    from .resources.polls import Poll
    from .resources.blocks import Block
from .resources.logic import DisplayAnswers, Display, Jump, JOIN_CONDITION_TO_STR
from .resources.questions import AnswerTypes, Question, Answer
from itertools import groupby

T = TypeVar("T", bound=BaseModel)


def to_json(model: BaseModel, file_path: str) -> None:
    """Serialize a pydantic model to a pretty-printed JSON file."""
    with open(file_path, "wb") as f:
        f.write(orjson.dumps(model.model_dump(mode="json"), option=orjson.OPT_INDENT_2))


def from_json(cls: Type[T], file_path: str) -> T:
    """Load and validate a pydantic model of type ``cls`` from a JSON file."""
    with open(file_path, "rb") as f:
        data = orjson.loads(f.read())
    return cls.model_validate(data)


DEFAULT_STYLE_NAME = 'Arial 11'
SUPPORT_STYLE_NAME = 'Support'
SUPPORT_STYLE_NAME_CHARACTER = 'Support Character'
DEFAULT_FONT_NAME = 'Arial'
DEFAULT_FONT_SIZE = 11
DEFAULT_COLOR = RGBColor(0, 0, 0)
BLUE_COLOR = RGBColor(0, 112, 192)
BLOCK_HEADER_FILL_COLOR = 'D9EAF7'

ANSWER_TYPES_LABELS = {
    AnswerTypes.single_answer: 'Один ответ',
    AnswerTypes.dropdown: "Выпадающий список",
    AnswerTypes.single_answer_per_row: "Один ответ по строке",
    AnswerTypes.multiple_choice: "Множественный выбор",
    AnswerTypes.open_question: "Открытый вопрос",
    AnswerTypes.ranking: "Ранжирование",
    AnswerTypes.slider: "Ползунок",
    AnswerTypes.multiple_choice_per_row: "Множественный выбор по строке",
    AnswerTypes.info_material: "Ознакомительный материал",
    AnswerTypes.email_request: "Запрос почты",
}


class BlockNames(StrEnum):
    description = "Описание блока (видно респонденту):"
    header = "Заголовок блока (видно респонденту):"


class QuestionSpecs(StrEnum):
    max_answers = "Максимум ответов: {x}"
    optional = "Необязателен к ответу"
    randomized = "Перемешивать ответы"
    children_randomized = "Перемешивать подвопросы"

class AnswerSpec(StrEnum):
    skip_randomize = "Не перемешивать"
    exclude = "Исключающий ответ"
    has_input = "Поле для ввода"
    input_validation = "Маска" # TODO specific masks

# class LogicTemplates(StrEnum):
#     display="Вопрос будет показан"
#     jump="Переход на {target_type} {target}"
#     display_answer="Ответ будет показан"


def set_table_borders(table: Table) -> None:
    """Add thin black borders on every edge/gridline of ``table``."""
    tbl = table._tbl
    tblPr = tbl.tblPr

    borders = OxmlElement('w:tblBorders')

    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        element = OxmlElement(f"w:{edge}")
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), "4")   # thin line
        element.set(qn("w:color"), "000000")
        element.set(qn("w:space"), "0")
        borders.append(element)

    tblPr.append(borders)


def replace_paragraphs_with_breaks(html: str) -> str:
    """
    Flatten every top-level ``<p>`` in ``html`` into a single paragraph
    joined by ``<br>``, so html4docx renders it as one Word paragraph with
    line breaks instead of several separate paragraphs.
    """
    soup = BeautifulSoup(html, "html.parser")
    paragraphs = soup.find_all("p")

    # If no <p> tags → treat as plain string
    if not paragraphs:
        text = html.strip()
        if not text:
            return ""
        return f"<p>{text}</p>"

    parts = []
    for p in paragraphs:
        content = p.decode_contents().strip()
        content = re.sub(r"^(<br\s*/?>\s*)+", "", content, flags=re.IGNORECASE)
        content = re.sub(r"(<br\s*/?>\s*)+$", "", content, flags=re.IGNORECASE)
        if content:
            parts.append(content)

    return "<br>".join(parts)


class ExtendedDocument:
    """Document wrapper with the styling/layout actions ``export_docx`` needs."""

    def __init__(self):
        self.doc = Document()
        self.parser = HtmlToDocx(default_paragraph_style=DEFAULT_STYLE_NAME)

    # -- style setup ----------------------------------------------------

    @staticmethod
    def _apply_font(
            style,
            *,
            name: str = DEFAULT_FONT_NAME,
            size: Pt = Pt(DEFAULT_FONT_SIZE),
            color: RGBColor = DEFAULT_COLOR,
            italic: bool = False,
    ) -> None:
        """Set name/size/color/italic on a docx style's ``.font``."""
        font = style.font
        font.name = name
        font.size = size
        font.color.rgb = color
        font.italic = italic

    @staticmethod
    def _apply_paragraph_spacing(
            style,
            *,
            space_before: Pt = Pt(0),
            space_after: Pt = Pt(0),
            line_spacing: float = 1.0,
            left_indent: Optional[Pt] = None,
    ) -> None:
        """Set spacing/indent on a docx style's ``.paragraph_format``."""
        pf = style.paragraph_format
        pf.space_before = space_before
        pf.space_after = space_after
        pf.line_spacing = line_spacing
        if left_indent is not None:
            pf.left_indent = left_indent

    def configure_default_style(self) -> None:
        style = self.doc.styles.add_style(DEFAULT_STYLE_NAME, WD_STYLE_TYPE.PARAGRAPH)
        self._apply_paragraph_spacing(style, space_before=Pt(18))
        self._apply_font(style)

    def configure_support_style(self) -> None:
        style = self.doc.styles.add_style(SUPPORT_STYLE_NAME, WD_STYLE_TYPE.PARAGRAPH)
        self._apply_font(style, color=BLUE_COLOR, italic=True)
        self._apply_paragraph_spacing(style, space_before=Pt(5), left_indent=Pt(18))

    def configure_support_character_style(self) -> None:
        style = self.doc.styles.add_style(SUPPORT_STYLE_NAME_CHARACTER, WD_STYLE_TYPE.CHARACTER)
        self._apply_font(style, color=BLUE_COLOR, italic=True)

    def modify_heading_style(self) -> None:
        self._apply_font(self.doc.styles["Heading 1"])

    def format_numberings(self) -> None:
        """Apply the default font/spacing to Word's built-in numbered-list styles."""
        styles = self.doc.styles
        for name in ("List Number", "List Number 2"):
            styles[name].font.name = DEFAULT_FONT_NAME
            self._apply_paragraph_spacing(styles[name])

        styles["List Number"].paragraph_format.space_before = Pt(18)
        styles["List Number 2"].paragraph_format.space_before = Pt(5)

    # -- basic content ----------------------------------------------------

    def add_footer(self, title: str) -> None:
        paragraph = self.doc.sections[0].footer.add_paragraph(title)
        # add_paragraph() only creates a run when `title` is non-empty, so
        # `.runs[0]` would raise IndexError for an empty title -
        # fall back to creating the run ourselves in that case.
        run = paragraph.runs[0] if paragraph.runs else paragraph.add_run(title)
        run.font.name = DEFAULT_FONT_NAME
        run.font.size = Pt(DEFAULT_FONT_SIZE)

    def set_title(self, title: str) -> None:
        p = self.doc.add_heading(level=0)
        p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER

        run = p.add_run(title)
        run.font.name = DEFAULT_FONT_NAME
        run.font.size = Pt(DEFAULT_FONT_SIZE)
        run.font.color.rgb = DEFAULT_COLOR
        run.bold = True

    def _add_html_paragraph(self, html: str, merge_paragraphs: bool = True) -> Paragraph:
        """Render ``html`` into the document and return the last paragraph produced."""
        if merge_paragraphs:
            html = replace_paragraphs_with_breaks(html)
        self.parser.add_html_to_document(html, self.doc)
        return self.doc.paragraphs[-1]

    def set_default_style(self, paragraph: Paragraph) -> Paragraph:
        for run in paragraph.runs:
            font = run.font
            font.name = DEFAULT_FONT_NAME
            font.size = Pt(DEFAULT_FONT_SIZE)
        return paragraph

    def add_styled_html_paragraph(self, html: str) -> Paragraph:
        p = self._add_html_paragraph(html, merge_paragraphs=True)
        return self.set_default_style(paragraph=p)

    def set_description(self, description: str) -> None:
        """
        Render a (possibly multi-paragraph) HTML description and style every
        fragment it produces.
        """
        self.add_styled_html_paragraph(description)

    def add_block_header(self, block_title: str) -> None:
        head = self.doc.add_heading(block_title, level=1)
        head.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # Access paragraph properties
        p_pr = head._element.get_or_add_pPr()

        # Create shading element
        shd = OxmlElement('w:shd')
        shd.set(qn('w:fill'), BLOCK_HEADER_FILL_COLOR)  # Hex color without #
        p_pr.append(shd)

    def list_number(self, par, prev=None, level=None, numbered=True) -> None:
        """
        Workaround to reset list numbering.
        Call after creating new paragraph and pass previous numbered paragraph.
        If None as previous paragraph passed - numbering will be reset.

        (Standard python-docx community workaround for restarting a
        numbered list mid-document, since python-docx has no built-in way
        to do this - manipulates the underlying OOXML numbering directly.)
        """
        xpath_options = {
            True: {"single": "count(w:lvl)=1 and ", "level": 0},
            False: {"single": "", "level": level},
        }

        def style_xpath(prefer_single=True):
            style = par.style.style_id
            return (
                'w:abstractNum['
                '{single}w:lvl[@w:ilvl="{level}"]/w:pStyle[@w:val="{style}"]'
                ']/@w:abstractNumId'
            ).format(style=style, **xpath_options[prefer_single])

        def type_xpath(prefer_single=True):
            t = "decimal" if numbered else "bullet"
            return (
                'w:abstractNum['
                '{single}w:lvl[@w:ilvl="{level}"]/w:numFmt[@w:val="{type}"]'
                ']/@w:abstractNumId'
            ).format(type=t, **xpath_options[prefer_single])

        def get_abstract_id(numbering):
            for fn in (style_xpath, type_xpath):
                for prefer_single in (True, False):
                    xp = fn(prefer_single)
                    ids = numbering.xpath(xp)
                    if ids:
                        return min(int(x) for x in ids)
            return 0

        if (prev is None or
                prev._p.pPr is None or
                prev._p.pPr.numPr is None or
                prev._p.pPr.numPr.numId is None):
            if level is None:
                level = 0
            numbering = self.doc.part.numbering_part.numbering_definitions._numbering
            anum = get_abstract_id(numbering)
            num = numbering.add_num(anum)
            num.add_lvlOverride(ilvl=level).add_startOverride(1)
            num_id = num.numId
        else:
            if level is None:
                level = prev._p.pPr.numPr.ilvl.val
            num_id = prev._p.pPr.numPr.numId.val

        ppr = par._p.get_or_add_pPr()
        numPr = ppr.get_or_add_numPr()
        numPr.get_or_add_numId().val = num_id
        numPr.get_or_add_ilvl().val = level

    def add_input_cell(self):
        """Render single-cell table for opened input"""
        table = self.doc.add_table(rows=1, cols=1)
        set_table_borders(table)

    # -- poll-specific rendering -----------------------------------------

    def process_block(self, block: Block) -> None:
        # page break for visual
        self.doc.add_page_break()
        self.add_block_header(block.name.upper())

        if block.description:
            self.doc.add_paragraph(BlockNames.description.value, style=SUPPORT_STYLE_NAME)
            self.add_styled_html_paragraph(block.description)

        if block.title:
            self.doc.add_paragraph(BlockNames.header.value, style=SUPPORT_STYLE_NAME)
            self.add_styled_html_paragraph(block.title)

    def process_question(self, question: Question) -> None:
        question_p = self.add_styled_html_paragraph(question.title)
        question_p.style = self.doc.styles["List Number"]

        # add technical info
        tech_str = [ANSWER_TYPES_LABELS.get(question.type_id, question.type_id.name)]

        if question.max_answer > 1:
            tech_str.append(QuestionSpecs.max_answers.value.format(x=question.max_answer))
        if question.optional:
            tech_str.append(QuestionSpecs.optional.value)
        if question.randomized:
            tech_str.append(QuestionSpecs.randomized.value)
        if question.children_randomized:
            tech_str.append(QuestionSpecs.children_randomized.value)

        full_support = ".\n".join(tech_str) + "."
        self.doc.add_paragraph(full_support, style=SUPPORT_STYLE_NAME)

    def process_answers(self, answers: List[Answer]) -> None:
        prev = None
        for answer in answers:
            answer_paragraph = self.add_styled_html_paragraph(answer.title)
            answer_paragraph.style = self.doc.styles["List Number 2"]
            self.list_number(answer_paragraph, prev)
            prev = answer_paragraph

            answer_str = []
            if answer.skip_randomize:
                answer_str.append(AnswerSpec.skip_randomize.value)
            if answer.exclude_answer:
                answer_str.append(AnswerSpec.exclude.value)
            if answer.has_input:
                answer_str.append(AnswerSpec.has_input.value)
            if answer.input_validation:  # InputValidations.none == "" is falsy
                answer_str.append(AnswerSpec.input_validation.value)

            if answer_str:
                full_support = " " + ". ".join(answer_str) + "."
                answer_paragraph.add_run(full_support, style=SUPPORT_STYLE_NAME_CHARACTER)

            if display_answers := answer.display_answers:
                display_logic = " " + self.process_display_answers(display_answers=display_answers)
                answer_paragraph.add_run(display_logic, style=SUPPORT_STYLE_NAME_CHARACTER)

    def _add_html_paragraph_to_cell(self, html: str, cell, merge_paragraphs: bool = True) -> Paragraph:
        """Render ``html`` into a table cell and return the last paragraph produced."""
        if merge_paragraphs:
            html = replace_paragraphs_with_breaks(html)
        self.parser.add_html_to_cell(html, cell)
        return cell.paragraphs[-1]

    def add_styled_html_cell(self, html: str, cell) -> Paragraph:
        p = self._add_html_paragraph_to_cell(html, cell, merge_paragraphs=True)
        return self.set_default_style(paragraph=p)

    def set_fixed_layout(self, table: Table) -> None:
        """Force fixed column widths (otherwise Word ignores cell/column widths)."""
        tbl_pr = table._tbl.tblPr
        layout = OxmlElement('w:tblLayout')
        layout.set(qn('w:type'), 'fixed')
        tbl_pr.append(layout)

    def set_column_widths(self, table: Table, widths: List) -> None:
        """
        widths: list of Cm/Inches/Emu values, one per column.
        Must set width on the table.columns AND on every cell in each column,
        or Word will ignore it.
        """
        self.set_fixed_layout(table)
        for col_idx, width in enumerate(widths):
            table.columns[col_idx].width = width
            for row in table.rows:
                row.cells[col_idx].width = width

    def insert_grid(self, question: Question) -> None:
        """
        Render a matrix/table question (one row per child sub-question, one
        column per answer option) as a docx table. The body cells show a
        plain numbered scale (1, 2, 3, ...) repeated in every row, as a
        print-friendly stand-in for the pick-one-per-row control.
        """
        if not question.children or not question.answers:
            raise ValueError(
                f"insert_grid requires both children (rows) and answers (columns); "
                f"question {question.id} has children={bool(question.children)}, "
                f"answers={bool(question.answers)}"
            )

        x, y = len(question.children), len(question.answers)
        table = self.doc.add_table(rows=x + 1, cols=y + 1)

        # Header row
        header = table.rows[0].cells
        for cell, answer in zip(header[1:], question.answers):
            self.add_styled_html_cell(answer.title, cell)

        # index column
        index_cells = table.columns[0].cells
        for cell, child in zip(index_cells[1:], question.children):
            self.add_styled_html_cell(child.title, cell)

        # column widths: first column = 2 units, rest = 1 unit each
        total_width = Pt(432)  # ~6in of usable width on a Letter/A4 page with 1in margins
        unit = int(total_width / (y + 2))
        widths = [unit * 2] + [unit] * y
        self.set_column_widths(table, widths)

        # body cells: repeat the 1..y scale marker in every row
        values = [str(i) for i in range(1, y + 1)]
        for row_i in range(1, x + 1):
            row = table.rows[row_i].cells
            for cell, value in zip(row[1:], values):
                self.add_styled_html_cell(value, cell)

    def verbose_logics(
            self,
            logics: List[Display | DisplayAnswers | Jump],
            sep: str = ".\n",
            **kwargs
    ) -> str:
        """
        Render a list of logic rules as ``"{template}, если {condition}"``
        sentences joined by their join-condition word (И/ИЛИ), e.g.
        ``"Вопрос будет показан, если A ИЛИ Вопрос будет показан, если B"``.

        NOTE: `Jump` is accepted by the type hint, but `Jump.human_display()`
        (inherited from Logic, unmodified) currently raises `KeyError` -
        its `_str_template` placeholders don't match what human_display()
        fills in (see logic.py). Don't pass real Jump instances here until
        that's fixed.
        """

        result = []
        for rule in logics:
            result.append(rule.human_readable())
            result.append(JOIN_CONDITION_TO_STR.get(rule.join_condition_id))

        return sep.join(result[:-1])  # drop the trailing join condition

    def process_displays(self, displays: List[Display]) -> None:
        txt = self.verbose_logics(logics=displays)
        self.doc.add_paragraph(txt, style=SUPPORT_STYLE_NAME)

    def process_jumps(self, jumps: List[Jump]) -> None:
        txt = self.verbose_logics(logics=jumps)
        self.doc.add_paragraph(txt, style=SUPPORT_STYLE_NAME)

    def process_display_answers(self, display_answers: List[DisplayAnswers]) -> str:
        return self.verbose_logics(logics=display_answers, sep=' ')


def export_docx(poll: Poll, file_path: str) -> None:
    """Render ``poll`` as a formatted .docx spec document and save it to ``file_path``."""
    ext_document = ExtendedDocument()
    document = ext_document.doc

    # initial stuff
    ext_document.configure_default_style()
    ext_document.configure_support_style()
    ext_document.configure_support_character_style()
    ext_document.modify_heading_style()
    ext_document.format_numberings()

    ext_document.set_title(poll.name.upper())
    ext_document.add_footer(poll.name)
    ext_document.set_description(poll.description)

    for block in poll.blocks:
        ext_document.process_block(block=block)

        for question in block.questions:
            ext_document.process_question(question=question)

            # logics --------------------------------------------------------
            if question.displays:
                ext_document.process_displays(question.displays)
            if question.jumps:
                ext_document.process_jumps(question.jumps)


            # add answers if needed
            match question.type_id:
                case AnswerTypes.info_material:
                    pass
                case AnswerTypes.open_question | AnswerTypes.email_request:
                    ext_document.add_input_cell()
                case AnswerTypes.single_answer_per_row | AnswerTypes.multiple_choice_per_row:
                    ext_document.insert_grid(question)
                case _:
                    ext_document.process_answers(answers=question.answers or [])

    document.save(file_path)


def iter_blocks(parent):
    """Yield Paragraph and Table objects in document order."""
    container = parent._tc if isinstance(parent, _Cell) else parent.element.body
    for child in container.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, parent)
        elif child.tag == qn("w:tbl"):
            yield Table(child, parent)


def iter_cells(table):
    """Yield every real cell of a table, exactly once, row by row."""
    for tr in table._tbl.iterchildren(qn("w:tr")):
        for tc in tr.iterchildren(qn("w:tc")):
            vmerge = tc.xpath("./w:tcPr/w:vMerge")
            # vMerge without val="restart" = continuation of a cell above -> skip
            if vmerge and vmerge[0].get(qn("w:val")) != "restart":
                continue
            yield _Cell(tc, table)


def process_cell(cell, result):
    paras, nested = [], []
    for block in iter_blocks(cell):
        if isinstance(block, Paragraph):
            paras.append(paragraph_to_md(block))
        else:
            nested.append(block)
    result.append("\n".join(paras))
    for t in nested:                       # tables inside a cell
        for c in iter_cells(t):
            process_cell(c, result)


def style_attr(para, attr):
    """Look up a font attribute through the paragraph style chain."""
    style = para.style
    while style is not None:
        value = getattr(style.font, attr)
        if value is not None:
            return value
        style = style.base_style
    return None


def run_format(run, para):
    f = run.font
    color = None
    if f.color is not None and f.color.type == MSO_COLOR_TYPE.RGB:
        color = str(f.color.rgb)
    size = f.size or style_attr(para, "size")
    bold = f.bold if f.bold is not None else style_attr(para, "bold")
    italic = f.italic if f.italic is not None else style_attr(para, "italic")
    return (
        bool(bold),
        bool(italic),
        bool(f.underline),
        bool(f.strike),
        color,
        size.pt if size else None,
        f.highlight_color is not None,
    )


def wrap(text, fmt):
    bold, italic, underline, strike, color, size, highlight = fmt
    if not text.strip():
        return text
    # keep surrounding spaces outside the markers (Markdown requires this)
    lead = text[: len(text) - len(text.lstrip())]
    trail = text[len(text.rstrip()):]
    core = text.strip()

    if bold and italic:
        core = f"***{core}***"
    elif bold:
        core = f"**{core}**"
    elif italic:
        core = f"*{core}*"
    if strike:
        core = f"~~{core}~~"
    if underline:
        core = f"<u>{core}</u>"
    if highlight:
        core = f"<mark>{core}</mark>"

    css = []
    if color:
        css.append(f"color:#{color}")
    if size:
        css.append(f"font-size:{size:g}pt")
    if css:
        core = f'<span style="{"; ".join(css)}">{core}</span>'
    return lead + core + trail


def paragraph_to_md(para):
    # merge adjacent runs with identical formatting -> no "**a****b**"
    runs = [(run_format(r, para), r.text) for r in para.runs]
    parts = []
    for fmt, group in groupby(runs, key=lambda x: x[0]):
        parts.append(wrap("".join(t for _, t in group), fmt))
    text = "".join(parts)

    name = para.style.name if para.style is not None else ""
    if name.startswith("Heading ") and name[8:].isdigit():
        text = "#" * int(name[8:]) + " " + text
    elif name == "Title":
        text = "# " + text
    elif "List" in name and text.strip():
        text = "- " + text
    return text


def docx_to_markdown(path):
    doc = Document(path)
    result = []

    for block in iter_blocks(doc):
        if isinstance(block, Paragraph):
            result.append(paragraph_to_md(block))
        else:
            for cell in iter_cells(block):
                process_cell(cell, result)
    return result


# our own inline tags (produced by the docx converter) must not be escaped
TAG_RE = re.compile(r"(</?(?:span|u|mark)\b[^>]*>)")


def md_to_html(text: str) -> str:
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