<script setup>
import AppShell from "@/components/layout/AppShell.vue";
import AppButton from "@/components/ui/AppButton.vue";
import EmptyState from "@/components/ui/EmptyState.vue";
</script>

<template>
    <AppShell>
        <template #header>
            <h1 class="text-base font-semibold text-ink">404</h1>
        </template>

        <div class="rounded-2xl bg-raised shadow-xs ring-1 ring-line">
            <EmptyState icon="warning" :message="$t('error.notFound')">
                <AppButton icon="arrowLeft" @click="$router.push({ name: 'dashboard' })">{{ $t("common.dashboard") }}</AppButton>
            </EmptyState>
        </div>
    </AppShell>
</template>
