from fastapi import FastAPI, Request
import uvicorn
app=FastAPI(title='LoopGrid local MCP test double')
@app.post('/rpc')
async def rpc(req:Request):
    b=await req.json();p=b.get('params') or {}
    if b.get('method')=='tools/call':return {'jsonrpc':'2.0','id':b.get('id'),'result':{'ok':True,'tool':p.get('name'),'echo':p.get('arguments') or {},'external_reference':'mcp_test_001'}}
    if b.get('method')=='tools/list':return {'jsonrpc':'2.0','id':b.get('id'),'result':{'tools':[{'name':'refund','description':'Local test refund tool'}]}}
    return {'jsonrpc':'2.0','id':b.get('id'),'result':{'ok':True}}
if __name__=='__main__':uvicorn.run(app,host='127.0.0.1',port=9100)
