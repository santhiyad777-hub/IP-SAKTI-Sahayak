import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from rag.chatbot import classification_questions
from utils.workspace_tools import profile_prompt, evidence_passport, review_pack, source_inventory, record_event

class WorkspaceToolsTests(unittest.TestCase):
    def sample(self):
        return {'role':'assistant','message_id':'m','jurisdiction':'india','original_answer':'Supported claim [2]', 'retrieved_context':[{'page_content':'Unused','metadata':{'title':'Unused'}},{'page_content':'Exact source excerpt','metadata':{'title':'Used law','page':3,'source_url':'https://example.org/law.pdf','source_id':'used','jurisdiction':'india','content_hash':'abc'}}]}
    def test_passport_only_contains_cited_context(self):
        p=evidence_passport(self.sample())
        self.assertEqual([s['title'] for s in p['sources']],['Used law'])
        self.assertEqual(p['sources'][0]['pdf_page'],4)
        self.assertEqual(p['status'],'Source-linked answer')
    def test_unknown_citation_is_not_confident(self):
        m=self.sample();m['original_answer']='Claim [9]'
        p=evidence_passport(m)
        self.assertEqual(p['unresolved_references'],[9])
        self.assertEqual(p['status'],'Citation needs review')
    def test_abstention_and_clarification_have_distinct_states(self):
        from rag.chatbot import ABSTAIN
        self.assertEqual(evidence_passport({'content':ABSTAIN})['status'],'Insufficient evidence')
        self.assertEqual(evidence_passport({'content':'Which country?', 'response_kind':'clarification'})['status'],'Awaiting product details')
    def test_empty_profile_asks_for_use_instead_of_category(self):
        q=profile_prompt({})
        self.assertIn('unknown',q)
        self.assertIn('intended use',classification_questions(q,'india')[0])
    def test_profile_facts_preserved_in_both_routes(self):
        profile={'use':'skin moisturising','route':'topical','claim':'moisturises','formula':'aloe cream','origin':'India','activity':'commercial use','applicant':'Indian company'}
        for task in ('classification','abs'):
            self.assertIn('aloe cream',profile_prompt(profile,task))
            self.assertIn('Indian company',profile_prompt(profile,task))
    def test_audit_never_contains_private_content(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'audit.jsonl';m=self.sample();m['content']='SECRET FORMULA';m['api_key']='secret-key'
            record_event(p,'answer_created',m)
            text=p.read_text(encoding='utf-8')
            self.assertNotIn('SECRET',text);self.assertNotIn('secret-key',text);self.assertNotIn('Exact source excerpt',text)
            self.assertEqual(json.loads(text)['cited_sources'],1)
    def test_review_pack_retains_original_and_citations(self):
        text=review_pack({'product_profile':{'formula':'aloe'},'messages':[self.sample()]})
        self.assertIn('aloe',text);self.assertIn('Supported claim [2]',text);self.assertIn('https://example.org/law.pdf',text)
        self.assertIn('No appointment',text)
    def test_freshness_is_scoped_and_unknown_dates_flagged(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'dataset/source_registry').mkdir(parents=True);(root/'law.txt').write_text('law')
            rows=[{'title':'India law','jurisdiction':'india','local_file_path':'law.txt','status':'verified'}, {'title':'Treaty','jurisdiction':'international'}]
            (root/'dataset/source_registry/curated.json').write_text(json.dumps(rows))
            found=source_inventory(root,'india',today=date(2026,9,28))
            self.assertEqual(len(found),1);self.assertEqual(found[0]['Review'],'Check snapshot');self.assertEqual(found[0]['Local file'],'Present')
    def test_abs_intent_does_not_turn_into_patent_intake(self):
        from rag.conversation import necessary_followup
        from utils.workspace_tools import profile_retrieval_query
        q=profile_prompt({'origin':'Aloe sourced in India','applicant':'Indian company','activity':'commercial manufacture','resource_status':'cultivated'},'abs')
        self.assertEqual(necessary_followup(q),'')
        self.assertNotIn('patentability',profile_retrieval_query(q))
        self.assertIn('Biological Diversity Act',profile_retrieval_query(q))
    def test_missing_abs_facts_ask_for_abs_information(self):
        from rag.conversation import necessary_followup
        self.assertIn('biological resource',necessary_followup(profile_prompt({},'abs')))
    def test_classification_asks_for_missing_composition(self):
        q=profile_prompt({'use':'moisturising','route':'topical','claim':'moisturises'})
        self.assertIn('authoritative text',classification_questions(q,'india')[0])
    def test_profile_clarification_is_retained_for_retrieval(self):
        from utils.workspace_tools import profile_retrieval_query
        q=profile_prompt({},'abs')+'\nUser clarification: Aloe from Kerala for research'
        self.assertIn('Aloe from Kerala',profile_retrieval_query(q))
    def test_abs_does_not_assume_cultivated_or_wild_origin(self):
        from rag.conversation import necessary_followup
        q=profile_prompt({'origin':'Aloe sourced in India','applicant':'Indian company','activity':'commercial manufacture'},'abs')
        self.assertIn('cultivated',necessary_followup(q))
    def test_empty_draft_can_recover_a_supported_rule_once(self):
        from unittest.mock import patch
        from langchain_core.documents import Document
        from rag.chatbot import ask_llm
        docs=[Document(page_content='The sample identifier is ALPHA.',metadata={'jurisdiction':'india'})]
        draft={'claims':[{'text':'The sample identifier is ALPHA.','evidence':[{'source':1,'span':1}]}]}
        with patch('rag.chatbot.call_json',side_effect=[{'claims':[],'clarification':'What is the sample?'},draft,{'supported':True,'answers_question':True}]) as call:
            self.assertIn('ALPHA',ask_llm('What is the sample identifier?',docs))
            self.assertEqual(call.call_count,3)
    def test_empty_draft_retry_is_bounded(self):
        from unittest.mock import patch
        from langchain_core.documents import Document
        from rag.chatbot import ask_llm,ABSTAIN
        docs=[Document(page_content='The sample identifier is ALPHA.',metadata={'jurisdiction':'india'})]
        empty={'claims':[],'clarification':'What is the sample?'}
        with patch('rag.chatbot.call_json',side_effect=[empty,empty]) as call:
            self.assertIn(ABSTAIN,ask_llm('What is the sample identifier?',docs))
            self.assertEqual(call.call_count,2)
