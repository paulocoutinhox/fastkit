import { mintRecaptcha } from "../../../recaptcha.js";

const ACTION = "admin_signin";

export function mintSignInToken(siteKey, document) {
    return mintRecaptcha(siteKey, ACTION, document);
}
