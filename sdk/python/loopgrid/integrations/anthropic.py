from __future__ import annotations
import time

def _text(r):
    try:return '\n'.join(getattr(x,'text','') for x in r.content if getattr(x,'text',None))
    except Exception:return str(r)[:4000]
def _usage(r):
    u=getattr(r,'usage',None);return {k:getattr(u,k) for k in ('input_tokens','output_tokens') if u and getattr(u,k,None) is not None}
def _tools(r):
    out=[]
    try:
        for b in r.content:
            if getattr(b,'type',None)=='tool_use':out.append({'id':getattr(b,'id',None),'name':getattr(b,'name',None),'arguments':getattr(b,'input',None)})
    except Exception:pass
    return out
class AnthropicRecorder:
    def __init__(self,grid,client,*,agent_id='anthropic-agent',service_name='anthropic-agent',privacy_mode=None):self.grid=grid;self.client=client;self.agent_id=agent_id;self.service_name=service_name;self.privacy_mode=privacy_mode
    def messages_create(self,**kwargs):
        idem=kwargs.pop('loopgrid_idempotency_key',None);d=self.grid.record_decision(decision_type='model_message',service_name=self.service_name,privacy_mode=self.privacy_mode,idempotency_key=idem,agent={'id':self.agent_id},model={'provider':'anthropic','name':kwargs.get('model')},input={'messages':kwargs.get('messages')},context={'provider_api':'anthropic.messages'},metadata={'capture_source':'anthropic.messages'});did=d['decision_id'];started=time.perf_counter()
        try:
            r=self.client.messages.create(**kwargs);lat=round((time.perf_counter()-started)*1000,2);self.grid.add_event(did,'model_completed',{'response':_text(r),'provider_request_id':getattr(r,'id',None),'usage':_usage(r),'stop_reason':getattr(r,'stop_reason',None),'latency_ms':lat},actor_type='agent',actor_id=self.agent_id)
            for c in _tools(r):self.grid.add_event(did,'tool_requested',c,actor_type='tool',actor_id=c.get('name') or 'anthropic-tool')
            return r
        except Exception as e:self.grid.add_event(did,'incident_flagged',{'stage':'provider_call','provider':'anthropic','error_type':type(e).__name__,'message':str(e)[:1000],'latency_ms':round((time.perf_counter()-started)*1000,2)},actor_type='system',actor_id='anthropic-recorder');raise
