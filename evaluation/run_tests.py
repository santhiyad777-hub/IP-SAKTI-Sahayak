"""Run isolated tests and write a machine-readable result without shell redirection."""
import json
import logging
import unittest
from pathlib import Path

def main():
 logging.getLogger('streamlit.runtime.scriptrunner_utils.script_run_context').setLevel(logging.ERROR)
 tests=unittest.defaultTestLoader.discover('tests')
 with Path('evaluation/final_tests.log').open('w',encoding='utf-8') as log:
  result=unittest.TextTestRunner(stream=log,verbosity=2).run(tests)
 summary={'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),'passed':result.wasSuccessful()}
 Path('evaluation/final_tests.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
 print(json.dumps(summary))
 raise SystemExit(0 if result.wasSuccessful() else 1)
if __name__=='__main__':main()
