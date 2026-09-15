<script setup>
defineProps({
    field: { type: Object, required: true },
    modelValue: { type: Boolean, default: false },
    error: { type: String, default: "" },
    inputId: { type: String, required: true },
});

const emit = defineEmits(["update:modelValue"]);
</script>

<template>
    <button
        :id="inputId"
        type="button"
        role="switch"
        :aria-checked="Boolean(modelValue)"
        :disabled="field.readOnly"
        class="inline-flex h-6 w-11 shrink-0 items-center rounded-full transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600 disabled:opacity-60"
        :class="[modelValue ? 'bg-brand-600' : 'bg-line-strong', error ? 'ring-2 ring-danger ring-offset-2' : '']"
        @click="emit('update:modelValue', !modelValue)"
    >
        <span class="size-4 rounded-full bg-raised shadow transition" :class="modelValue ? 'translate-x-6' : 'translate-x-1'" />
    </button>
</template>
