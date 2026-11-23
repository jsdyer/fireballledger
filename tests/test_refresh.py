import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from refresh import configuration, normalize, differences, retain, ROOT

FIELDS=['date','energy','impact-e','lat','lat-dir','lon','lon-dir','alt']
def payload(rows):return {'signature':{'version':'1.2','source':'NASA/JPL Fireball Data API'},'count':len(rows),'fields':FIELDS,'data':rows}
ROW=['2020-01-01 00:00:00','2','.4',None,None,None,None,None]
class RefreshTests(unittest.TestCase):
 def setUp(self):self.config=json.loads((ROOT/'web/config.json').read_text())
 def test_null_location_and_zero_location_are_distinct(self):
  data=normalize(payload([ROW, ['2020-01-02 00:00:00','1','.1','0','N','0','E',None]]),self.config)
  self.assertEqual(data[0]['lat'],'0');self.assertIsNone(data[1]['lat'])
 def test_partial_coordinates_fail(self):
  row=ROW.copy();row[3]='10'
  with self.assertRaises(ValueError):normalize(payload([row]),self.config)
 def test_api_version_and_count_are_guarded(self):
  p=payload([ROW]);p['signature']['version']='2.0'
  with self.assertRaises(ValueError):normalize(p,self.config)
  p=payload([ROW]);p['count']=2
  with self.assertRaises(ValueError):normalize(p,self.config)
 def test_same_date_edit_is_revision_but_date_edit_is_unmatched(self):
  old=normalize(payload([ROW]),self.config);new=copy.deepcopy(old);new[0]['energy']='3'
  delta=differences(old,new);self.assertEqual(len(delta['changed']),1);self.assertFalse(delta['added'])
  new[0]['date']='2020-01-01 00:00:01';delta=differences(old,new)
  self.assertEqual(delta['added'],['2020-01-01 00:00:01']);self.assertEqual(delta['absent'],['2020-01-01 00:00:00'])
 def test_failed_capture_does_not_mutate_index(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);retain(payload([ROW]),self.config,root,'2026-01-01T00:00:00Z');before=(root/'index.json').read_bytes()
   with self.assertRaises(ValueError):retain(payload([]),self.config,root,'2026-01-02T00:00:00Z')
   self.assertEqual(before,(root/'index.json').read_bytes())
 def test_new_scope_keeps_old_capture_but_has_no_false_diff(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);first=retain(payload([ROW]),self.config,root,'2026-01-01T00:00:00Z')
   cfg=copy.deepcopy(self.config);cfg['apiParameters']['date-min']='2000-01-01';second=retain(payload([ROW]),cfg,root,'2026-01-02T00:00:00Z')
   self.assertIsNone(second['comparison']);self.assertTrue((root/first['file']).exists())
 def test_retention_and_same_scope_comparison(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);self.config['retainCaptures']=2
   for day in range(1,4):retain(payload([ROW]),self.config,root,f'2026-01-0{day}T00:00:00Z')
   index=json.loads((root/'index.json').read_text());self.assertEqual(len(index['captures']),2);self.assertEqual(len(list((root/'captures').iterdir())),2)
   self.assertEqual(index['captures'][0]['comparison'],{'added':0,'absent':0,'changed':0})
 def test_unexpected_shrink_fails(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);row=ROW.copy();row[0]='2020-01-02 00:00:00';retain(payload([ROW,row]),self.config,root,'2026-01-01T00:00:00Z')
   with self.assertRaisesRegex(ValueError,'shrinkage'):retain(payload([ROW]),self.config,root,'2026-01-02T00:00:00Z')
if __name__=='__main__':unittest.main()
