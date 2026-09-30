import unittest
from unittest.mock import patch
from rag.conversation import necessary_followup, respond

class SelectiveClarificationTests(unittest.TestCase):
    def test_general_questions_are_direct(self):
        for q in ['What are ABS compliance requirements?', 'Explain export requirements', 'When is Form III required?', 'What labelling requirements apply to Ayurveda Aahara products?', 'Can I patent a traditional Ayurvedic formulation?', 'How does the Budapest Treaty help?']:
            with self.subTest(q=q): self.assertEqual(necessary_followup(q),'')
    def test_missing_material_facts_trigger_question(self):
        for q in ['I want to export my herbal product abroad', 'Can I patent my formulation?', 'Does Section 3(e) apply to my invention?', 'Do I need ABS approval for my product?']:
            with self.subTest(q=q): self.assertTrue(necessary_followup(q))
    def test_supplied_facts_not_requested_again(self):
        for q in ['I want to export my herbal product to Singapore', 'Can I patent my new extraction method?', 'Do I need ABS for neem sourced in India for commercial use?']:
            with self.subTest(q=q): self.assertEqual(necessary_followup(q),'')
    def test_clarification_reply_reaches_answer_with_original_question(self):
        with patch('rag.conversation.prepare_query',side_effect=lambda q,*a,**kw:q), patch('rag.conversation.retrieve_documents',return_value=[]), patch('rag.conversation.ask_llm',return_value='Grounded response') as ask:
            first=respond('I want to export my herbal product abroad',answer_language='English')
            self.assertIn('Which country',first['answer'])
            ask.assert_not_called()
            second=respond('Singapore',cache=first['cache'],answer_language='English')
            self.assertEqual(second['answer'],'Grounded response')
            self.assertIn('User clarification: Singapore',ask.call_args.args[0])
    def test_full_classification_details_do_not_trigger_intake(self):
        from rag.chatbot import classification_questions
        self.assertEqual(classification_questions('Classify my product. Intended use: skin moisturising. Route: topical. Claim: moisturises skin.','india'),[])
