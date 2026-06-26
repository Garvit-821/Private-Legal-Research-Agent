/**
 * Local-Cortex API contract helpers (schema v1).
 */
(function (global) {
    const SCHEMA_VERSION = '1.0';

    function unwrapEnvelope(body) {
        if (!body || typeof body !== 'object') return body;
        if (body.schema_version === SCHEMA_VERSION) {
            if (body.error) {
                const err = new Error(body.error.message || 'Request failed');
                err.code = body.error.code;
                err.details = body.error.details;
                throw err;
            }
            return body.data;
        }
        return body;
    }

    async function apiJson(url, options = {}) {
        const response = await fetch(url, options);
        const body = await response.json();
        if (!response.ok) {
            try {
                unwrapEnvelope(body);
            } catch (err) {
                throw err;
            }
            throw new Error(body.detail || body.message || 'Request failed');
        }
        return unwrapEnvelope(body);
    }

    function parseSsePayload(raw) {
        const body = JSON.parse(raw);
        if (body.schema_version === SCHEMA_VERSION) {
            if (body.error) {
                const err = new Error(body.error.message || 'Stream error');
                err.code = body.error.code;
                throw err;
            }
            return body;
        }
        return { schema_version: null, type: body.type, data: body, error: null };
    }

    global.CortexContracts = {
        SCHEMA_VERSION,
        unwrapEnvelope,
        apiJson,
        parseSsePayload,
    };
})(window);
