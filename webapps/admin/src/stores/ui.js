import { defineStore } from "pinia";
import { ref } from "vue";

let sequence = 0;

export const TOAST_TIMEOUT = 4000;

export const useUiStore = defineStore("ui", () => {
    const toasts = ref([]);
    const sidebarOpen = ref(false);

    // The panel draws nothing of itself until it knows what this account reaches, so no menu is ever shown and then taken away.
    const booting = ref(false);

    // What stopped it from finding out, because a panel that cannot start has to say so rather than stay blank.
    const bootFailure = ref("");

    function notify(tone, message) {
        sequence += 1;

        const toast = { id: sequence, tone, message };
        toasts.value.push(toast);

        setTimeout(() => dismiss(toast.id), TOAST_TIMEOUT);

        return toast.id;
    }

    function dismiss(id) {
        toasts.value = toasts.value.filter((toast) => toast.id !== id);
    }

    function toggleSidebar(value) {
        sidebarOpen.value = value === undefined ? !sidebarOpen.value : value;
    }

    return { toasts, sidebarOpen, booting, bootFailure, dismiss, toggleSidebar, success: (message) => notify("success", message), error: (message) => notify("error", message), info: (message) => notify("info", message) };
});
