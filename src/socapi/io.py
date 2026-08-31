from typing import List, Optional, Type, TypeVar, TYPE_CHECKING, Dict
import orjson
from pydantic import BaseModel

from docx import Document
from docx.shared import RGBColor, Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.style import WD_STYLE_TYPE
from docx.text.paragraph import Paragraph
from docx.table import Table
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from html4docx import HtmlToDocx
from bs4 import BeautifulSoup
import re

if TYPE_CHECKING:
    from .resources.polls import Poll
    from .resources.blocks import Block
from .resources.logic import DisplayAnswers, Display, Jump, JOIN_CONDITION_TO_STR
from .resources.questions import AnswerTypes, Question, Answer, QuestionInclude

T = TypeVar("T", bound=BaseModel)

def to_json(self: BaseModel, file_path: str) -> None:
    with open(file_path, "wb") as f:
        f.write(orjson.dumps(
            self.model_dump(mode="json"),
            option=orjson.OPT_INDENT_2,
        )
        )


def from_json(cls: Type[T], file_path: str) -> T:
    with open(file_path, "rb") as f:
        data = orjson.loads(f.read())

    return cls.model_validate(data)



DEFAULT_STYLE_NAME = 'Arial 11'
SUPPORT_STYLE_NAME = 'Support'
SUPPORT_STYLE_NAME_CHARACTER = 'Support Character'
DEFAULT_FONT_NAME = 'Arial'
DEFAULT_FONT_SIZE = 11
DEFAULT_COLOR = RGBColor(0,0,0)
BLUE_COLOR = RGBColor(0,112,192)
BLOCK_HEADER_FILL_COLOR = 'D9EAF7'

ANSWER_TYPES_LABELS = {
    AnswerTypes.single_answer : 'Один ответ',
    AnswerTypes.dropdown : "Выпадающий список",
    AnswerTypes.single_answer_per_row : "Один ответ по строке",
    AnswerTypes.multiple_choice : "Множественный выбор",
    AnswerTypes.open_question : "Открытый вопрос",
    AnswerTypes.ranking : "Ранжирование",
    AnswerTypes.slider : "Ползунок",
    AnswerTypes.multiple_choice_per_row : "Множественный выбор по строке",
    AnswerTypes.info_material : "Ознакомительный материал",
    AnswerTypes.email_request : "Запрос почты"
}




def set_table_borders(table: Table):
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
    """
    document wrapper with styling actions
    """

    def __init__(self):
        self.doc = Document()
        self.parser = HtmlToDocx(default_paragraph_style=DEFAULT_STYLE_NAME)


    def configure_default_style(self):
        styles = self.doc.styles
        style = styles.add_style(DEFAULT_STYLE_NAME, WD_STYLE_TYPE.PARAGRAPH)

        # configure pafargraph format and spacings
        pf = style.paragraph_format
        pf.space_before = Pt(18)
        pf.space_after = Pt(0)
        pf.line_spacing = 1.0  # single spacing


        # Configure font
        font = style.font
        font.name = 'Arial'
        font.size = Pt(11)
        font.color.rgb = DEFAULT_COLOR

    def configure_support_style(self):
        styles = self.doc.styles
        style = styles.add_style(SUPPORT_STYLE_NAME, WD_STYLE_TYPE.PARAGRAPH)

        # Configure font
        font = style.font
        font.name = 'Arial'
        font.size = Pt(11)
        font.color.rgb = BLUE_COLOR
        font.italic = True

        # configure pafargraph format and spacings
        pf = style.paragraph_format
        pf.space_before = Pt(5)
        pf.space_after = Pt(0)
        pf.line_spacing = 1.0  # single spacing
        pf.left_indent = Pt(18)


    def configure_support_character_style(self):
        styles = self.doc.styles
        style = styles.add_style(SUPPORT_STYLE_NAME_CHARACTER, WD_STYLE_TYPE.CHARACTER)

        # Configure font
        font = style.font
        font.name = 'Arial'
        font.size = Pt(11)
        font.color.rgb = BLUE_COLOR
        font.italic = True


    def modify_heading_style(self):
        style = self.doc.styles["Heading 1"]

        # Configure font
        font = style.font
        font.name = 'Arial'
        font.size = Pt(11)
        font.color.rgb = DEFAULT_COLOR


    def format_numberings(self):
        # set styles for numerated list
        styles = self.doc.styles
        for style in ["List Number", "List Number 2"]:
            styles[style].font.name = DEFAULT_FONT_NAME

            # configure pafargraph format and spacings
            pf = styles[style].paragraph_format

            pf.space_after = Pt(0)
            pf.line_spacing = 1.0  # single spacing

        styles["List Number"].paragraph_format.space_before = Pt(18)
        styles["List Number 2"].paragraph_format.space_before = Pt(5)


    def add_footer(self, title: str):
        paragraph = self.doc.sections[0].footer.add_paragraph(title)
        run = paragraph.runs[0]
        run.font.name = DEFAULT_FONT_NAME
        run.font.size = Pt(DEFAULT_FONT_SIZE)


    def set_title(self, title: str):
        p = self.doc.add_heading(level=0)
        p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER

        run = p.add_run(title)
        run.font.name = DEFAULT_FONT_NAME
        run.font.size = Pt(DEFAULT_FONT_SIZE)
        run.font.color.rgb = DEFAULT_COLOR
        run.bold = True


    def _add_html_paragraph(self, html: str, merge_paragraphs: bool = True) -> Paragraph:
        """
        wrapper to return last paragraph
        :param html:
        :return:
        """
        if merge_paragraphs:
            html = replace_paragraphs_with_breaks(html)
        self.parser.add_html_to_document(html, self.doc)
        return self.doc.paragraphs[-1]



    def set_default_style(self, paragraph: Paragraph):
        for r in paragraph.runs:
            font = r.font
            font.name = DEFAULT_FONT_NAME
            font.size = Pt(DEFAULT_FONT_SIZE)
        return paragraph


    def add_styled_html_paragraph(self, html: str) -> Paragraph:
        p = self._add_html_paragraph(html, merge_paragraphs=True)
        p = self.set_default_style(paragraph=p)
        return p


    def set_description(self, description: str):
        """
        set description from html str and set.
        since description has severall paragrpahs (fragments), apply styling to all
        :param description:
        :return:
        """
        self.add_styled_html_paragraph(description)


    def add_block_header(self, block_title: str):
        head = self.doc.add_heading(block_title, level=1)

        head.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # Access paragraph properties
        p_pr = head._element.get_or_add_pPr()

        # Create shading element
        shd = OxmlElement('w:shd')
        shd.set(qn('w:fill'), BLOCK_HEADER_FILL_COLOR)  # Hex color without #

        # Apply shading
        p_pr.append(shd)



    def list_number(self, par, prev=None, level=None, numbered=True):
        """
        Workaround to reset list numbering.
        Call after creating new paragraph and pass previous numbered paragraph.
        If None as previous paragraph passed - numbering will be reset

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


    def process_block(self, block: Block):
        # page break for visual
        self.doc.add_page_break()
        self.add_block_header(block.name.upper())

        if block.description:
            self.doc.add_paragraph("Описание блока (видно респонденту):", style=SUPPORT_STYLE_NAME)
            self.add_styled_html_paragraph(block.description)

        if block.title:
            self.doc.add_paragraph("Заголовок блока (видно респонденту):", style=SUPPORT_STYLE_NAME)
            self.add_styled_html_paragraph(block.title)


    def process_question(self, question: Question):
        question_p = self.add_styled_html_paragraph(question.title)
        question_p.style = self.doc.styles["List Number"]

        # add technical info
        tech_str = []
        tech_str.append(ANSWER_TYPES_LABELS[question.type_id])

        if question.max_answer > 1:
            tech_str.append(f"Максимум ответов: {question.max_answer}")

        if question.optional:
            tech_str.append(f"Необязателен к ответу")

        if question.randomized:
            tech_str.append("Перемешивать ответы")

        if question.children_randomized:
            tech_str.append("Перемешивать подвопросы")

        full_support = ".\n".join(tech_str) + "."

        p = self.doc.add_paragraph(full_support, style=SUPPORT_STYLE_NAME)



    def process_answers(self, answers: List[Answer]):
        prev = None
        for answer in answers:
            answer_paragraph = self.add_styled_html_paragraph(answer.title)
            answer_paragraph.style = self.doc.styles["List Number 2"]
            self.list_number(answer_paragraph, prev)
            prev = answer_paragraph

            answer_str = []

            if answer.skip_randomize:
                answer_str.append("Не перемешивать")
            if answer.exclude_answer:
                answer_str.append("Исключающий ответ")
            if answer.has_input:
                answer_str.append("Поле для ввода")
            if answer.input_validation:
                answer_str.append("Маска")

            if answer_str:
                full_support = " " + ". ".join(answer_str) + "."
                answer_paragraph.add_run(full_support, style=SUPPORT_STYLE_NAME_CHARACTER)

    def _add_html_paragraph_to_cell(self, html: str, cell, merge_paragraphs: bool = True) -> Paragraph:
        """
        wrapper to add html content into a table cell, returns last paragraph in the cell
        """
        if merge_paragraphs:
            html = replace_paragraphs_with_breaks(html)
        self.parser.add_html_to_cell(html, cell)
        return cell.paragraphs[-1]

    def add_styled_html_cell(self, html: str, cell) -> Paragraph:
        p = self._add_html_paragraph_to_cell(html, cell, merge_paragraphs=True)
        p = self.set_default_style(paragraph=p)
        return p

    def set_fixed_layout(self, table: Table):
        """Force fixed column widths (otherwise Word ignores cell/column widths)."""
        tbl_pr = table._tbl.tblPr
        layout = OxmlElement('w:tblLayout')
        layout.set(qn('w:type'), 'fixed')
        tbl_pr.append(layout)

    def set_column_widths(self, table: Table, widths: List):
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

    def insert_grid(self, question: Question):
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
        total_width = Pt(432)
        unit = int(total_width / (y + 2))
        widths = [unit * 2] + [unit] * y
        self.set_column_widths(table, widths)

        # values
        values = [str(i) for i in range(1, y+1)]
        for row_i in range(1, x+1):
            row = table.rows[row_i].cells
            for cell, value in zip(row[1:], values):
                self.add_styled_html_cell(value, cell)

    def process_display(self, display: Display):
        pass

    def process_displays(self, displays: List[Display]):
        result = []
        for d in displays:
            result.append(f"Вопрос будет показан, если {d.human_display()}")
            result.append(JOIN_CONDITION_TO_STR.get(d.join_condition_id))

        full_support = ".\n".join(result[:-1]) # drop last join condition

        p = self.doc.add_paragraph(full_support, style=SUPPORT_STYLE_NAME)

    def process_jump(self, question: Question, question_mapper: Dict[int, str], answer_mapper: Dict[int, str]):
        pass
        template = "Если {conditions} переход на {tartet_type} {target}."
        # template_condition =
        tmplate_start = "Если"
        teplate_target = "переход на {target_} Финальная страница."





def export_docx(poll: Poll, file_path: str) -> None:
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
            if question.displays:
                ext_document.process_displays(question.displays)

            # for jump in question.jumps:
            #     ext_document.process_jump(jump, question_mapper=question_mapper, answer_mapper=answer_mapper)

            # add answers if needed
            match question.type_id:
                case AnswerTypes.info_material:
                    pass
                case  AnswerTypes.open_question | AnswerTypes.email_request:
                    table = document.add_table(rows=1, cols=1)
                    set_table_borders(table)
                case AnswerTypes.single_answer_per_row | AnswerTypes.multiple_choice_per_row:
                    ext_document.insert_grid(question)
                case _:
                    ext_document.process_answers(question.answers)

    document.save(file_path)