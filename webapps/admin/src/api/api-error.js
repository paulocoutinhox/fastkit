export class ApiError extends Error {
    constructor(status, payload) {
        super(payload.detail);

        this.status = status;
        this.code = payload.code;
        this.errors = payload.errors || {};
    }
}
