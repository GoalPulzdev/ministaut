import unittest,tempfile
from pathlib import Path
from datetime import datetime,timedelta,timezone
from .control import ControlPlane,Event
from .profiles import StadiumProfile,validate_measurement

URL="https://billett.rbk.no/checkout/6a9a7e3f3f93920b289b0675"
class V3Tests(unittest.TestCase):
 def test_arbitrary_arena_and_fail_closed(self):
  p=StadiumProfile("koteng",1,"vivenu",{"A":100,"B":60},{"A":[2,3],"B":[5,7]},True)
  self.assertEqual(validate_measurement(p,{"A":20,"B":30})[0],True)
  self.assertFalse(validate_measurement(p,{"A":20})[0])
  self.assertFalse(validate_measurement(p,{"A":20,"B":61})[0])
  self.assertFalse(validate_measurement(StadiumProfile("new",1,"vivenu",{"A":50},{"A":[1,2]},False),{"A":1})[0])
 def test_independent_jobs_archive_restart(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/"control.json"
   cp=ControlPlane(path)
   now=datetime(2026,10,24,tzinfo=timezone.utc)
   for i in range(3):
    cp.add(Event(str(i),URL,"lerkendal",(now+timedelta(days=i+1)).isoformat(),"Match"+str(i),state="monitoring"))
   self.assertEqual(len(cp.tick(now)),3)
   self.assertEqual(len(cp.tick(now)),0)
   first=cp.claim("worker",now)
   self.assertEqual(cp.finish(first.id,True,now+timedelta(minutes=1)),"succeeded")
   cp=ControlPlane(path)
   self.assertEqual(len(cp.tick(now+timedelta(minutes=61))),3)
   cp.tick(now+timedelta(days=2))
   self.assertEqual(cp.events["0"].state,"completed")
   self.assertEqual(cp.events["1"].state,"completed")
   self.assertNotEqual(cp.events["2"].state,"completed")
 def test_no_late_publication(self):
  with tempfile.TemporaryDirectory() as tmp:
   cp=ControlPlane(Path(tmp)/"state.json")
   now=datetime(2026,10,24,tzinfo=timezone.utc)
   cp.add(Event("a",URL,"lerkendal",(now+timedelta(minutes=2)).isoformat(),"A",state="monitoring"))
   [job]=cp.tick(now);cp.claim("worker",now)
   self.assertEqual(cp.finish(job.id,True,now+timedelta(minutes=3)),"cancelled")
   self.assertEqual(cp.events["a"].state,"completed")
if __name__=="__main__":unittest.main()
