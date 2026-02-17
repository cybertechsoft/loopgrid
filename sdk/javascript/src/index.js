/**
 * LoopGrid JavaScript SDK
 * 
 * The control plane for AI decision reliability.
 * 
 * Installation:
 *   npm install @cybertechsoft/loopgrid
 * 
 * Usage:
 *   const { LoopGrid } = require('@cybertechsoft/loopgrid');
 *   const grid = new LoopGrid({ serviceName: 'my-agent' });
 * 
 * Documentation: https://github.com/cybertechsoft/loopgrid
 */

const VERSION = '0.1.0';

class LoopGridError extends Error {
  constructor(message) {
    super(message);
    this.name = 'LoopGridError';
  }
}

class LoopGridAPIError extends LoopGridError {
  constructor(statusCode, detail) {
    super(`API Error ${statusCode}: ${detail}`);
    this.name = 'LoopGridAPIError';
    this.statusCode = statusCode;
    this.detail = detail;
  }
}

class LoopGrid {
  constructor(options = {}) {
    this.baseUrl = (options.baseUrl || 'http://localhost:8000').replace(/\/$/, '');
    this.serviceName = options.serviceName || 'default';
    this.timeout = options.timeout || 30000;
  }

  async _request(method, endpoint, data = null) {
    const url = `${this.baseUrl}${endpoint}`;
    const options = { method, headers: { 'Content-Type': 'application/json' } };
    if (data) options.body = JSON.stringify(data);

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), this.timeout);
      const response = await fetch(url, { ...options, signal: controller.signal });
      clearTimeout(timeoutId);
      const json = await response.json();
      if (!response.ok) throw new LoopGridAPIError(response.status, json.detail || response.statusText);
      return json;
    } catch (error) {
      if (error instanceof LoopGridAPIError) throw error;
      if (error.name === 'AbortError') throw new LoopGridError(`Request timed out after ${this.timeout}ms`);
      throw new LoopGridError(`Cannot connect to LoopGrid at ${this.baseUrl}: ${error.message}`);
    }
  }

  // Decision Operations
  async recordDecision({ decisionType, input, model, output, prompt, toolCalls, metadata }) {
    const data = { service_name: this.serviceName, decision_type: decisionType, input, model, output };
    if (prompt) data.prompt = prompt;
    if (toolCalls) data.tool_calls = toolCalls;
    if (metadata) data.metadata = metadata;
    return this._request('POST', '/v1/decisions', data);
  }

  async getDecision(decisionId) { return this._request('GET', `/v1/decisions/${decisionId}`); }

  async listDecisions(options = {}) {
    const params = new URLSearchParams();
    if (options.serviceName) params.append('service_name', options.serviceName);
    if (options.decisionType) params.append('decision_type', options.decisionType);
    if (options.status) params.append('status', options.status);
    params.append('page', options.page || 1);
    params.append('page_size', options.pageSize || 20);
    return this._request('GET', `/v1/decisions?${params.toString()}`);
  }

  async markIncorrect(decisionId, reason) {
    return this._request('POST', `/v1/decisions/${decisionId}/incorrect`, reason ? { reason } : {});
  }

  async attachCorrection({ decisionId, correction, correctedBy, notes }) {
    const data = { correction, corrected_by: correctedBy };
    if (notes) data.notes = notes;
    return this._request('POST', `/v1/decisions/${decisionId}/correction`, data);
  }

  // Replay Operations
  async createReplay({ decisionId, overrides, triggeredBy = 'sdk' }) {
    const data = { decision_id: decisionId, triggered_by: triggeredBy };
    if (overrides) data.overrides = overrides;
    return this._request('POST', '/v1/replays', data);
  }

  async getReplay(replayId) { return this._request('GET', `/v1/replays/${replayId}`); }
  async compare(decisionId, replayId) { return this._request('GET', `/v1/decisions/${decisionId}/compare/${replayId}`); }

  // Integrity & Compliance
  async verifyIntegrity(serviceName) {
    const params = serviceName ? `?service_name=${serviceName}` : '';
    return this._request('GET', `/v1/integrity/verify${params}`);
  }

  async complianceReport(serviceName) {
    const params = serviceName ? `?service_name=${serviceName}` : '';
    return this._request('GET', `/v1/compliance/report${params}`);
  }

  async health() { return this._request('GET', '/health'); }
}

module.exports = { LoopGrid, LoopGridError, LoopGridAPIError, VERSION };
module.exports.default = LoopGrid;
