<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, useId, watch } from "vue";
import { useI18n } from "vue-i18n";

import { names } from "../../support/refusal.js";
import AppIcon from "../ui/AppIcon.vue";
import { api } from "@/api/client";
import { isWaiting, narrowingFilters, parentsOf } from "@/support/dependencies";
import { newest } from "@/support/latest";
import { sortByLabel } from "@/support/sorting";

const SEARCH_DELAY = 250;
const PANEL_HEIGHT = 280;

const props = defineProps({
    field: { type: Object, required: true },
    modelValue: { type: [Number, String], default: null },
    values: { type: Object, default: () => ({}) },
    fields: { type: Array, default: () => [] },
    error: { type: String, default: "" },
    inputId: { type: String, required: true },
});

const emit = defineEmits(["update:modelValue"]);

const { t, locale } = useI18n();

const open = ref(false);
const term = ref("");
const options = ref([]);
const selected = ref(null);
const loading = ref(false);
const failure = ref("");
const root = ref(null);
const trigger = ref(null);
const panel = ref(null);
const searchBox = ref(null);
const panelId = useId();
const anchor = ref({ top: 0, left: 0, width: 0, above: false });

let timer = null;

const answers = newest();
const labels = newest();

const waiting = computed(() => isWaiting(props.field, props.values));
const filters = computed(() => narrowingFilters(props.field, props.values));

const parentLabel = computed(() => {
    const parent = props.fields.find((field) => field.name === parentsOf(props.field)[0]);

    return parent ? t(parent.label) : "";
});

// Typing and a level above moving overlap, and an earlier answer arriving later would list what nobody asked for.
async function search() {
    const attempt = answers.take();

    if (waiting.value) {
        options.value = [];

        return;
    }

    loading.value = true;
    failure.value = "";

    // A refusal is said where the options would be, because an empty list reads as a search that found nothing.
    try {
        const payload = await api.get(`/${props.field.resource}/lookup`, { search: term.value, limit: 20, ...filters.value });

        if (!answers.stale(attempt)) {
            options.value = sortByLabel(payload.items, locale.value);
        }
    } catch (error) {
        if (!answers.stale(attempt)) {
            options.value = [];
            failure.value = error.message;
        }
    } finally {
        if (!answers.stale(attempt)) {
            loading.value = false;
        }
    }
}

// The API names the value this field holds, so a record outside the first page of options is not read as its own number, and one it cannot name at all is gone.
async function loadSelected(id) {
    const attempt = labels.take();

    if (!id) {
        selected.value = null;

        return;
    }

    const named = await api.get(`/${props.field.resource}/lookup/${id}`).catch(() => ({ id, label: `#${id}` }));

    // The value can move while its name is on the way, and a late answer would draw a name over a value that is no longer this one.
    if (!labels.stale(attempt)) {
        selected.value = named;
    }
}

// The options live at the end of the page, so closing hands the keyboard back to the field it came from.
function close() {
    open.value = false;
    trigger.value?.focus();
}

function choose(option) {
    selected.value = option;
    emit("update:modelValue", option.id);
    close();
}

function clear() {
    selected.value = null;
    emit("update:modelValue", null);
}

// The panel is drawn outside the field so nothing clips it, so its position is measured and never inherited.
function place() {
    const box = root.value?.getBoundingClientRect();

    if (!box) {
        return;
    }

    const below = window.innerHeight - box.bottom;
    const above = below < PANEL_HEIGHT && box.top > below;

    anchor.value = { top: above ? box.top - PANEL_HEIGHT - 4 : box.bottom + 4, left: box.left, width: box.width, above };
}

function toggle() {
    if (props.field.readOnly || waiting.value) {
        return;
    }

    open.value = !open.value;

    if (open.value) {
        place();
        search();
        nextTick(() => searchBox.value?.focus());
    }
}

// The options are drawn at the end of the page, so tabbing past either end of them would leave the page instead of going back to the form.
function onPanelTab(event) {
    const reachable = [...panel.value.querySelectorAll("input, button")];
    const leaving = event.shiftKey ? document.activeElement === reachable[0] : document.activeElement === reachable[reachable.length - 1];

    if (leaving) {
        event.preventDefault();
        close();
    }
}

function onOutside(event) {
    const inside = root.value?.contains(event.target) || panel.value?.contains(event.target);

    if (!inside) {
        open.value = false;
    }
}

watch(term, () => {
    clearTimeout(timer);
    timer = setTimeout(search, SEARCH_DELAY);
});

watch(() => props.modelValue, loadSelected);

// The level above moved, so whatever is listed here no longer belongs to it.
watch(filters, () => {
    if (open.value) {
        search();
    }
});

function reposition() {
    if (open.value) {
        place();
    }
}

onMounted(() => {
    loadSelected(props.modelValue);
    document.addEventListener("click", onOutside);
    window.addEventListener("resize", reposition);
    window.addEventListener("scroll", reposition, true);
});

onBeforeUnmount(() => {
    clearTimeout(timer);
    document.removeEventListener("click", onOutside);
    window.removeEventListener("resize", reposition);
    window.removeEventListener("scroll", reposition, true);
});
</script>

<template>
    <div ref="root" class="relative">
        <button
            :id="inputId"
            ref="trigger"
            type="button"
            :disabled="field.readOnly || waiting"
            class="field-control flex items-center justify-between gap-2 text-left"
            :class="{ 'field-control-invalid': error }"
            :aria-expanded="open"
            aria-haspopup="dialog"
            :aria-controls="open ? panelId : undefined"
            v-bind="names(inputId, error)"
            @click="toggle"
        >
            <span :class="selected ? ['truncate text-ink', { 'pr-6': !field.readOnly }] : 'text-ink-faint'">{{ selected ? selected.label : waiting ? $t("common.selectFirst", { field: parentLabel }) : $t("common.select") }}</span>

            <AppIcon name="chevronDown" :size="16" class="shrink-0 text-ink-faint" />
        </button>

        <button v-if="selected && !field.readOnly" type="button" class="absolute top-1/2 right-9 -translate-y-1/2 rounded p-0.5 text-ink-faint transition hover:text-ink-muted" :aria-label="$t('action.clearValue')" @click="clear">
            <AppIcon name="close" :size="14" />
        </button>

        <Teleport to="body">
            <div
                v-if="open"
                :id="panelId"
                ref="panel"
                role="dialog"
                :aria-label="$t(field.label)"
                class="fixed z-50 overflow-hidden rounded-lg bg-raised shadow-lg ring-1 ring-line"
                :style="{ top: `${anchor.top}px`, left: `${anchor.left}px`, width: `${anchor.width}px` }"
                @keydown.esc.stop="close"
                @keydown.tab="onPanelTab"
            >
                <div class="border-b border-line p-2">
                    <input ref="searchBox" v-model="term" type="search" class="field-control h-8 text-xs" :aria-label="$t('action.search')" :placeholder="$t('common.typeToSearch')" />
                </div>

                <ul class="max-h-56 overflow-y-auto py-1 text-sm">
                    <li v-if="loading" class="px-3 py-2 text-xs text-ink-faint">{{ $t("common.loading") }}</li>
                    <li v-else-if="failure" class="px-3 py-2 text-xs text-danger" role="alert">{{ failure }}</li>
                    <li v-else-if="!options.length" class="px-3 py-2 text-xs text-ink-faint">{{ $t("common.noOptions") }}</li>

                    <li v-for="option in options" :key="option.id">
                        <button
                            type="button"
                            class="w-full px-3 py-2 text-left transition hover:bg-sunken focus-visible:bg-sunken focus-visible:outline-none"
                            :class="option.id === modelValue ? 'bg-lifted font-medium text-ink' : 'text-ink-soft'"
                            :aria-current="option.id === modelValue ? 'true' : undefined"
                            @click="choose(option)"
                        >
                            {{ option.label }}
                        </button>
                    </li>
                </ul>
            </div>
        </Teleport>
    </div>
</template>
