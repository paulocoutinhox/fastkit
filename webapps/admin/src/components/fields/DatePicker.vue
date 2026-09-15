<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";

import { names } from "../../support/refusal.js";
import AppButton from "../ui/AppButton.vue";
import AppIcon from "../ui/AppIcon.vue";
import { monthMatrix, monthName, pad, weekdayNames } from "@/support/datetime";

const HOURS = Array.from({ length: 24 }, (_, hour) => hour);
const MINUTES = Array.from({ length: 60 }, (_, minute) => minute);

const props = defineProps({
    modelValue: { type: String, default: "" },
    mode: { type: String, default: "date" },
    disabled: { type: Boolean, default: false },
    invalid: { type: Boolean, default: false },
    inputId: { type: String, required: true },
    display: { type: String, default: "" },
    today: { type: Object, required: true },
});

const emit = defineEmits(["update:modelValue"]);

const { locale } = useI18n();

const open = ref(false);
const root = ref(null);
const cursor = ref({ year: props.today.year, month: props.today.month });

const hasTime = computed(() => props.mode !== "date");
const weekdays = computed(() => weekdayNames(locale.value));
const weeks = computed(() => monthMatrix(cursor.value.year, cursor.value.month, locale.value));
const heading = computed(() => monthName(cursor.value.year, cursor.value.month, locale.value));

const selected = computed(() => {
    if (!props.modelValue) {
        return null;
    }

    const [date, time = "00:00"] = props.modelValue.split("T");
    const [year, month, day] = date.split("-");
    const [hour, minute] = time.split(":");

    return { year: Number(year), month: Number(month), day: Number(day), hour: Number(hour), minute: Number(minute) };
});

function build(parts) {
    const date = `${parts.year}-${pad(parts.month)}-${pad(parts.day)}`;

    return props.mode === "date" ? date : `${date}T${pad(parts.hour)}:${pad(parts.minute)}`;
}

function current() {
    return selected.value || { ...props.today, hour: props.mode === "datetime" ? props.today.hour : 0, minute: props.mode === "datetime" ? props.today.minute : 0 };
}

function chooseDay(day) {
    const base = current();
    emit("update:modelValue", build({ ...base, year: day.year, month: day.month, day: day.day }));

    if (!hasTime.value) {
        open.value = false;
    }
}

function chooseTime(unit, value) {
    emit("update:modelValue", build({ ...current(), [unit]: Number(value) }));
}

function isSelected(day) {
    return Boolean(selected.value) && selected.value.year === day.year && selected.value.month === day.month && selected.value.day === day.day;
}

function isToday(day) {
    return props.today.year === day.year && props.today.month === day.month && props.today.day === day.day;
}

function move(step) {
    const month = cursor.value.month + step;
    cursor.value = { year: cursor.value.year + Math.floor((month - 1) / 12), month: ((((month - 1) % 12) + 12) % 12) + 1 };
}

function pickNow() {
    emit("update:modelValue", build(props.today));
    open.value = false;
}

function clear() {
    emit("update:modelValue", "");
    open.value = false;
}

function toggle() {
    if (props.disabled) {
        return;
    }

    open.value = !open.value;
}

function onOutside(event) {
    if (root.value && !root.value.contains(event.target)) {
        open.value = false;
    }
}

watch(open, (value) => {
    if (value && selected.value && selected.value.year) {
        cursor.value = { year: selected.value.year, month: selected.value.month };
    }
});

onMounted(() => document.addEventListener("click", onOutside));
onBeforeUnmount(() => document.removeEventListener("click", onOutside));

// Escape closes the calendar and stops there, and a closed one lets it reach whatever holds the field, a dialog included.
function shut(event) {
    if (!open.value) {
        return;
    }

    open.value = false;
    event.stopPropagation();
}

// A keyboard that tabs past the calendar has left it, and a click on its own padding moves the focus nowhere and is not leaving.
function left(event) {
    if (event.relatedTarget && !root.value.contains(event.relatedTarget)) {
        open.value = false;
    }
}
</script>

<template>
    <div ref="root" class="relative" @keydown.esc="shut" @focusout="left">
        <button :id="inputId" type="button" :disabled="disabled" class="field-control flex items-center justify-between gap-2 text-left" :class="{ 'field-control-invalid': invalid }" :aria-expanded="open" v-bind="names(inputId, invalid)" @click="toggle">
            <span :class="display ? ['truncate text-ink', { 'pr-6': !disabled }] : 'text-ink-faint'">{{ display || $t("common.select") }}</span>

            <AppIcon name="calendar" :size="16" class="shrink-0 text-ink-faint" />
        </button>

        <!-- Clearing is a control of its own beside the trigger, because one drawn inside another button is one a keyboard never reaches. -->
        <button v-if="display && !disabled" type="button" class="absolute top-1/2 right-9 -translate-y-1/2 rounded p-0.5 text-ink-faint transition hover:text-ink-muted" :aria-label="$t('action.clearValue')" @click="clear">
            <AppIcon name="close" :size="14" />
        </button>

        <div v-if="open" class="absolute z-20 mt-1 w-full min-w-72 rounded-lg bg-raised p-3 shadow-lg ring-1 ring-line">
            <div>
                <div class="flex items-center justify-between gap-2 pb-2">
                    <button type="button" class="rounded-lg p-1.5 text-ink-muted transition hover:bg-sunken hover:text-ink" :aria-label="$t('action.previous')" @click="move(-1)"><AppIcon name="chevronLeft" :size="16" /></button>
                    <span class="text-sm font-medium text-ink capitalize">{{ heading }}</span>
                    <button type="button" class="rounded-lg p-1.5 text-ink-muted transition hover:bg-sunken hover:text-ink" :aria-label="$t('action.next')" @click="move(1)"><AppIcon name="chevronRight" :size="16" /></button>
                </div>

                <div class="grid grid-cols-7 gap-0.5 pb-1 text-center text-xs text-ink-faint">
                    <span v-for="(weekday, index) in weekdays" :key="index">{{ weekday }}</span>
                </div>

                <div v-for="(week, index) in weeks" :key="index" class="grid grid-cols-7 gap-0.5">
                    <button
                        v-for="day in week"
                        :key="`${day.year}-${day.month}-${day.day}`"
                        type="button"
                        class="rounded-lg py-1.5 text-sm transition"
                        :class="[isSelected(day) ? 'bg-action font-medium text-action-ink' : day.outside ? 'text-ink-faint hover:bg-sunken' : 'text-ink-soft hover:bg-sunken', isToday(day) && !isSelected(day) ? 'font-semibold text-ink' : '']"
                        @click="chooseDay(day)"
                    >
                        {{ day.day }}
                    </button>
                </div>
            </div>

            <div v-if="hasTime" class="mt-3 flex items-center gap-2 border-t border-line pt-3">
                <select class="field-control h-8 text-sm" :aria-label="$t('common.hour')" :value="selected ? selected.hour : today.hour" @change="chooseTime('hour', $event.target.value)">
                    <option v-for="hour in HOURS" :key="hour" :value="hour">{{ pad(hour) }}</option>
                </select>

                <span class="text-ink-faint">:</span>

                <select class="field-control h-8 text-sm" :aria-label="$t('common.minute')" :value="selected ? selected.minute : today.minute" @change="chooseTime('minute', $event.target.value)">
                    <option v-for="minute in MINUTES" :key="minute" :value="minute">{{ pad(minute) }}</option>
                </select>
            </div>

            <div class="mt-3 flex justify-between gap-2 border-t border-line pt-3">
                <AppButton variant="ghost" size="sm" @click="clear">{{ $t("action.reset") }}</AppButton>
                <AppButton variant="secondary" size="sm" @click="pickNow">{{ mode === "date" ? $t("common.today") : $t("common.now") }}</AppButton>
            </div>
        </div>
    </div>
</template>
