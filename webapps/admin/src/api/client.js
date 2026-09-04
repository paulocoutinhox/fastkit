export class ApiError extends Error {
    constructor(status, payload) {
        super(payload.detail || "Request failed");

        this.status = status;
        this.code = payload.code || "error.internal";
        this.errors = payload.errors || {};
    }
}

// The server declares where the API answers, and the build hands that same value over here.
export const API_PATH = __API_PATH__;

const state = { token: null, locale: "en", onUnauthorized: null };

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

async function request(method, path, { body, params } = {}) {
    const response = await fetch(`${API_PATH}${path}${buildQuery(params)}`, { method, headers: buildHeaders(body), body: body instanceof FormData ? body : body === undefined ? undefined : JSON.stringify(body) });

    if (response.status === 204) {
        return null;
    }

    const payload = await response.json().catch(() => ({}));

    if (!response.ok) {
        if (response.status === 401 && state.onUnauthorized) {
            state.onUnauthorized();
        }

        throw new ApiError(response.status, payload);
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
