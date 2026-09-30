import unittest
from unittest.mock import patch
from langchain_core.documents import Document
from rag.chatbot import ask_llm, ABSTAIN, resolve_spans, validate_claims
from rag.retriever import route_regimes

class AccuracyTests(unittest.TestCase):
    def setUp(self):
        self.docs=[Document(page_content='The identifier is ALPHA. The archive stores identifiers.', metadata={'jurisdiction':'india'})]
    def claim(self,text):
        return {'claims':[{'text':text,'evidence':[{'source':1,'span':1}]}]}
    def test_background_only_answer_is_not_presented_as_answer(self):
        with patch('rag.chatbot.call_json',side_effect=[self.claim('The archive stores identifiers.'),{'supported':True,'answers_question':False,'repairable':False}]):
            self.assertIn(ABSTAIN,ask_llm('What is the identifier?',self.docs))
    def test_correctable_answer_gets_one_revision(self):
        with patch('rag.chatbot.call_json',side_effect=[self.claim('The identifier is BETA.'),{'supported':False,'answers_question':False,'repairable':True,'reason':'Use ALPHA, not BETA.'},self.claim('The identifier is ALPHA.'),{'supported':True,'answers_question':True}]) as call:
            answer=ask_llm('What is the identifier?',self.docs)
            self.assertIn('ALPHA',answer)
            self.assertNotIn('BETA',answer)
            self.assertEqual(call.call_count,4)
            self.assertIn('ALPHA',call.call_args_list[2].args[1]['revision_feedback'])
    def test_revision_is_bounded_and_still_fails_closed(self):
        bad={'supported':False,'answers_question':False,'repairable':True,'reason':'Incorrect identifier'}
        with patch('rag.chatbot.call_json',side_effect=[self.claim('BETA'),bad,self.claim('BETA'),bad]) as call:
            self.assertIn(ABSTAIN,ask_llm('What is the identifier?',self.docs))
            self.assertEqual(call.call_count,4)
    def test_malformed_reference_does_not_crash(self):
        result={'claims':[{'text':'bad','evidence':[{'reference':[]}]}]}
        self.assertEqual(validate_claims(resolve_spans(result,self.docs),self.docs),[])
    def test_patent_formulation_does_not_force_drug_sources(self):
        self.assertNotIn('drug_regulation',route_regimes('Can I patent a traditional Ayurvedic formulation?'))
        self.assertIn('drug_regulation',route_regimes('Does my patented formulation need drug approval?'))
    def test_gi_registry_route(self):
        self.assertIn('gi',route_regimes('What does the official GI registry say about Navara Rice?'))

    def test_label_position_does_not_spread_to_adjacent_requirement(self):
        from rag.chatbot import packaging_scope_errors
        claims=[{'text':'The front of the pack must display the logo and warning.', 'evidence':[{'quote':'The logo on the front of the pack.'},{'quote':'An advisory warning prominently written.'}]}]
        self.assertTrue(packaging_scope_errors(claims))
        claims[0]['text']='The label must carry a prominent warning.'
        self.assertEqual(packaging_scope_errors(claims),[])

    def test_statutory_tests_cannot_be_conflated(self):
        from rag.chatbot import statutory_scope_errors
        claims=[{'text':'Section 3(e) requires enhancement of efficacy.', 'evidence':[{'quote':'A mere admixture resulting only in aggregation of properties.'}]}]
        self.assertTrue(statutory_scope_errors(claims))
        claims[0]['text']='Section 3(e) excludes a mere admixture resulting only in aggregation of properties.'
        self.assertEqual(statutory_scope_errors(claims),[])
