from __future__ import annotations
import time
from uuid import uuid4
class LoopGridCallbackHandler:
    def __init__(self,grid,*,agent_id='langgraph-agent',service_name='langgraph',privacy_mode=None):self.grid=grid;self.agent_id=agent_id;self.service_name=service_name;self.privacy_mode=privacy_mode;self.runs={};self.started={}
    def on_chain_start(self,serialized,inputs,*,run_id=None,**kwargs):
        rid=str(run_id or uuid4());name=(serialized or {}).get('name') or kwargs.get('name') or 'graph_run';d=self.grid.record_decision(decision_type='agent_graph_run',service_name=self.service_name,privacy_mode=self.privacy_mode,idempotency_key=f'langgraph:{rid}',agent={'id':self.agent_id},context={'run_id':rid,'graph':name},input={'inputs':inputs},metadata={'capture_source':'langgraph-callback'});self.runs[rid]=d['decision_id'];self.started[rid]=time.perf_counter()
    def on_chain_end(self,outputs,*,run_id=None,**kwargs):
        rid=str(run_id);did=self.runs.get(rid)
        if did:self.grid.add_event(did,'model_completed',{'outputs':outputs,'latency_ms':round((time.perf_counter()-self.started.get(rid,time.perf_counter()))*1000,2)},actor_type='agent',actor_id=self.agent_id);self.grid.add_event(did,'outcome_observed',{'status':'succeeded','verified_against':'langgraph-runtime'},actor_type='system',actor_id='langgraph-adapter')
    def on_chain_error(self,error,*,run_id=None,**kwargs):
        rid=str(run_id);did=self.runs.get(rid)
        if did:self.grid.add_event(did,'incident_flagged',{'error_type':type(error).__name__,'message':str(error)[:1000],'latency_ms':round((time.perf_counter()-self.started.get(rid,time.perf_counter()))*1000,2)},actor_type='system',actor_id='langgraph-adapter')
    def on_tool_start(self,serialized,input_str,*,run_id=None,parent_run_id=None,**kwargs):
        did=self.runs.get(str(parent_run_id)) or self.runs.get(str(run_id));name=(serialized or {}).get('name','tool')
        if did:self.grid.add_event(did,'tool_requested',{'tool':name,'input':input_str},actor_type='tool',actor_id=name)
    def on_tool_end(self,output,*,run_id=None,parent_run_id=None,**kwargs):
        did=self.runs.get(str(parent_run_id)) or self.runs.get(str(run_id))
        if did:self.grid.add_event(did,'tool_result',{'output':output},actor_type='tool',actor_id='tool')
