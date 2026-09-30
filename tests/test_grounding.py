import unittest
from unittest.mock import patch
from langchain_core.documents import Document
from rag.chatbot import ask_llm,validate_claims,citation,ABSTAIN,classification_questions
from rag.retriever import bm25
class GroundingTests(unittest.TestCase):
    def setUp(self):
        self.docs=[Document(page_content='This isolated test document says the sample identifier is ALPHA.',metadata={'page':0,'jurisdiction':'india','title':'Test fixture'})]
    def test_empty_evidence_never_calls_model(self):
        with patch('rag.chatbot.call_json') as call:
            self.assertIn(ABSTAIN,ask_llm('What is the sample?',[])); call.assert_not_called()
    def test_wrong_jurisdiction_never_calls_model(self):
        with patch('rag.chatbot.call_json') as call:
            self.assertIn(ABSTAIN,ask_llm('What is the sample?',self.docs,jurisdiction='international')); call.assert_not_called()
    def test_fabricated_quote_rejected(self):
        data={'claims':[{'text':'It is BETA.','evidence':[{'source':1,'quote':'The sample identifier is BETA.'}]}]}
        self.assertEqual([],validate_claims(data,self.docs))
    def test_nonexistent_source_rejected(self):
        data={'claims':[{'text':'It is ALPHA.','evidence':[{'source':9,'quote':self.docs[0].page_content}]}]}
        self.assertEqual([],validate_claims(data,self.docs))
    def test_exact_quote_not_enough_when_auditor_rejects(self):
        data={'claims':[{'text':'The identifier is BETA.','evidence':[{'source':1,'quote':self.docs[0].page_content}]}]}
        with patch('rag.chatbot.call_json',side_effect=[data,{'supported':False}]):
            self.assertIn(ABSTAIN,ask_llm('What is the sample?',self.docs))
    def test_supported_claim_gets_deterministic_page_citation(self):
        data={'claims':[{'text':'The identifier is ALPHA.','evidence':[{'source':1,'quote':self.docs[0].page_content}]}]}
        with patch('rag.chatbot.call_json',side_effect=[data,{'supported':True}]):
            answer=ask_llm('What is the sample?',self.docs)
            self.assertIn('PDF page: 1',answer); self.assertIn('[1]',answer); self.assertIn('not legal advice',answer)
    def test_keyword_ranking(self):
        scores=bm25('Section 3 traditional knowledge',['A car has wheels.','Section 3 concerns traditional knowledge.'])
        self.assertGreater(scores[1],scores[0])
    def test_classification_does_not_guess(self):
        questions=classification_questions("Help classify this Ayurveda formulation. Use/claims: unknown. Text/composition/process: unknown.", "india")
        self.assertEqual(len(questions),1)
        with patch('rag.chatbot.call_json') as call:
            answer=ask_llm("Help classify this Ayurveda formulation. Use/claims: unknown.",[])
            self.assertIn("No regulatory category",answer); call.assert_not_called()
    def test_regime_routing(self):
        from rag.retriever import route_regimes
        self.assertIn('patents',route_regimes('traditional knowledge patent'))
        self.assertIn('patents',route_regimes('What does Section 3(p) say about traditional knowledge?'))
        self.assertIn('biodiversity_abs',route_regimes('patent and ABS compliance'))
        self.assertEqual([],route_regimes('football scores'))
    def test_span_references_resolve_to_real_evidence(self):
        from rag.chatbot import resolve_spans
        data={"claims":[{"text":"The sample is ALPHA.","evidence":[{"source":1,"span":1}]}]}
        self.assertEqual(len(validate_claims(resolve_spans(data,self.docs),self.docs)),1)
        data={"claims":[{"text":"The sample is ALPHA.","evidence":[{"source":1,"span":999}]}]}
        self.assertEqual(validate_claims(resolve_spans(data,self.docs),self.docs),[])
    def test_auditor_can_remove_unsupported_claims(self):
        data={"claims":[{"text":"The identifier is ALPHA.","evidence":[{"source":1,"quote":self.docs[0].page_content}]},
                        {"text":"Unsupported BETA statement.","evidence":[{"source":1,"quote":self.docs[0].page_content}]}]}
        with patch('rag.chatbot.call_json',side_effect=[data,{"supported":False,"supported_claims":[1]}]):
            answer=ask_llm('What is the sample?',self.docs)
            self.assertIn('ALPHA',answer); self.assertNotIn('BETA',answer)
    def test_malformed_claims(self):
        for claims in (None,{},[{}],[{'text':'x','evidence':[]}],[None]):
            self.assertEqual([],validate_claims({'claims':claims},self.docs))
if __name__=='__main__': unittest.main()
