<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
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
const root = ref(null);
const panel = ref(null);
const anchor = ref({ top: 0, left: 0, width: 0, above: false });

let timer = null;

const answers = newest();

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

    try {
        const payload = await api.get(`/${props.field.resource}/lookup`, { search: term.value, limit: 20, ...filters.value });

        if (!answers.stale(attempt)) {
            options.value = sortByLabel(payload.items, locale.value);
        }
    } finally {
        if (!answers.stale(attempt)) {
            loading.value = false;
        }
    }
}

// The API names the value this field holds, so a record outside the first page of options is not read as its own number, and one it cannot name at all is gone.
async function loadSelected(id) {
    if (!id) {
        selected.value = null;

        return;
    }

    selected.value = await api.get(`/${props.field.resource}/lookup/${id}`).catch(() => ({ id, label: `#${id}` }));
}

function choose(option) {
    selected.value = option;
    open.value = false;
    emit("update:modelValue", option.id);
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
        <button :id="inputId" type="button" :disabled="field.readOnly || waiting" class="field-control flex items-center justify-between gap-2 text-left" :class="{ 'field-control-invalid': error }" v-bind="names(inputId, error)" @click="toggle">
            <span :class="selected ? 'truncate text-ink' : 'text-ink-faint'">{{ selected ? selected.label : waiting ? $t("common.selectFirst", { field: parentLabel }) : $t("common.select") }}</span>

            <span class="flex shrink-0 items-center gap-1">
                <AppIcon v-if="selected && !field.readOnly" name="close" :size="14" class="text-ink-faint hover:text-ink-muted" @click.stop="clear" />
                <AppIcon name="chevronDown" :size="16" class="text-ink-faint" />
            </span>
        </button>

        <Teleport to="body">
            <div v-if="open" ref="panel" class="fixed z-50 overflow-hidden rounded-lg bg-raised shadow-lg ring-1 ring-line" :style="{ top: `${anchor.top}px`, left: `${anchor.left}px`, width: `${anchor.width}px` }">
                <div class="border-b border-line p-2">
                    <input v-model="term" type="search" class="field-control py-1.5 text-xs" :aria-label="$t('common.search')" :placeholder="$t('common.typeToSearch')" />
                </div>

                <ul class="max-h-56 overflow-y-auto py-1 text-sm">
                    <li v-if="loading" class="px-3 py-2 text-xs text-ink-faint">{{ $t("common.loading") }}</li>
                    <li v-else-if="!options.length" class="px-3 py-2 text-xs text-ink-faint">{{ $t("common.noOptions") }}</li>

                    <li v-for="option in options" :key="option.id">
                        <button type="button" class="w-full px-3 py-2 text-left transition hover:bg-sunken" :class="option.id === modelValue ? 'bg-brand-50 text-brand-ink' : 'text-ink-soft'" @click="choose(option)">
                            {{ option.label }}
                        </button>
                    </li>
                </ul>
            </div>
        </Teleport>
    </div>
</template>
