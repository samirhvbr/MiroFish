<template>
  <div class="url-source">
    <label for="article-url">{{ $t('urlSource.urlLabel') }}</label>
    <div class="url-row">
      <input id="article-url" v-model="url" type="url" placeholder="https://example.org/article" :disabled="busy || disabled" @input="invalidateSource" />
      <button type="button" :disabled="!url.trim() || busy || disabled" @click="readArticle">{{ $t(reading ? 'urlSource.reading' : 'urlSource.read') }}</button>
    </div>
    <p class="hint">{{ $t('urlSource.scope') }}</p>
    <p v-if="error" role="alert" class="source-error">{{ error }}</p>

    <section v-if="source" class="source-preview" :aria-label="$t('urlSource.preview')">
      <h3>{{ source.title }}</h3>
      <a :href="source.url" target="_blank" rel="noopener noreferrer">{{ source.url }}</a>
      <p v-if="source.resolved_url !== source.url" class="hint">{{ $t('urlSource.resolvedUrl') }} {{ source.resolved_url }}</p>
      <p class="hint">{{ $t('urlSource.retrieved') }} {{ source.retrieved_at }} · {{ source.text.length }} {{ $t('urlSource.characters') }}</p>
      <details>
        <summary>{{ $t('urlSource.extractedText') }}</summary>
        <pre>{{ source.text }}</pre>
      </details>
      <label for="simulation-horizon">{{ $t('urlSource.horizon') }}</label>
      <input id="simulation-horizon" type="number" min="1" max="720" step="1" :value="horizon" :disabled="busy || disabled" @input="$emit('update:horizon', Number($event.target.value))" />
      <button type="button" :disabled="busy || disabled || !validHorizon" @click="generateDraft">{{ $t(drafting ? 'urlSource.drafting' : 'urlSource.generate') }}</button>
      <p class="hint">{{ $t('urlSource.reviewHint') }}</p>
      <div v-if="draft" class="draft-summary">
        <h4>{{ $t('urlSource.summary') }}</h4>
        <p>{{ draft.summary }}</p>
        <h4>{{ $t('urlSource.assumptions') }}</h4>
        <ul v-if="draft.assumptions.length"><li v-for="(item, index) in draft.assumptions" :key="index">{{ item }}</li></ul>
        <p v-else>{{ $t('urlSource.noAssumptions') }}</p>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { previewUrlSource, draftUrlPrompt } from '../api/graph'

const props = defineProps({ disabled: Boolean, horizon: { type: Number, default: 72 } })
const emit = defineEmits(['update:source', 'update:horizon', 'draft', 'busy'])
const url = ref('')
const source = ref(null)
const draft = ref(null)
const error = ref('')
const reading = ref(false)
const drafting = ref(false)
const busy = computed(() => reading.value || drafting.value)
const validHorizon = computed(() => Number.isInteger(props.horizon) && props.horizon >= 1 && props.horizon <= 720)

function invalidateSource() {
  source.value = null
  draft.value = null
  error.value = ''
  emit('update:source', null)
}

async function readArticle() {
  invalidateSource()
  reading.value = true
  emit('busy', true)
  try {
    const response = await previewUrlSource(url.value.trim())
    source.value = response.data
    emit('update:source', source.value)
  } catch (err) {
    error.value = err.message
  } finally {
    reading.value = false
    emit('busy', false)
  }
}

async function generateDraft() {
  if (!source.value || !validHorizon.value) return
  drafting.value = true
  error.value = ''
  emit('busy', true)
  try {
    const response = await draftUrlPrompt(source.value.source_id, props.horizon)
    draft.value = response.data
    emit('draft', response.data.prompt)
  } catch (err) {
    error.value = err.message
  } finally {
    drafting.value = false
    emit('busy', false)
  }
}
</script>

<style scoped>
.url-source { display: grid; gap: 10px; font-size: 13px; }
.url-row { display: flex; flex-wrap: wrap; gap: 8px; }
input { box-sizing: border-box; min-width: 0; padding: 10px; border: 1px solid #ccc; border-radius: 4px; font: inherit; }
.url-row input { flex: 1; min-width: 180px; }
button { padding: 10px 14px; border: 1px solid #ccc; border-radius: 4px; background: #f5f5f5; cursor: pointer; font: inherit; }
button:disabled { opacity: .5; cursor: default; }
button:hover:enabled { border-color: #ff4500; }
.hint { margin: 0; color: #666; font-size: 12px; line-height: 1.5; overflow-wrap: anywhere; }
.source-error { color: #b42318; margin: 0; }
.source-preview { display: grid; gap: 12px; padding: 14px; border: 1px solid #e5e5e5; border-radius: 4px; }
h3, h4, p { margin: 0; }
a { overflow-wrap: anywhere; color: #b33300; }
summary { cursor: pointer; }
pre { white-space: pre-wrap; overflow-wrap: anywhere; max-height: 240px; overflow-y: auto; font: inherit; line-height: 1.6; background: #f5f5f5; padding: 10px; }
#simulation-horizon { width: 100%; }
.draft-summary { display: grid; gap: 8px; line-height: 1.6; }
ul { padding-left: 20px; margin: 0; }
</style>
