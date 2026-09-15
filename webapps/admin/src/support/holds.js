import { inject, onBeforeUnmount, provide, reactive } from "vue";

// A field that cannot be sent yet holds the form it sits in: a draft that is not JSON, a file still on its way up.
export const HOLDS = Symbol("holds");

export function provideHolds() {
    const holds = reactive(new Set());

    provide(HOLDS, holds);

    return holds;
}

export function useHold() {
    const holds = inject(HOLDS);
    const self = Symbol("hold");

    onBeforeUnmount(() => holds.delete(self));

    return (held) => (held ? holds.add(self) : holds.delete(self));
}
