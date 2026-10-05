# Writing lesson content (pass A and pass B)

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

## Pass B (question bank, per subject)

Add `questions` to existing topics by editing the topic JSON directly (or a draft with `--force` before the topic is ever imported). Per topic: about 5 MCQs, 3 short, 2 long, plus differentiate and case questions where the slides support them. Written questions need `model` (short intro, the points, the professor's example, short conclusion) and a `rubric`. Match the subject's style in `content/patterns/<subject>.json`.
