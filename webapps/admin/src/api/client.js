import { ApiError } from "./api-error";

// The server declares where the API answers, and the build hands that same value over here.
export const API_PATH = __API_PATH__;

// The words for what the server never said, handed over by whoever installed the catalogues, because this module reaching for one would read another in the suite.
const state = { token: null, sessionRevision: 0, locale: "en", onUnauthorized: null, translate: null };

export function configure(options) {
    if (Object.hasOwn(options, "token")) {
        state.sessionRevision += 1;
    }

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

async function sent(method, path, { body, params } = {}) {
    const sessionRevision = state.sessionRevision;
    let response;

    // A network that dropped answers nothing at all, and the browser's own sentence for it is in English whatever the panel speaks.
    try {
        response = await fetch(`${API_PATH}${path}${buildQuery(params)}`, { method, headers: buildHeaders(body), body: body instanceof FormData ? body : body === undefined ? undefined : JSON.stringify(body) });
    } catch {
        throw unsaid(0, "message.unreachable");
    }

    if (response.status === 401 && state.token && sessionRevision === state.sessionRevision && state.onUnauthorized) {
        state.onUnauthorized();
    }

    return response;
}

async function refusal(response) {
    let payload;

    try {
        payload = await response.json();
    } catch {
        return unsaid(response.status, "message.unreadableAnswer");
    }

    // A proxy in front answers its own page for a body too large or a server gone, which carries no sentence of ours.
    return payload?.detail ? new ApiError(response.status, payload) : unsaid(response.status, "message.unreadableAnswer");
}

async function request(method, path, options) {
    const response = await sent(method, path, options);

    if (response.status === 204) {
        return null;
    }

    if (!response.ok) {
        throw await refusal(response);
    }

    try {
        return await response.json();
    } catch {
        throw unsaid(response.status, "message.unreadableAnswer");
    }
}

// A file comes back as bytes and the name the server gave it, which is the name the browser saves it under.
async function download(path, params) {
    const response = await sent("GET", path, { params });

    if (!response.ok) {
        throw await refusal(response);
    }

    const [, filename] = /filename="([^"]+)"/.exec(response.headers.get("Content-Disposition"));

    return { blob: await response.blob(), filename };
}

export const api = {
    get: (path, params) => request("GET", path, { params }),
    post: (path, body) => request("POST", path, { body }),
    put: (path, body) => request("PUT", path, { body }),
    remove: (path) => request("DELETE", path),
    download,
    upload: (purpose, file) => {
        const body = new FormData();
        body.append("file", file);

        return request("POST", `/uploads/${purpose}`, { body });
    },
};
