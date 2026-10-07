import pytest
from socapi import *
from socapi.resources.pages import PageType

def make():
    return Poll(name="t", user_id=1, type_id=PollType.BY_BLOCK)

def test_flow():
    poll = make()
    finish = poll.add_page(name="Спасибо", type_id="finish", title=None)
    assert finish.type_id is PageType.FINISH and finish.data.title == "" and finish.id < 0
    with pytest.raises(ValueError): poll.add_page(name="x", type_id="finish")
    with pytest.raises(ValueError): poll.add_page(name="x")
    with pytest.raises(ValueError): poll.add_page(name="x", type_id="bogus")
    with pytest.raises(ValueError): poll.add_page(finish, name="x")

    b = poll.add_block(name="b1", title="T")
    q1 = b.add_question(title="Q1", type_id="single_answer",
                        answers=["a", "b", Answer(title="other", has_input=True)], optional=True)
    q2 = b.add_question(title="Q2", type_id=AnswerTypes.multiple_choice, answers=["x", "y"])
    m = b.add_question(title="M", type_id="single_answer_per_row", answers=["1", "2"], rows=["r1", "r2"])
    assert [a.order for a in q1.answers] == [1, 2, 3] and q1.optional
    assert all(a.id < 0 and a.question_id == q1.id for a in q1.answers)
    assert [c.id < 0 and c.parent_id == m.id for c in m.children] == [True, True]
    assert q2.poll_order == 2

    q2.add_display(q1, "is_selected", 2)
    q2.answers[0].add_display(q1, Comparator.is_selected, [1, 3])
    q1.add_jump(finish, "is_selected", 1)
    q1.add_jump(m, Comparator.is_answered)
    assert len(poll.displays) == 1 and len(poll.display_answers) == 1 and len(poll.jumps) == 2
    assert poll.jumps[0].target_page_id == finish.id
    assert q1.jumps and q2.displays
    poll.validate_draft()

    with pytest.raises(ValueError): q2.add_display(q1, "is_selected")          # no answer order
    with pytest.raises(ValueError): q2.add_display(q1, "is_selected", 9)       # no such answer
    with pytest.raises(ValueError): q2.add_display(q1, "nope", 1)
    with pytest.raises(TypeError): q1.add_jump("x", "is_answered")
    other = make(); ob = other.add_block(name="o"); oq = ob.add_question(title="O", type_id="single_answer", answers=["a"])
    with pytest.raises(ValueError): q2.add_display(oq, "is_selected", 1)
    with pytest.raises(ValueError): q1.add_jump(oq, "is_answered")
    with pytest.raises(ValueError): b.add_question(q1)                          # already attached
    with pytest.raises(ValueError): b.add_question(q1, title="x")
    with pytest.raises(ValueError): b.add_question(title="x")
    with pytest.raises(ValueError): poll.add_block(b)
    with pytest.raises(ValueError): poll.add_block(name="z", block=None) if False else poll.add_block()

def test_ready_objects_and_preset_questions():
    poll = make()
    blk = Block(name="b", questions=[Question(title="Q", type_id=AnswerTypes.single_answer, answers=[Answer(title="a")])])
    poll.add_block(blk)
    q = blk.questions[0]
    assert q.id < 0 and q._poll is poll and q.answers[0].id < 0 and q.block_id == blk.id
    assert poll.get_question_by_id(q.id) is q
    b2 = poll.add_block(Block(name="b2")); assert b2.order == 2
    pg = poll.add_page(Page(name="g", type_id=PageType.GREETING)); assert pg.poll_id is None and pg.dump_create_payload()["name"] == "g"
    q.add_jump(pg, "is_answered")
    poll.validate_draft()
