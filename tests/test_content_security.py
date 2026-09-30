import unittest
from markdown_it import MarkdownIt
from security.content import message_markdown

class ContentSecurityTests(unittest.TestCase):
    def test_external_markdown_images_never_auto_load(self):
        parser=MarkdownIt()
        for text in ['![secret](https://attacker.example/x)', '![x][id]\n\n[id]: https://attacker.example/x', r'\\![x](https://attacker.example/x)', '[![x](https://attacker.example/x)](https://example.org)']:
            self.assertNotIn('<img',parser.render(message_markdown(text)))
    def test_citations_and_plain_text_are_preserved(self):
        text='A source: [1](https://official.example/law). Hello!'
        self.assertEqual(message_markdown(text),text)
