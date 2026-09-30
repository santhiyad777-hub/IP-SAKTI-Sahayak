import unittest
from unittest.mock import patch
from rag.conversation import respond
from rag.chatbot import classification_questions

class SourceFlowTests(unittest.TestCase):
    def test_generation_schema_rejects_invented_statute_number_as_span(self):
        from rag.chatbot import response_schema
        import jsonschema
        schema=response_schema({"evidence":[{"source":1,"spans":[{"span":1,"text":"Evidence"},{"span":2,"text":"Another passage"}]}]})
        valid={"claims":[{"text":"Claim","evidence":[{"reference":"S1P2"}]}],"clarification":""}
        jsonschema.validate(valid,schema)
        valid["claims"][0]["evidence"][0]["reference"]="S1P13"
        with self.assertRaises(jsonschema.ValidationError):jsonschema.validate(valid,schema)

    def test_one_bad_citation_does_not_discard_independent_valid_claim(self):
        from langchain_core.documents import Document
        from rag.chatbot import resolve_spans, validate_claims
        docs=[Document(page_content="A verified source passage with a supported fact.")]
        response={"claims":[
            {"text":"Supported fact", "evidence":[{"reference":"S1P1"}]},
            {"text":"Bad reference", "evidence":[{"reference":"S1P99"}]}]}
        claims=validate_claims(resolve_spans(response,docs),docs)
        self.assertEqual([c["text"] for c in claims],["Supported fact"])

    def test_exact_tanglish_question_asks_without_api_or_retrieval(self):
        with patch('rag.conversation.prepare_query',side_effect=AssertionError('No translation needed')), patch('rag.conversation.retrieve_documents',side_effect=AssertionError('No retrieval needed')), patch('rag.chatbot.call_json',side_effect=AssertionError('No generation needed')):
            result=respond('En herbal product medicine-aa, food-aa, cosmetic-aa?',answer_language='English')
        self.assertIn('intended use',result['answer'])
        self.assertIn('pending_question',result['cache'])

    def test_general_food_question_does_not_trigger_classification(self):
        self.assertEqual(classification_questions('What labelling requirements apply to Ayurveda Aahara products?','india'),[])

    def test_empty_uploads_explain_source_selection(self):
        with patch('rag.conversation.retrieve_documents',return_value=[]),patch('rag.conversation.ask_llm',side_effect=AssertionError('No evidence')):
            result=respond('Can I patent a traditional Ayurvedic formulation?',source_mode='Uploaded documents',answer_language='English')
        self.assertIn('Choose Knowledge base',result['answer'])

    def test_new_question_does_not_inherit_pending_classification(self):
        cache={"pending_question":"En herbal product medicine-aa, food-aa, cosmetic-aa?", "scope":("india","Knowledge base",(),False)}
        question="What labelling requirements apply to Ayurveda Aahara products?"
        with patch('rag.conversation.retrieve_documents',return_value=[]), patch('rag.conversation.ask_llm',return_value='answer') as ask:
            respond(question,cache=cache,answer_language='English')
        self.assertEqual(ask.call_args.args[0],question)

    def test_answer_to_classification_is_not_asked_same_question_again(self):
        self.assertEqual(classification_questions('En herbal product medicine-aa, food-aa, cosmetic-aa?\nUser clarification: A cream for skin moisturising.','india'),[])

if __name__=='__main__':unittest.main()
