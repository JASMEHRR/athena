"""Build a small, valid content set inside the test environment."""

from __future__ import annotations

from athena import contentio
from athena.models import (
    Bullet,
    Chunk,
    Deck,
    Example,
    ExplainBack,
    Flashcard,
    KeyTerm,
    Question,
    RubricPoint,
    Slide,
    Topic,
    question_id,
)

DECK_ID = "mm--session-9"
TOPIC_ID = "mm-s9-pricing"


def slide(n: int, title: str, lines: list[str], kind: str = "content") -> Slide:
    text = "\n".join([title, *lines])
    return Slide(n=n, kind=kind, title=title, text=text,
                 bullets=[Bullet(level=0, text=line) for line in lines], word_count=len(text.split()))


def make_deck() -> Deck:
    return Deck(
        id=DECK_ID,
        subject_id="mm",
        file="C:/college/MM/Session 9.pdf",
        sha256="0" * 64,
        title="Pricing",
        order=1,
        slides=[
            slide(1, "Pricing Strategies", ["Dr. Test"], kind="title"),
            slide(2, "Penetration Pricing", ["Low price to win market share fast",
                                            "Example: Jio entered in 2016 with free data"]),
            slide(3, "Skimming Pricing", ["High launch price, lowered later",
                                         "Example: Apple prices new iPhones at 79,900"]),
            slide(4, "Price Elasticity", ["Elastic demand: change in price causes a bigger change in quantity",
                                         "Elasticity of 1.8 for cars"]),
            slide(5, "Thank you", [], kind="end"),
        ],
    )


def mcq(stem: str, options: list[str], answer: str, refs: list[str], **kw) -> Question:
    return Question(id=question_id(TOPIC_ID, stem), type="mcq", stem=stem, options=options,
                    answer=answer, source_refs=refs, **kw)


def make_topic() -> Topic:
    c1 = Chunk(
        id=f"{TOPIC_ID}-c1",
        heading="Penetration pricing",
        explanation_md="Set a **low price** to win share fast. Jio did this in 2016 with free data.",
        example_ids=["mm-ex-jio"],
        key_terms=[KeyTerm(term="Penetration pricing", meaning="Low price to win market share fast",
                           source_ref=f"{DECK_ID}#2")],
        exam_line="Penetration pricing means a low price to win share.",
        check_questions=[mcq("Which company entered with free data?", ["Jio", "Apple", "Neither"], "Jio",
                             [f"{DECK_ID}#2", f"{DECK_ID}#3"])],
        source_refs=[f"{DECK_ID}#2"],
    )
    c2 = Chunk(
        id=f"{TOPIC_ID}-c2",
        heading="Skimming pricing",
        explanation_md="Start high, then lower the price later. Apple prices new iPhones at 79,900. "
                       "A firm can set a low or high start depending on the goal.",
        example_ids=["mm-ex-apple"],
        check_questions=[mcq("Skimming starts with a price that is?", ["High", "Low", "Free"], "High",
                             [f"{DECK_ID}#3"])],
        source_refs=[f"{DECK_ID}#3"],
    )
    long_q = Question(
        id=question_id(TOPIC_ID, "Differentiate penetration and skimming pricing."),
        type="differentiate",
        stem="Differentiate penetration and skimming pricing.",
        model_answer_md="Penetration uses a low price (Jio, 2016). Skimming starts high (Apple).",
        rubric=[RubricPoint(point="Penetration: low price for share", source_ref=f"{DECK_ID}#2"),
                RubricPoint(point="Skimming: high launch price", source_ref=f"{DECK_ID}#3")],
        marks=5,
        difficulty=2,
        source_refs=[f"{DECK_ID}#2", f"{DECK_ID}#3"],
    )
    return Topic(
        id=TOPIC_ID,
        subject_id="mm",
        deck_id=DECK_ID,
        title="Pricing strategies",
        source_refs=[f"{DECK_ID}#2", f"{DECK_ID}#3"],
        chunks=[c1, c2],
        flashcards=[Flashcard(id=f"{TOPIC_ID}-f1", front="Penetration pricing", back="Low price to win share fast",
                              source_refs=[f"{DECK_ID}#2"])],
        questions=[long_q],
        explain_back=ExplainBack(
            prompt="Explain the two pricing strategies.",
            rubric=[RubricPoint(point="Low price to win share", source_ref=f"{DECK_ID}#2"),
                    RubricPoint(point="High launch price lowered later", source_ref=f"{DECK_ID}#3")],
        ),
    )


def make_examples() -> list[Example]:
    return [
        Example(id="mm-ex-jio", deck_id=DECK_ID, slide=2, label="Jio free data",
                text="Jio entered in 2016 with free data", kind="company", taught_in=[f"{TOPIC_ID}-c1"]),
        Example(id="mm-ex-apple", deck_id=DECK_ID, slide=3, label="Apple iPhone pricing",
                text="Apple prices new iPhones at 79,900", kind="company", taught_in=[f"{TOPIC_ID}-c2"]),
    ]


def write_all(deck: Deck | None = None, topic: Topic | None = None, examples: list[Example] | None = None) -> None:
    contentio.save_deck(deck or make_deck())
    contentio.save_topic(topic or make_topic())
    contentio.save_examples("mm", examples if examples is not None else make_examples())
