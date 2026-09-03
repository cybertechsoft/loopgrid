from __future__ import annotations
import argparse,json,os,httpx
ap=argparse.ArgumentParser();ap.add_argument('--base-url',default='http://127.0.0.1:8000');ap.add_argument('--key',default=os.getenv('LOOPGRID_INGEST_KEY'));a=ap.parse_args();h={'Content-Type':'application/json'}
if a.key:h['X-LoopGrid-Key']=a.key
p={'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'refund','arguments':{'amount':20,'currency':'USD'}}};r=httpx.post(a.base_url.rstrip('/')+'/api/v1/mcp-proxy/billing',headers=h,json=p,timeout=20);print(r.status_code);print(json.dumps(r.json(),indent=2));raise SystemExit(0 if r.status_code==200 else 1)
