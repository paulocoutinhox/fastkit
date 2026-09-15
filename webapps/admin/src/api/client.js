export class ApiError extends Error {
    constructor(status, payload) {
        super(payload.detail);

        this.status = status;
        this.code = payload.code;
        this.errors = payload.errors || {};
    }
}

// The server declares where the API answers, and the build hands that same value over here.
export const API_PATH = __API_PATH__;

// The words for what the server never said, handed over by whoever installed the catalogues, because this module reaching for one would read another in the suite.
const state = { token: null, locale: "en", onUnauthorized: null, translate: null };

export function configure(options) {
    Object.assign(state, options);
}

function buildHeaders(body) {
    const headers = { "Accept-Language": state.locale };

    if (state.token) {
        headers.Authorization = `Bearer ${state.token}`;
    }

    if (body !== undefined && !(body instanceof FormData)) {
        headers["Content-Type"] = "application/json";
    }

    return headers;
}

function buildQuery(params) {
    const query = new URLSearchParams();

    Object.entries(params || {}).forEach(([name, value]) => {
        if (value !== null && value !== undefined && value !== "") {
            query.append(name, value);
        }
    });

    const serialized = query.toString();

    return serialized ? `?${serialized}` : "";
}

function unsaid(status, code) {
    return new ApiError(status, { code, detail: state.translate(code) });
}

async function request(method, path, { body, params } = {}) {
    let response;

    // A network that dropped answers nothing at all, and the browser's own sentence for it is in English whatever the panel speaks.
    try {
        response = await fetch(`${API_PATH}${path}${buildQuery(params)}`, { method, headers: buildHeaders(body), body: body instanceof FormData ? body : body === undefined ? undefined : JSON.stringify(body) });
    } catch {
        throw unsaid(0, "message.unreachable");
    }

    if (response.status === 204) {
        return null;
    }

    const payload = await response.json().catch(() => null);

    if (!response.ok) {
        if (response.status === 401 && state.onUnauthorized) {
            state.onUnauthorized();
        }

        // A proxy in front answers its own page for a body too large or a server gone, which carries no sentence of ours.
        throw payload?.detail ? new ApiError(response.status, payload) : unsaid(response.status, "message.unreadableAnswer");
    }

    return payload;
}

export const api = {
    get: (path, params) => request("GET", path, { params }),
    post: (path, body) => request("POST", path, { body }),
    put: (path, body) => request("PUT", path, { body }),
    remove: (path) => request("DELETE", path),
    upload: (purpose, file) => {
        const body = new FormData();
        body.append("file", file);

        return request("POST", `/uploads/${purpose}`, { body });
    },
};
