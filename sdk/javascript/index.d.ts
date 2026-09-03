export type Json = Record<string, any>;
export interface LoopGridOptions { baseUrl?: string; apiKey?: string | null; workspaceId?: string; bearerToken?: string | null; }
export declare class LoopGrid {
  constructor(options?: LoopGridOptions);
  recordDecision(data: Json): Promise<Json>;
  getDecision(id: string): Promise<Json>;
  listDecisions(limit?: number): Promise<Json[]>;
  addEvent(id: string, data: Json): Promise<Json>;
  modelCompleted(id: string, payload: Json, actorId?: string, extra?: Json): Promise<Json>;
  policyEvaluated(id: string, payload: Json, actorId?: string, extra?: Json): Promise<Json>;
  humanApproved(id: string, reviewer: string, reason?: string, extra?: Json): Promise<Json>;
  humanRejected(id: string, reviewer: string, reason?: string, extra?: Json): Promise<Json>;
  toolExecuted(id: string, payload: Json, actorId?: string, extra?: Json): Promise<Json>;
  outcomeObserved(id: string, payload: Json, actorId?: string, extra?: Json): Promise<Json>;
  policies(): Promise<Json[]>;
  evaluatePolicy(policyId: string, proposedAction: Json, authority?: Json, context?: Json): Promise<Json>;
  reviews(): Promise<Json[]>;
  review(id: string, action: 'approve'|'reject', reviewer: string, reason?: string): Promise<Json>;
  verifyWorkspace(): Promise<Json>;
  checkpoint(): Promise<Json>;
  exportEvidence(id: string, includePayloads?: boolean): Promise<ArrayBuffer>;
  systemInfo(): Promise<Json>;
  readiness(): Promise<Json>;
  pilotReadiness(): Promise<Json>;
  replay(id: string, data: Json): Promise<Json>;
  ingestOTel(spans: Json[]): Promise<Json>;
  ingestMCP(request: Json, response?: Json | null, extra?: Json): Promise<Json>;
  payloadStatus(id: string): Promise<Json>;
  erasePayload(id: string, reason?: string): Promise<Json>;
  runRetention(): Promise<Json>;
  decision(id: string): Promise<Json>;
  decisions(limit?: number): Promise<Json[]>;
  verify(): Promise<Json>;
  evidence(id: string, includePayloads?: boolean): Promise<ArrayBuffer>;
}
