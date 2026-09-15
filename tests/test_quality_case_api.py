import json,sys,tempfile,threading,unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request,urlopen
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from enterprise_dashboard import make_handler

class QualityCaseApiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();root=Path(self.temp.name);ui=root/"index.html";ui.write_text("ok",encoding="utf-8")
        handler=make_handler(root/"data.db",root/"summary.json",root/"model.json",ui,root/"staging",None)
        self.server=ThreadingHTTPServer(("127.0.0.1",0),handler);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.base=f"http://127.0.0.1:{self.server.server_address[1]}"
    def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join();self.temp.cleanup()
    def request(self,path,payload=None,csrf=True):
        headers={"Content-Type":"application/json"}
        if csrf:headers["X-CSRF-Token"]="test"
        req=Request(self.base+path,data=json.dumps(payload).encode() if payload is not None else None,headers=headers,method="POST" if payload is not None else "GET")
        with urlopen(req) as response:return response.status,json.loads(response.read())
    def test_create_transition_and_read_history(self):
        _,created=self.request("/api/quality/cases",{"lot_id":"lot-api-1","safety_class":"safety","reason":"검토 시작"});case_id=created["case"]["case_id"]
        _,changed=self.request("/api/quality/transition",{"case_id":case_id,"to_status":"INVESTIGATING","reason":"검사 배정"})
        self.assertEqual(changed["case"]["status"],"INVESTIGATING")
        _,loaded=self.request(f"/api/quality/case?id={case_id}");self.assertEqual(len(loaded["events"]),2)
    def test_csrf_is_required_for_change(self):
        with self.assertRaises(HTTPError) as caught:self.request("/api/quality/cases",{"lot_id":"LOT-X","safety_class":"SAFETY","reason":"test"},csrf=False)
        self.assertEqual(caught.exception.code,403)
if __name__=="__main__":unittest.main()
