import { API_PATH } from "@/api/client";

// The server knows the site of each brand, so the address comes answered with the page and is never built from the host the panel was opened on.
export function contentOnSite(record) {
    return record.address;
}

// What the operator pastes into the provider console: one address per tenant and per gateway, told apart by the key.
export function webhookUrl(record) {
    return record.webhookKey ? `${window.location.origin}${API_PATH}/webhooks/${record.webhookKey}` : "";
}
