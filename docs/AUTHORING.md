# Writing lesson content (pass A, pass B and pass C)

Claude writes all teaching content. This is the workflow and the draft format.

## Workflow for one deck (pass A)

1. `.venv\Scripts\python scripts\show_deck.py <deck_id>` prints every slide's text, notes and, for slides flagged `needs_visual`, the path of the slide picture. Open those pictures and read them.
2. Write a draft JSON (format below) in the scratchpad. Use only what is on the slides: their words, their examples, their numbers.
3. `.venv\Scripts\python -m athena.author <draft.json>` writes the topics, the examples catalog, `visual_text` and slide-kind fixes. It refuses to overwrite existing topics unless `--force` (only for topics never imported into the app).
4. Run `python -m athena.validate`, `python -m athena.grounding`, `python -m athena.coverage`. Fix every grounding failure in the draft and rebuild with `--force`, or mark the item `needs_check`.
5. When coverage shows 100% (or every gap is explained in `gaps`) set `pass_a: true` in `content/decks/<deck_id>/status.json`, tick the deck in PROGRESS.md and commit.

## Writing rules

- Plain, friendly English, like a sharp senior explaining the night before the exam. Short paragraphs, key terms in **bold**. No em dashes (validate rejects them).
- Every chunk, question, card and rubric point cites the slides it came from. A name or number in an item must be on a slide it cites (grounding checks this). If an MCQ distractor names something from another slide, cite that slide too.
- Never write "slide 15" in text (the number is not on the slide). Do not invent abbreviations the slide does not use.
- Numbers you compute from slide numbers (worked answers) go in the item's `derived` list.
- A `clar` (clarification) is allowed only for a term the slide names without explaining: at most 2 sentences, no names, no numbers. The app labels it "Not on slide".
- Topics: a coherent run of 3 to 10 slides. Chunks: 3 to 6 per topic. Check questions: 2 to 3 per chunk (mcq, tf, fill, oneline).

## Draft format

```json
{
  "deck_id": "aib--...", "subject_id": "aib", "short": "s2",
  "title": "Session 2: clean deck title in the professor's words (optional)",
  "kinds": {"1": "title", "19": "end"},
  "visual_text": {"4": "What the picture on slide 4 shows, in words."},
  "gaps": {"7": "Reason slide 7 is not taught (e.g. a video link only)."},
  "examples": [{"key": "haptik", "slide": 3, "label": "Haptik", "text": "...", "kind": "company"}],
  "topics": [{
    "slug": "what-is-ai", "title": "...", "summary": "...", "minutes": 20, "difficulty": 1,
    "chunks": [{
      "heading": "...", "refs": [2, 4], "examples": ["haptik"], "body": "markdown",
      "terms": [["Term", "Meaning", 4]], "exam": "Remember-for-the-exam line",
      "clar": ["term", "plain meaning"],
      "derived": ["0.24"],
      "checks": [
        {"type": "mcq", "q": "...", "options": ["A", "B", "C"], "a": "A", "refs": [4], "why": "optional"},
        {"type": "tf", "q": "...", "a": "True"},
        {"type": "fill", "q": "... ____ ...", "a": "word", "accept": ["other spelling"]}
      ]
    }],
    "cards": [["front", "back", [4], "term|list|example|fact|formula"]],
    "explain": {"prompt": "...", "points": [["rubric point", 4]]},
    "questions": [
      {"type": "long", "q": "...", "marks": 10, "difficulty": 2, "style": "explain",
       "model": "markdown model answer", "rubric": [["point", 4], ["point", 5]], "refs": [4, 5]}
    ]
  }]
}
```

Refs are slide numbers in this deck, or full `"<deck_id>#<n>"` strings for another deck. Ids are generated: topic `<subject>-<short>-<slug>`, chunk `<topic>-c<n>`, card `<topic>-f<n>`, question `<topic>-q-<hash of stem>`, example `<subject>-ex-<key>`.

## Pass C (teach it properly, per topic)

JasMehr's verdict on pass A lessons: "just words". Pass C adds a teaching layer to every chunk of a topic without touching ids, checks, cards or questions. Write a draft `{"subject_id": "be", "topics": {"<topic_id>": {"c1": {...}, "c2": {...}}}}` and run `python -m athena.author <file> --teach`. Only the keys given are replaced (derived numbers are added), so re-running is safe. Then run validate and grounding, look at every part in the app at desktop and phone width (pictures included), and commit.

Keys per chunk (all optional, but a taught chunk has at least `big_idea`, one visual or a worked example, `watch_out` and `exam_answer`):

- `big_idea`: the part in one plain sentence, as you would say it to a friend.
- `body`: replaces `explanation_md`. Short paragraphs, one idea each, plain words, **bold** the terms. Explain *why*, not only *what*. Write `P*` and `Q*` freely; for any other literal star write `\*` (in the JSON draft: `\\*`).
- `exam`: replaces `exam_line` (still used as the old-layout summary).
- `visuals`: a list of picture specs (docs/CONTENT_SCHEMA.md); `"ref": <slide>` sets `source_ref`. Redraw the slide's own graph with the slide's own numbers; when a slide has a graph, the lesson should have the drawn version. Use `compare` for "A vs B", `flow` for processes and cycles, `tree` for decision/probability trees and classifications, `matrix` for payoff tables and 2x2 grids, `normal` for z questions. Check that labels do not collide at phone width.
- `analogy`: one everyday comparison (at most 3 sentences, no names, no numbers above 10). Only when it truly helps.
- `worked`: `{"question": md, "steps": [{"title", "body", "why", "result"}], "answer": md}`. One move per step. Lay the working out in **columns** (a Markdown table) whenever there is more than one number: show where every number comes from. `why` is one plain sentence. `result` is the line to underline.
- `watch_out`: the 2 or 3 mistakes students actually make here (signs, wrong subtraction, wrong table column, mixing up two terms).
- `trick`: one short memory hook.
- `exam_answer`: the answer exactly as it should be written for full marks: definition in the slide's words, the formula, the working, the conclusion, and "(Draw ...)" where a diagram earns marks.
- `derived`: numbers you computed.

Never put the analogy inside `exam_answer`. Every number and name must be on the chunk's slides (or a visual's `ref`) or in `derived`.

## One-shot crash course (per subject, next exam first)

What JasMehr asked for on 8 Nov 2026: "give it everything, tell it how many hours I have, and it teaches me everything the paper comes from". One file, `content/crash/<subject>.json` (schema in docs/CONTENT_SCHEMA.md).

1. Read the subject's pattern, every past paper (transcribe new ones into `content/pyqs/<subject>.json`), and the decks the exam covers. Note which slide questions the papers reuse word for word (BE EST 2025 Q2 was Session 8's slide question).
2. Choose 10 to 15 sections in study order: what the latest papers test most comes first, with priority 1; mid-term material that may return is 2 or 3. Give each a realistic `minutes`.
3. Each section: `why` (the past-paper evidence), a one-line `big_idea`, a short `body_md`, at least one picture, the slide's own worked example as `worked`, practice from slide questions and past papers (`pyq_id`), `quiz_ids` from the bank where it exists, `watch_out`, `memory_trick`, `exam_answer_md`.
4. Compute every number in a script (tables, RMSE, NPV) instead of typing it, and list computed numbers in `derived`. Name slide arithmetic slips plainly.
5. If the paper can ask about topics with no slides in Athena, say so in `gaps_md`. Never fill the gap from outside the slides.
6. `formulas`: every formula the paper needs, one card each, with its slide. `last_hour`: 10 to 15 lines to read before walking in.
7. Run validate and grounding, open `#/crash/<subject>` at desktop and phone width with every part open, and commit.

## Pass B (question bank, per subject)

Write a question-bank draft `{"subject_id": "be", "topics": {"<topic_id>": [question, ...]}}` and run `python -m athena.author <file> --questions`. It replaces only the `questions` of those topics (re-running is safe) and leaves lessons, cards and ids alone. Questions use the check format plus `model`, `rubric` (`[["point", slide], ...]`), `marks`, `difficulty` (1 to 3), `style` and `derived`; slide refs are numbers in the topic's own deck. Per topic: about 5 MCQs, 3 short, 2 long, plus differentiate and case questions where the slides support them. Written questions need `model` (short intro, the points, the professor's example, short conclusion) and a `rubric`. Match the subject's style in `content/patterns/<subject>.json`.
