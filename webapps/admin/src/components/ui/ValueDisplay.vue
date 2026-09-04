<script setup>
import { computed } from "vue";
import { useI18n } from "vue-i18n";

import AppBadge from "./AppBadge.vue";
import AppIcon from "./AppIcon.vue";
import { useAuthStore } from "@/stores/auth";
import { useMetaStore } from "@/stores/meta";
import { formatDate, formatDateTime } from "@/support/datetime";
import { valueAt } from "@/support/dependencies";

const props = defineProps({
    column: { type: Object, required: true },
    record: { type: Object, required: true },
    truncate: { type: Boolean, default: false },
});

const { locale, t, te } = useI18n();
const auth = useAuthStore();
const meta = useMetaStore();

const value = computed(() => props.record[props.column.name]);

// A value with no tone of its own is neutral on purpose, because these are the values of twenty enums and only some of them mean anything to the eye.
const ENUM_TONES = {
    active: "success",
    completed: "success",
    processed: "success",
    success: "success",
    pending: "warning",
    processing: "warning",
    partial: "warning",
    trialing: "info",
    grace_period: "warning",
    warning: "warning",
    paused: "warning",
    failed: "error",
    error: "error",
    blocked: "error",
    revoked: "error",
    canceled: "error",
    expired: "error",
    suspended: "error",
    administrator: "brand",
};

const enumLabel = computed(() => {
    const key = `enum.${props.column.enumName}.${value.value}`;

    return te(key) ? t(key) : value.value;
});

const referenceLabel = computed(() => {
    const related = value.value;

    return valueAt(related, props.column.referenceField) || related.name || related.title || related.code || `#${related.id}`;
});

const mediaUrl = computed(() => (value.value ? `${meta.storageBaseUrl}/${value.value}` : ""));

const isEmpty = computed(() => value.value === null || value.value === undefined || value.value === "");
</script>

<template>
    <span v-if="isEmpty" class="text-ink-faint">—</span>

    <span v-else-if="column.type === 'boolean'" class="inline-flex items-center gap-1.5" :class="value ? 'text-good' : 'text-ink-faint'">
        <AppIcon :name="value ? 'check' : 'close'" :size="16" />
        <span class="text-xs">{{ value ? $t("common.yes") : $t("common.no") }}</span>
    </span>

    <AppBadge v-else-if="column.type === 'enum'" :tone="ENUM_TONES[value] || 'neutral'">{{ enumLabel }}</AppBadge>

    <span v-else-if="column.type === 'datetime'" class="tabular-nums">{{ formatDateTime(value, locale, auth.timezone) }}</span>

    <span v-else-if="column.type === 'date'" class="tabular-nums">{{ formatDate(value, locale) }}</span>

    <span v-else-if="column.type === 'number'" class="tabular-nums">{{ value }}</span>

    <code v-else-if="column.type === 'code'" class="rounded bg-sunken px-1.5 py-0.5 font-mono text-xs text-ink-soft">{{ value }}</code>

    <span v-else-if="column.type === 'reference'">{{ referenceLabel }}</span>

    <span v-else-if="column.type === 'thumbnail'" class="inline-flex size-10 items-center justify-center overflow-hidden rounded-lg bg-sunken ring-1 ring-line">
        <img :src="mediaUrl" :alt="$t(column.label)" class="max-h-full max-w-full object-contain" />
    </span>

    <pre v-else-if="column.type === 'json'" class="max-h-64 overflow-auto rounded-lg bg-inverse p-3 font-mono text-xs text-ink">{{ JSON.stringify(value, null, 2) }}</pre>

    <!-- The body is markup an editor wrote and the panel is where an administrator is signed in, so it is previewed where a script of it reaches nothing. -->
    <iframe v-else-if="column.type === 'html'" :srcdoc="value" :title="$t(column.label)" sandbox class="h-72 w-full rounded-lg bg-raised ring-1 ring-line" />

    <a v-else-if="column.type === 'file'" class="inline-flex items-center gap-1.5 text-brand-ink hover:underline" :href="mediaUrl" target="_blank" rel="noreferrer">
        <AppIcon name="document" :size="14" />
        <span class="truncate">{{ value.split("/").pop() }}</span>
    </a>

    <span v-else :class="truncate || column.type === 'truncate' ? 'line-clamp-2' : ''">{{ value }}</span>
</template>
