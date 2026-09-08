<script setup lang="ts">
  /** Chip-styled dropdown - thin wrapper around Dropdown.vue's ARIA listbox. */
  import { useId } from 'vue'
  import Dropdown from './Dropdown.vue'

  const model = defineModel<string>({ required: true })
  defineProps<{ options: { value: string; label: string }[]; label: string }>()

  const labelId = useId()
  const buttonId = useId()
</script>

<template>
  <span :id="labelId" class="visually-hidden">{{ label }}</span>
  <Dropdown
    :model-value="model"
    @update:model-value="model = $event"
    :options="options"
    :label-id="labelId"
    :button-id="buttonId"
  />
</template>
