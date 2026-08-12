

<template>
  <div>
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold">Server Settings</h1>
    </div>

    <div class="bg-gray-900 border border-gray-800 rounded-xl p-6 max-w-2xl">
      <h2 class="text-lg font-semibold mb-4">Jellyfin Server</h2>

      <div v-if="loading" class="text-gray-400 text-sm">Loading...</div>

      <form v-else @submit.prevent="saveSettings" class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-gray-300 mb-1">Server URL</label>
          <input v-model="form.jellyfin_url" type="text" placeholder="https://jellyfin.example.com"
            class="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-100 focus:border-brand-500 focus:outline-none" />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-300 mb-1">API Key</label>
          <input v-model="form.jellyfin_api_key" type="password"
            :placeholder="apiKeyConfigured ? '(leave empty to keep current)' : 'Enter API key'"
            class="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-100 focus:border-brand-500 focus:outline-none" />
        </div>

        <div class="flex gap-3">
          <button type="button" @click="testConnection"
            :disabled="testing"
            class="rounded-lg border border-gray-700 px-4 py-2.5 text-sm font-medium text-gray-300 hover:bg-gray-800 disabled:opacity-50">
            {{ testing ? 'Testing...' : 'Test Connection' }}
          </button>
          <button type="submit" :disabled="saving"
            class="rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50">
            {{ saving ? 'Saving...' : 'Save' }}
          </button>
        </div>

        <div v-if="testResult" class="mt-3 text-sm rounded-lg px-4 py-3"
          :class="testResult.ok ? 'bg-green-900/40 text-green-300 border border-green-700' : 'bg-red-900/40 text-red-300 border border-red-700'">
          <template v-if="testResult.ok">
            Connected: {{ testResult.server_name }} (v{{ testResult.server_version }}) — {{ testResult.latency_ms }}ms
          </template>
          <template v-else>
            {{ testResult.error }}
          </template>
        </div>

        <p v-if="saveMessage" class="text-green-400 text-sm">{{ saveMessage }}</p>
        <p v-if="errorMessage" class="text-red-400 text-sm">{{ errorMessage }}</p>
      </form>
    </div>

    <!-- Branding Logo -->
    <div class="bg-gray-900 border border-gray-800 rounded-xl p-6 max-w-2xl mt-6">
      <h2 class="text-lg font-semibold mb-4">Branding Logo</h2>
      <p class="text-sm text-gray-400 mb-4">Upload a custom logo for newsletter headers (PNG or JPEG). If none is set, the Jellyfin server logo will be used (if available).</p>

      <div v-if="logoPreview" class="mb-4 flex items-center gap-4">
        <img :src="logoPreview" alt="Logo preview" class="h-12 object-contain rounded bg-gray-800 p-1" />
        <button @click="removeLogo" :disabled="logoUploading"
          class="text-xs text-red-400 hover:text-red-300 disabled:opacity-50">
          {{ logoUploading ? 'Removing...' : 'Remove' }}
        </button>
      </div>

      <div class="flex items-center gap-3">
        <label class="cursor-pointer rounded-lg border border-gray-700 px-4 py-2 text-sm text-gray-300 hover:bg-gray-800 transition-colors">
          {{ logoPreview ? 'Change Logo' : 'Upload Logo' }}
          <input type="file" accept="image/png,image/jpeg" class="hidden" @change="onLogoSelected" />
        </label>
        <span v-if="logoMessage" class="text-xs" :class="logoError ? 'text-red-400' : 'text-green-400'">{{ logoMessage }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from "vue";
import api from "../services/api";

const loading = ref(true);
const saving = ref(false);
const testing = ref(false);
const testResult = ref(null);
const saveMessage = ref("");
const errorMessage = ref("");
const apiKeyConfigured = ref(false);

const form = reactive({
  jellyfin_url: "",
  jellyfin_api_key: "",
});

// Logo state
const logoPreview = ref("");
const logoUploading = ref(false);
const logoMessage = ref("");
const logoError = ref(false);

onMounted(async () => {
  try {
    const { data } = await api.get("/settings/jellyfin");
    form.jellyfin_url = data.jellyfin_url || "";
    apiKeyConfigured.value = data.jellyfin_api_key_configured;
  } catch (e) {
    errorMessage.value = e.response?.data?.detail || "Failed to load settings";
  } finally {
    loading.value = false;
  }
  checkLogoStatus();
});

async function checkLogoStatus() {
  try {
    const { data } = await api.get("/settings/logo/status");
    if (data.has_logo) {
      logoPreview.value = "/api/v1/settings/logo?" + Date.now();
    }
  } catch { /* logo not available */ }
}

function onLogoSelected(e) {
  const file = e.target.files?.[0];
  if (!file) return;
  logoUploading.value = true;
  logoMessage.value = "";
  logoError.value = false;

  const formData = new FormData();
  formData.append("file", file);

  api.post("/settings/logo", formData, { headers: { "Content-Type": "multipart/form-data" } })
    .then(() => {
      logoPreview.value = "/api/v1/settings/logo?" + Date.now();
      logoMessage.value = "Logo uploaded.";
    })
    .catch((err) => {
      logoError.value = true;
      logoMessage.value = err.response?.data?.detail || "Upload failed";
    })
    .finally(() => { logoUploading.value = false; });
}

async function removeLogo() {
  logoUploading.value = true;
  logoMessage.value = "";
  logoError.value = false;
  try {
    await api.delete("/settings/logo");
    logoPreview.value = "";
    logoMessage.value = "Logo removed.";
  } catch (e) {
    logoError.value = true;
    logoMessage.value = e.response?.data?.detail || "Failed to remove";
  } finally {
    logoUploading.value = false;
  }
}

async function testConnection() {
  testing.value = true;
  testResult.value = null;
  try {
    const { data } = await api.post("/setup/test-jellyfin", {
      jellyfin_url: form.jellyfin_url,
      jellyfin_api_key: form.jellyfin_api_key || "placeholder",
    });
    testResult.value = data;
  } catch (e) {
    testResult.value = { ok: false, error: e.response?.data?.detail || "Test failed" };
  } finally {
    testing.value = false;
  }
}

async function saveSettings() {
  saving.value = true;
  saveMessage.value = "";
  errorMessage.value = "";
  try {
    await api.put("/settings/jellyfin", {
      jellyfin_url: form.jellyfin_url,
      jellyfin_api_key: form.jellyfin_api_key,
    });
    apiKeyConfigured.value = apiKeyConfigured.value || !!form.jellyfin_api_key;
    form.jellyfin_api_key = "";
    saveMessage.value = "Settings saved successfully.";
  } catch (e) {
    errorMessage.value = e.response?.data?.detail || "Failed to save settings";
  } finally {
    saving.value = false;
  }
}
</script>

