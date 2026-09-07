import tempfile
import unittest
from pathlib import Path
from test_astra_cheap import load_helper

class FocusTests(unittest.TestCase):
    def test_literal_focus_and_recovery(self):
        h=load_helper()
        with tempfile.TemporaryDirectory() as d:
            p=Path(d); (p/'run.log').write_text('noise\nbefore\njob[7] failed\nafter\nother\n')
            r=h.pack(p,'run.log','view.json',contains='job[7]',context=1)
            self.assertEqual([x['line'] for x in r['lines']],[2,3,4])
            self.assertFalse(r['complete'])
            self.assertEqual(h.expand(p,'view.json',1,1)['lines'][0]['text'],'noise')

    def test_no_match_has_no_unrelated_fallback(self):
        h=load_helper()
        with tempfile.TemporaryDirectory() as d:
            p=Path(d); (p/'run.log').write_text('ERROR unrelated\n')
            r=h.pack(p,'run.log','view.json',contains='job7')
            self.assertEqual(r['lines'],[])
            self.assertFalse(r['complete'])

    def test_invalid_focus_is_rejected(self):
        h=load_helper()
        with tempfile.TemporaryDirectory() as d:
            p=Path(d); (p/'run.log').write_text('x')
            for contains,context in [('',1),('x',-1),('x',True),('x',101)]:
                with self.subTest(contains=contains,context=context):
                    with self.assertRaises(ValueError):
                        h.pack(p,'run.log','view.json',contains=contains,context=context)
