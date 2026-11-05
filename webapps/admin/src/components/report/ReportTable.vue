<script setup>
const props = defineProps({
    columns: { type: Array, required: true },
    rows: { type: Array, required: true },
});

// A count and an amount are read down a column, so they line up by their last digit.
const FIGURES = new Set(["integer", "money"]);

function aligned(column) {
    return FIGURES.has(column.kind) ? "text-right tabular-nums whitespace-nowrap" : "";
}
</script>

<template>
    <div>
        <div class="hidden overflow-x-auto lg:block">
            <table class="w-full text-left text-sm">
                <thead class="border-b border-line text-xs tracking-wide text-ink-muted uppercase">
                    <tr>
                        <th v-for="column in props.columns" :key="column.key" scope="col" class="px-4 py-3 font-medium whitespace-nowrap first:pl-6 last:pr-6" :class="aligned(column)">{{ column.label }}</th>
                    </tr>
                </thead>

                <tbody class="divide-y divide-line">
                    <tr v-for="(row, index) in props.rows" :key="index">
                        <td v-for="column in props.columns" :key="column.key" class="px-4 py-3 align-top text-ink first:pl-6 last:pr-6" :class="aligned(column)">
                            <span v-if="row[column.key] === null" class="text-ink-faint">—</span>
                            <span v-else>{{ row[column.key] }}</span>
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>

        <ul class="divide-y divide-line lg:hidden">
            <li v-for="(row, index) in props.rows" :key="index" class="space-y-2 px-5 py-4">
                <div v-for="column in props.columns" :key="column.key" class="flex items-start justify-between gap-3">
                    <span class="text-xs font-medium tracking-wide text-ink-muted">{{ column.label }}</span>
                    <span class="min-w-0 text-right text-sm break-words" :class="row[column.key] === null ? 'text-ink-faint' : 'text-ink-soft'">{{ row[column.key] ?? "—" }}</span>
                </div>
            </li>
        </ul>
    </div>
</template>
