"""Print a deck's slides compactly for a content pass.

Usage: .venv\\Scripts\\python scripts\\show_deck.py <deck_id> [first] [last]
Shows slide number, kind, needs_visual flag, title, text, notes, visual_text and
the render path (open it to look at the slide).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from athena import config, contentio  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    deck = contentio.load_deck(sys.argv[1])
    if deck is None:
        print(f"no deck {sys.argv[1]}")
        return 1
    first = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    last = int(sys.argv[3]) if len(sys.argv) > 3 else len(deck.slides)
    print(f"# {deck.id} | {deck.title} | {len(deck.slides)} slides | {deck.file}")
    for slide in deck.slides[first - 1:last]:
        flag = "VISUAL" if slide.needs_visual else ""
        print(f"\n--- #{slide.n} [{slide.kind}] {flag} {slide.title}")
        body = slide.text
        if slide.title and body.startswith(slide.title):
            body = body[len(slide.title):].strip()
        if body:
            print(body)
        if slide.notes:
            print(f"NOTES: {slide.notes}")
        if slide.visual_text:
            print(f"VISUAL_TEXT: {slide.visual_text}")
        if slide.needs_visual and slide.render:
            print(f"RENDER: {config.DATA_DIR / slide.render}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
