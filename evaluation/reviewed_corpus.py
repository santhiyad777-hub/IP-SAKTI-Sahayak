"""Offline retrieval checks for the SIH26045 corpus; no generation API calls."""
import json
from config import BASE_DIR
from rag.retriever import retrieve_documents
from ingestion.pipeline import write_json

CASES=[
 ('india','Biological Diversity Rules 2024 application forms NBA approval',{'bd_rules_2024'}),
 ('international','Convention on Biological Diversity Article 15 access genetic resources',{'cbd_convention'}),
 ('india','Cosmetics Rules 2020 labelling import registration certificate',{'cosmetics_rules_2020'}),
 ('india','phytopharmaceutical new drug clinical trials rules 2019',{'ndct_rules_2019'}),
 ('india','Ayurveda Aahara 2022 NOT FOR MEDICINAL USE label',{'ayurveda_aahara_2022'}),
 ('india','Drugs and Magic Remedies 1954 prohibition misleading advertisements section 4',{'drugs_magic_remedies_1954'}),
 ('international','UK MHRA traditional herbal registration THR 30 years',{'uk_herbal_registration'}),
 ('international','Budapest Treaty Article 3 deposit microorganisms patent',{'budapest_treaty'}),
 ('international','Madrid Protocol Article 3 international trademark application',{'madrid_protocol'}),
 ('international','Hague Geneva Act Article 5 international design application',{'hague_geneva_act'}),
 ('india','DPDP Rules 2025 Data Fiduciary security safeguards consent',{'dpdp_rules_2025'}),
 ('india','Navara Rice geographical indication registration application 17',{'navara_gi_record'}),
 ('international','NIST AI RMF GOVERN MAP MEASURE MANAGE',{'nist_ai_rmf'}),
]

def main():
    results=[]
    for jurisdiction,question,expected in CASES:
        docs=retrieve_documents(question,jurisdiction=jurisdiction)
        actual={d.metadata.get('source_id') for d in docs}
        row=dict(question=question,jurisdiction=jurisdiction,expected=sorted(expected),retrieved=sorted(actual),
                 relevant_source_found=bool(actual&expected),jurisdiction_separation=all(d.metadata['jurisdiction']==jurisdiction for d in docs),
                 source_citations_present=all(d.metadata.get('source_url') and d.metadata.get('title') for d in docs))
        results.append(row);print(json.dumps(row),flush=True)
    report=dict(cases=len(results),passed=sum(r['relevant_source_found'] and r['jurisdiction_separation'] and r['source_citations_present'] for r in results),results=results)
    write_json(BASE_DIR/'dataset/review_26045/retrieval_checks.json',report)
    assert report['passed']==report['cases'],report

if __name__=='__main__':main()
