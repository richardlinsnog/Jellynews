<template>
  <div>
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold">Templates</h1>
      <button @click="reload" :disabled="reloading"
        class="rounded-lg border border-gray-700 px-4 py-2 text-sm font-medium text-gray-300 hover:bg-gray-800 disabled:opacity-50 transition-colors">
        {{ reloading ? 'Reloading...' : 'Reload registry' }}
      </button>
    </div>

    <div v-if="loading" class="text-gray-400 text-sm">Loading templates...</div>

    <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <div v-for="tpl in templates" :key="tpl.template_id"
        class="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden hover:border-gray-700 transition-colors cursor-pointer"
        @click="selectTemplate(tpl)">
        <div class="aspect-video bg-gray-800 flex items-center justify-center text-2xl">
          <span v-if="tpl.preview_image">{{ tpl.preview_image }}</span>
          <span v-else>🎨</span>
        </div>
        <div class="p-4">
          <div class="flex items-start justify-between">
            <div>
              <h3 class="font-semibold text-gray-100">{{ tpl.name }}</h3>
              <p class="text-xs text-gray-400 mt-0.5">by {{ tpl.author }} · v{{ tpl.version }}</p>
            </div>
            <span v-if="tpl.is_active" class="text-xs px-2 py-0.5 rounded bg-green-600/20 text-green-400 font-medium">Active</span>
          </div>
          <div class="flex flex-wrap gap-1 mt-3">
            <span v-for="ch in tpl.supports_channels" :key="ch"
              class="text-xs px-1.5 py-0.5 rounded bg-gray-800 text-gray-400">{{ ch }}</span>
          </div>
          <div class="flex items-center gap-2 mt-3 text-xs text-gray-500">
            <span v-if="tpl.is_builtin">📦 built-in</span>
            <span v-if="!tpl.is_verified" class="text-amber-400">⚠ unverified</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Detail modal -->
    <div v-if="selected" class="fixed inset-0 z-50 flex items-center justify-center bg-black/60" @click.self="selected = null">
      <div class="bg-gray-900 border border-gray-700 rounded-xl w-full max-w-3xl max-h-[85vh] overflow-y-auto m-4">
        <div class="flex items-center justify-between p-5 border-b border-gray-800">
          <h2 class="text-lg font-semibold">{{ selected.name }}</h2>
          <button @click="selected = null" class="text-gray-400 hover:text-gray-200 text-xl leading-none">&times;</button>
        </div>
        <div class="p-5 space-y-4">
          <div class="flex gap-4 text-sm text-gray-400">
            <span>by {{ selected.author }}</span>
            <span>v{{ selected.version }}</span>
            <span v-if="selected.is_builtin">📦 built-in</span>
            <span v-if="!selected.is_verified" class="text-amber-400">⚠ unverified</span>
          </div>
          <div>
            <label class="text-xs font-medium text-gray-400 uppercase tracking-wide">Channel</label>
            <select v-model="previewChannel" @change="renderPreview"
              class="ml-3 rounded-lg border border-gray-700 bg-gray-800 px-2 py-1 text-sm text-gray-200">
              <option v-for="ch in selected.supports_channels" :key="ch" :value="ch">{{ ch }}</option>
            </select>
            <button @click="renderPreview"
              class="ml-2 rounded-lg bg-brand-600 px-3 py-1 text-xs font-semibold text-white hover:bg-brand-700 transition-colors">
              Render preview
            </button>
          </div>
          <div v-if="previewLoading" class="text-sm text-gray-400">Rendering...</div>
          <div v-else-if="previewHtml" class="bg-gray-950 border border-gray-800 rounded-lg p-4 overflow-auto max-h-96">
            <div v-if="previewChannel === 'email'" v-html="previewHtml" class="text-sm"></div>
            <pre v-else class="text-sm text-gray-200 whitespace-pre-wrap font-mono">{{ previewHtml }}</pre>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import api from "../services/api";

const templates = ref([]);
const loading = ref(true);
const reloading = ref(false);
const selected = ref(null);
const previewChannel = ref("email");
const previewHtml = ref("");
const previewLoading = ref(false);

onMounted(async () => {
  try {
    const { data } = await api.get("/templates");
    templates.value = data;
  } finally {
    loading.value = false;
  }
});

async function reload() {
  reloading.value = true;
  try {
    const { data } = await api.post("/templates/reload");
    templates.value = data.templates || [];
    await loadTemplates();
  } finally {
    reloading.value = false;
  }
}

async function loadTemplates() {
  const { data } = await api.get("/templates");
  templates.value = data;
}

async function selectTemplate(tpl) {
  selected.value = tpl;
  previewChannel.value = tpl.supports_channels[0] || "email";
  previewHtml.value = "";
  if (previewChannel.value) await renderPreview();
}

async function renderPreview() {
  if (!selected.value) return;
  previewLoading.value = true;
  try {
    const { data } = await api.post(`/templates/${selected.value.template_id}/render`, {
      channel: previewChannel.value,
    });
    previewHtml.value = data.rendered;
  } catch (e) {
    previewHtml.value = "Error rendering template: " + (e.response?.data?.detail || e.message);
  } finally {
    previewLoading.value = false;
  }
}
</script>
