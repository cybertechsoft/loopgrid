from __future__ import annotations
import json,time

def _text(r):
    if getattr(r,'output_text',None):return r.output_text
    try:return r.choices[0].message.content
    except Exception:return str(r)[:4000]
def _usage(r):
    u=getattr(r,'usage',None)
    if not u:return {}
    out={}
    for src,dst in [('input_tokens','input_tokens'),('output_tokens','output_tokens'),('total_tokens','total_tokens'),('prompt_tokens','input_tokens'),('completion_tokens','output_tokens')]:
        v=getattr(u,src,None)
        if v is not None:out[dst]=v
    return out
def _chat_tools(r):
    try:
        calls=getattr(r.choices[0].message,'tool_calls',None) or [];out=[]
        for c in calls:
            f=getattr(c,'function',None);args=getattr(f,'arguments',None)
            try:args=json.loads(args) if isinstance(args,str) else args
            except Exception:pass
            out.append({'id':getattr(c,'id',None),'name':getattr(f,'name',None),'arguments':args})
        return out
    except Exception:return []
class OpenAIRecorder:
    def __init__(self,grid,client,*,agent_id='openai-agent',service_name='openai-agent',privacy_mode=None):self.grid=grid;self.client=client;self.agent_id=agent_id;self.service_name=service_name;self.privacy_mode=privacy_mode
    def _start(self,decision_type,source,kwargs,idem=None):
        return self.grid.record_decision(decision_type=decision_type,service_name=self.service_name,privacy_mode=self.privacy_mode,idempotency_key=idem,agent={'id':self.agent_id},model={'provider':'openai','name':kwargs.get('model')},input={'input':kwargs.get('input'),'messages':kwargs.get('messages')},context={'provider_api':source},metadata={'capture_source':source})
    def responses_create(self,**kwargs):
        idem=kwargs.pop('loopgrid_idempotency_key',None);d=self._start('model_response','openai.responses',kwargs,idem);did=d['decision_id'];started=time.perf_counter()
        try:
            r=self.client.responses.create(**kwargs);lat=round((time.perf_counter()-started)*1000,2);self.grid.add_event(did,'model_completed',{'response':_text(r),'provider_request_id':getattr(r,'id',None),'usage':_usage(r),'latency_ms':lat},actor_type='agent',actor_id=self.agent_id);return r
        except Exception as e:self.grid.add_event(did,'incident_flagged',{'stage':'provider_call','provider':'openai','error_type':type(e).__name__,'message':str(e)[:1000],'latency_ms':round((time.perf_counter()-started)*1000,2)},actor_type='system',actor_id='openai-recorder');raise
    def chat_completions_create(self,**kwargs):
        idem=kwargs.pop('loopgrid_idempotency_key',None);d=self._start('chat_completion','openai.chat.completions',kwargs,idem);did=d['decision_id'];started=time.perf_counter()
        try:
            r=self.client.chat.completions.create(**kwargs);lat=round((time.perf_counter()-started)*1000,2);finish=None
            try:finish=r.choices[0].finish_reason
            except Exception:pass
            self.grid.add_event(did,'model_completed',{'response':_text(r),'provider_request_id':getattr(r,'id',None),'usage':_usage(r),'finish_reason':finish,'latency_ms':lat},actor_type='agent',actor_id=self.agent_id)
            for c in _chat_tools(r):self.grid.add_event(did,'tool_requested',c,actor_type='tool',actor_id=c.get('name') or 'openai-tool')
            return r
        except Exception as e:self.grid.add_event(did,'incident_flagged',{'stage':'provider_call','provider':'openai','error_type':type(e).__name__,'message':str(e)[:1000],'latency_ms':round((time.perf_counter()-started)*1000,2)},actor_type='system',actor_id='openai-recorder');raise
