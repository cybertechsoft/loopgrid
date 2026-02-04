/**
 * LoopGrid JavaScript SDK
 * 
 * The control plane for AI decision reliability.
 * 
 * Installation:
 *   npm install loopgrid
 * 
 * Usage:
 *   const { LoopGrid } = require('loopgrid');
 *   // or: import { LoopGrid } from 'loopgrid';
 *   
 *   const grid = new LoopGrid({ serviceName: 'my-agent' });
 *   
 *   const decision = await grid.recordDecision({
 *     decisionType: 'customer_support_reply',
 *     input: { message: 'I was charged twice' },
 *     model: { provider: 'openai', name: 'gpt-4' },
 *     output: { response: 'Refund initiated.' }
 *   });
 * 
 * Documentation: https://github.com/cybertech/loopgrid
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
  /**
   * Create a LoopGrid client
   * @param {Object} options - Configuration options
   * @param {string} [options.baseUrl='http://localhost:8000'] - LoopGrid server URL
   * @param {string} [options.serviceName='default'] - Your service name
   * @param {number} [options.timeout=30000] - Request timeout in ms
   */
  constructor(options = {}) {
    this.baseUrl = (options.baseUrl || 'http://localhost:8000').replace(/\/$/, '');
    this.serviceName = options.serviceName || 'default';
    this.timeout = options.timeout || 30000;
  }

  async _request(method, endpoint, data = null) {
    const url = `${this.baseUrl}${endpoint}`;
    
    const options = {
      method,
      headers: {
        'Content-Type': 'application/json',
      },
    };

    if (data) {
      options.body = JSON.stringify(data);
    }

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), this.timeout);
      
      const response = await fetch(url, { ...options, signal: controller.signal });
      clearTimeout(timeoutId);

      const json = await response.json();

      if (!response.ok) {
        throw new LoopGridAPIError(response.status, json.detail || response.statusText);
      }

      return json;
    } catch (error) {
      if (error instanceof LoopGridAPIError) {
        throw error;
      }
      if (error.name === 'AbortError') {
        throw new LoopGridError(`Request timed out after ${this.timeout}ms`);
      }
      throw new LoopGridError(`Cannot connect to LoopGrid at ${this.baseUrl}: ${error.message}`);
    }
  }

  // ================================================================
  // Decision Operations
  // ================================================================

  /**
   * Record an AI decision to the ledger
   * @param {Object} params - Decision parameters
   * @param {string} params.decisionType - Type of decision
   * @param {Object} params.input - Input that triggered the decision
   * @param {Object} params.model - Model info (provider, name, version)
   * @param {Object} params.output - The AI's output
   * @param {Object} [params.prompt] - Optional prompt info
   * @param {Array} [params.toolCalls] - Optional tool calls
   * @param {Object} [params.metadata] - Optional metadata
   * @returns {Promise<Object>} The recorded decision
   */
  async recordDecision({ decisionType, input, model, output, prompt, toolCalls, metadata }) {
    const data = {
      service_name: this.serviceName,
      decision_type: decisionType,
      input,
      model,
      output,
    };

    if (prompt) data.prompt = prompt;
    if (toolCalls) data.tool_calls = toolCalls;
    if (metadata) data.metadata = metadata;

    return this._request('POST', '/v1/decisions', data);
  }

  /**
   * Get a decision by ID
   * @param {string} decisionId - Decision ID
   * @returns {Promise<Object>} The decision
   */
  async getDecision(decisionId) {
    return this._request('GET', `/v1/decisions/${decisionId}`);
  }

  /**
   * List decisions with optional filters
   * @param {Object} [options] - Filter options
   * @returns {Promise<Object>} Paginated list of decisions
   */
  async listDecisions(options = {}) {
    const params = new URLSearchParams();
    if (options.serviceName) params.append('service_name', options.serviceName);
    if (options.decisionType) params.append('decision_type', options.decisionType);
    if (options.status) params.append('status', options.status);
    params.append('page', options.page || 1);
    params.append('page_size', options.pageSize || 20);

    return this._request('GET', `/v1/decisions?${params.toString()}`);
  }

  /**
   * Mark a decision as incorrect
   * @param {string} decisionId - Decision ID
   * @param {string} [reason] - Optional reason
   * @returns {Promise<Object>} Updated decision
   */
  async markIncorrect(decisionId, reason) {
    const data = reason ? { reason } : {};
    return this._request('POST', `/v1/decisions/${decisionId}/incorrect`, data);
  }

  /**
   * Attach a human correction to a decision
   * @param {Object} params - Correction parameters
   * @param {string} params.decisionId - Decision ID
   * @param {Object} params.correction - The corrected output
   * @param {string} params.correctedBy - Who made the correction
   * @param {string} [params.notes] - Optional notes
   * @returns {Promise<Object>} Updated decision
   */
  async attachCorrection({ decisionId, correction, correctedBy, notes }) {
    const data = { correction, corrected_by: correctedBy };
    if (notes) data.notes = notes;
    return this._request('POST', `/v1/decisions/${decisionId}/correction`, data);
  }

  // ================================================================
  // Replay Operations
  // ================================================================

  /**
   * Create a replay for a decision
   * @param {Object} params - Replay parameters
   * @param {string} params.decisionId - Decision to replay
   * @param {Object} [params.overrides] - Optional overrides
   * @param {string} [params.triggeredBy='sdk'] - Who triggered the replay
   * @returns {Promise<Object>} The replay result
   */
  async createReplay({ decisionId, overrides, triggeredBy = 'sdk' }) {
    const data = { decision_id: decisionId, triggered_by: triggeredBy };
    if (overrides) data.overrides = overrides;
    return this._request('POST', '/v1/replays', data);
  }

  /**
   * Get a replay by ID
   * @param {string} replayId - Replay ID
   * @returns {Promise<Object>} The replay
   */
  async getReplay(replayId) {
    return this._request('GET', `/v1/replays/${replayId}`);
  }

  /**
   * Compare a decision with a replay
   * @param {string} decisionId - Decision ID
   * @param {string} replayId - Replay ID
   * @returns {Promise<Object>} Comparison result
   */
  async compare(decisionId, replayId) {
    return this._request('GET', `/v1/decisions/${decisionId}/compare/${replayId}`);
  }

  // ================================================================
  // Utility Methods
  // ================================================================

  /**
   * Check if the server is healthy
   * @returns {Promise<Object>} Health status
   */
  async health() {
    return this._request('GET', '/health');
  }
}

// Export for different module systems
module.exports = { LoopGrid, LoopGridError, LoopGridAPIError, VERSION };
module.exports.default = LoopGrid;
