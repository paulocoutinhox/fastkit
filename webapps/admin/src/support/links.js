import { API_PATH } from "@/api/client";

// The address a reader would type for a published content, which is the tag and nothing else: a page of the site is one address in every language.
export function contentOnSite(record) {
    return record.tag ? `/content/${record.tag}` : "";
}

// What the operator pastes into the provider console: one address per tenant and per gateway, told apart by the key.
export function webhookUrl(record) {
    return record.webhookKey ? `${window.location.origin}${API_PATH}/webhooks/${record.webhookKey}` : "";
}
