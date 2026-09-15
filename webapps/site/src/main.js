import "./style.css";

import { bindBanners, sendCount } from "./banner";
import { bindConsent, sendConsent } from "./consent";
import { bindFlashes } from "./flash";
import { bindLightbox } from "./lightbox";
import { bindMasks } from "./mask";
import { bindMenu } from "./menu";
import { bindPostalCode, fetchPostalCode } from "./postal-code";
import { bindRecaptcha } from "./recaptcha";
import { bindSubmits } from "./submit";
import { bindUploads } from "./upload";

// A challenge Google refuses to mint has to fail, because a promise that never settles is a form that never leaves.
export function grecaptchaToken(siteKey) {
    return new Promise((resolve, reject) => {
        window.grecaptcha.ready(() => window.grecaptcha.execute(siteKey, { action: "submit" }).then(resolve, reject));
    });
}

function start(root = document) {
    bindSubmits(root);
    bindMenu(root);
    bindFlashes(root);
    bindConsent(root, sendConsent);
    bindUploads(root);
    bindMasks(root);
    bindLightbox(root);
    bindPostalCode(root, fetchPostalCode);
    bindBanners(root, sendCount);

    if (window.grecaptcha) {
        bindRecaptcha(root, grecaptchaToken);
    }
}

start();
