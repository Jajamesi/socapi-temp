from socapi import (
    ParserClient, Poll, PollType, Block, Question, Answer, AnswerTypes, ChildQuestion,
    Comparator, exceptions, Page
)
from socapi.resources.pages import PageType

from socapi.resources.questions import InputValidations
import socapi
import asyncio

import os
import dotenv
dotenv.load_dotenv("../tests/.env")

login=os.getenv("LOGIN", "")
password= os.getenv("PASSWORD", "")

poll = Poll(
    name='**--ТЕСТ АВТО ОПРОСА-- Анкета. Общая выборка**',
    description="Здравствуйте! Это исследование проводится с целью определения ключевых зон роста и решений по "
                "повышению качества жизни граждан в субъектах Российской Федерации. "
                "Просим Вас ответить на вопросы о населенном пункте и регионе Вашего проживания. "
                "Прохождение анкеты займет примерно 15-20 минут.\n"
                'Мы гарантируем анонимность и конфиденциальность Ваших ответов, '
                'анализируем данные только в обобщенном виде.',
    user_id=561,
    type_id=PollType.ONE_QUESTION,
    meta=[0]
)

start_page = poll.add_page(Page(
    name="Стартовая страница",
    type_id=PageType.GREETING
))
finish_page = poll.add_page(Page(
    name="Финальная страница",
    type_id=PageType.FINISH
))
disqualified_page = poll.add_page(Page(
    name="Страница дисквалицификации",
    type_id=PageType.DISQUALIFICATION
))

intro = poll.add_block(Block(name='**1 - ВВОДНЫЙ БЛОК**'))

first_info_screen = intro.add_question(Question(
    title='**Чтобы помочь классифицировать ответы и сделать их статистически сопоставимыми, просим ответить на несколько вопросов о Вас.**',
    type_id=AnswerTypes.info_material,
    min_answer=0
))

age = intro.add_question(Question(
    title='**Сколько Вам полных лет?**', type_id=AnswerTypes.single_answer,
    answers=[
        Answer(title='До 16 лет'),
        Answer(title="16-24", has_input=True, input_validation=InputValidations.number),
        Answer(title="25-59", has_input=True, input_validation=InputValidations.number),
        Answer(title='60 лет и старше (укажите)', has_input=True, input_validation=InputValidations.number),
    ],
))
age_filter = age.add_jump(
    target=disqualified_page,
    comparator=Comparator.IS_SELECTED,
    reference_answer_order=1
)


gender = intro.add_question(Question(
    title="gender", type_id=AnswerTypes.single_answer,
    answers=[Answer(title="m"), Answer(title="f")],
))
display_gender = gender.add_display(
    reference_question=age,
    comparator=Comparator.IS_SELECTED,
    reference_answer_order=1,
)




async def main():
    async with (socapi.ParserClient(login=login, password=password, host="online-sociology.ru") as client):
        new_poll = await client.poll.upload_poll(poll=poll, verbose=True)

    new_poll.to_json_file("./test.json")

asyncio.run(main())