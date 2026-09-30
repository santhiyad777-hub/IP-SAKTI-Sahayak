"""Stop model-authored Markdown from auto-loading external tracking images."""
import re

def message_markdown(text):
    # Entities render as a literal exclamation mark, not an image token. This also
    # covers reference-style images, escaped syntax and nested image links.
    return re.sub(r'!(?=\[)', '&#33;', str(text))
