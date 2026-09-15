import "./style.css";

import { bindBanners, sendCount } from "./banner";
import { bindFlashes } from "./flash";
import { bindLightbox } from "./lightbox";
import { bindMasks } from "./mask";
import { bindMenu } from "./menu";
import { bindPostalCode, fetchPostalCode } from "./postal-code";
import { bindRecaptcha, mintToken } from "./recaptcha";
import { bindSubmits } from "./submit";
import { bindUploads } from "./upload";

function start(root = document) {
    bindSubmits(root);
    bindMenu(root);
    bindFlashes(root);
    bindUploads(root);
    bindMasks(root);
    bindLightbox(root);
    bindPostalCode(root, fetchPostalCode);
    bindBanners(root, sendCount);
    bindRecaptcha(root, mintToken);
}

start();
