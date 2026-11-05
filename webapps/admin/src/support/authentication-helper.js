const SOCIAL_ERRORS = {
    "error.social-link-required": "auth.socialLinkRequired",
    "error.social-identity-in-use": "auth.socialIdentityInUse",
    "error.social-provider-already-connected": "auth.socialAlreadyConnected",
    "error.social-attempt-invalid": "auth.socialAttemptInvalid",
    "error.social-response-invalid": "auth.socialInvalidResponse",
    "error.social-unavailable": "auth.socialUnavailable",
    "error.social-denied": "auth.socialDenied",
    "error.account-blocked": "auth.accountBlocked",
    "error.invalid-credentials": "auth.socialAttemptInvalid",
    "error.panel-not-allowed": "auth.panelNotAllowed",
    "error.authentication-method-disabled": "auth.methodDisabled",
};

export class AuthenticationHelper {
    static socialError(code) {
        if (!Object.hasOwn(SOCIAL_ERRORS, code)) {
            return "auth.socialInvalidResponse";
        }

        return SOCIAL_ERRORS[code];
    }

    static navigate(address) {
        window.location.assign(address);
    }
}
