# Content schema

All generated content lives in `content/` as JSON and is committed. The Pydantic models in `athena/models.py` are the exact contract; this file explains them. `python -m athena.validate` checks every file against the models.

## IDs

- Lowercase slugs: `a-z`, `0-9`, single `-` or `.` between parts.
- Subject: short slug, for example `qtm`, `mm`, `far`.
- Deck: `<subject-id>--<file-slug>`, for example `qtm--module-3`. The only place `--` appears.
- Topic: `<subject-id>-<deck-short>-<topic-slug>`, unique across all subjects.
- Chunk: `<topic-id>-c<n>`. Flashcard: `<topic-id>-f<n>`.
- Question: `<topic-id>-q-<8 char sha1 of the normalized stem>` (see `models.question_id`). Check questions use the same rule.
- Example: `<subject-id>-ex-<slug>`. Framework: `<subject-id>-fw-<slug>`. Link: `link-<slug>`.
- **Never rename an ID once written.** Set `retired: true` and add a new item instead. JasMehr's progress in SQLite points at these IDs.

## Source refs

Every teaching item carries `source_refs`, a list of `"<deck_id>#<slide number>"` strings (slide numbers start at 1; for PDF decks the page number). `validate` checks each ref points at a real slide.

## Files

### `content/subjects.json`
List of `{id, name, short_name, code, aliases[], color, deck_ids[], faculty}`. `aliases` are lowercase strings used to map Classroom course names and folder names to the subject.

### `content/decks/<deck_id>/deck.json`
Written by `python -m athena.ingest`, then enriched by Claude (only `visual_text` is hand-written).

```
{id, subject_id, file (absolute source path), source: college|inbox|fixture,
 file_type: pptx|pdf|ppt|odp, sha256, title, order, duplicates[], ingested_at,
 slides: [{n, kind: content|title|agenda|end|blank, title, text,
           bullets[{level, text}], tables[[[cell]]], notes, charts[{title, chart_type,
           categories[], series[{name, values[]}]}], visual_text, images[] (paths under data/),
           render (page image under data/, or null), needs_visual, word_count}]}
```

`needs_visual` is true when a content slide has under 25 words, or carries a chart, table-as-picture, diagram or picture. Claude looks at the rendered image and writes what it shows into `visual_text`. Grounding treats `visual_text` as slide text.

`content/decks/<deck_id>/status.json` (written by Claude): `{pass_a, pass_b, verified, coverage_note}`.

### `content/topics/<subject_id>/<topic_id>.json`

```
{id, subject_id, deck_id, title, order, summary, est_minutes (5-240), difficulty (1-3),
 source_refs[], stale, retired,
 chunks: [{id, heading, explanation_md, example_ids[], key_terms[{term, meaning, source_ref}],
           exam_line, clarification: {term, text} | null, check_questions[Question],
           source_refs[], needs_check, retired}],
 flashcards: [{id, front, back, kind: term|list|example|fact|formula, source_refs[], needs_check, retired}],
 questions: [Question],
 explain_back: {prompt, rubric[{point, source_ref}]} | null,
 framework_ids[], link_ids[], video_ids[]}
```

**Question** (used for chunk checks and the question bank):

```
{id, type: mcq|true_false|fill|one_line|short|long|differentiate|case,
 stem, options[], answer, accept[] (other accepted answers for fill/one_line),
 explanation, model_answer_md, rubric[{point, source_ref}], marks, difficulty (1-3),
 style_tag, source_refs[], needs_check, retired}
```

- `mcq`: at least 3 distinct options; `answer` equals one option exactly.
- `true_false`: `answer` is `"True"` or `"False"`.
- `fill`, `one_line`: `answer` required; matching ignores case, spaces and punctuation, and also accepts anything in `accept`.
- `short`, `long`, `differentiate`, `case`: `model_answer_md` and a rubric of at least 2 points required. Model answers follow MBA exam shape: short intro, the points, the professor's example, short conclusion. Never contain clarification text.

`clarification` is the one narrow exception to "slides only": at most 2 sentences giving the plain meaning of a term the slide names without explaining. No names, no numbers, no examples. The app labels it "Not on slide".

Items with `needs_check: true` are hidden from lessons and quizzes.

### `content/examples/<subject_id>.json`
List of `{id, deck_id, slide, label, text, kind: company|case|numeric|scenario|illustration|person|product, taught_in[chunk ids], needs_check, retired}`. Every example in a deck appears here and is taught in at least one chunk.

### `content/frameworks.json`
List of `{id, subject_id, name, description, parts[{name, text}], example_ids[], topic_ids[], source_refs[], retired}`. Only frameworks, models and matrices that appear in the slides.

### `content/links.json`
List of `{id, concept, note, a{subject_id, topic_id, source_ref}, b{...}, retired}`: the same concept in two subjects' slides.

### `content/exams.json`
List of `{subject_id, date (YYYY-MM-DD), time, type (MST, EST, quiz), note}`. Settings in the app can override these.

### `content/pyqs/<subject_id>.json`
List of `{id, subject_id, year, exam, q_no, marks, text, co, bt, topic_ids[], in_slides, note}`.

### `content/patterns/<subject_id>.json`
`{subject_id, summary, paper_format, total_marks, duration, question_verbs[], marks_structure[], repeated_topics[], sources[]}`.

### `content/syllabus/<subject_id>.json`
`{subject_id, course_code, title, source_file, faculty[], modules[], evaluation[], sessions[{n, topic, module, deck_ids[], has_ppt}], note}`.

### `content/videos.json`
List of `{id, topic_id, title, url, channel, duration_s}`. Labelled "Extra help, not exam source" in the app.

### `content/feedback/<answer_id>.json`
Written by refresh sessions: `{id, answer_id, kind: explain_back|written, topic_id, question_id, graded_at, score, max_score, points_hit[], points_missed[], feedback_md, source_refs[]}`.
