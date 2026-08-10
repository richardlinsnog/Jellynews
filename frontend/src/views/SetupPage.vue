<template>
  <div class="flex min-h-screen items-center justify-center bg-gray-950 px-4">
    <div class="w-full max-w-md">
      <div class="text-center mb-8">
        <h1 class="text-2xl font-bold tracking-tight">🍿 Welcome to JellyNews</h1>
        <p class="text-gray-400 mt-2 text-sm">Let's get your newsletter instance ready</p>
      </div>

      <div class="mb-8 flex justify-center gap-2">
        <div v-for="step in 3" :key="step"
          class="w-8 h-8 rounded-full flex items-center justify-center text-xs font-semibold transition-colors"
          :class="currentStep === step
            ? 'bg-brand-600 text-white'
            : currentStep > step
              ? 'bg-green-600/30 text-green-400 border border-green-600'
              : 'bg-gray-800 text-gray-500 border border-gray-700'">
          {{ currentStep > step ? '✓' : step }}
        </div>
      </div>

      <div v-if="statusLoading" class="text-center py-12">
        <p class="text-gray-400 text-sm">Checking instance status...</p>
      </div>

      <div v-else-if="!setupRequired && !setupDone" class="text-center py-12">
        <p class="text-gray-400">Setup already completed.</p>
        <router-link to="/login" class="text-brand-500 hover:underline text-sm mt-4 inline-block">Go to login</router-link>
      </div>

      <form v-else-if="!setupDone" @submit.prevent="handleSubmit" class="space-y-4">
        <!-- Step 1: Admin Account -->
        <template v-if="currentStep === 1">
          <div>
            <label for="username" class="block text-sm font-medium text-gray-300 mb-1">Admin Username</label>
            <input id="username" v-model="form.username" type="text" required minlength="3" maxlength="150"
              pattern="^[a-zA-Z0-9_-]+$" autocomplete="username"
              class="w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2.5 text-sm text-gray-100 focus:border-brand-500 focus:ring-1 focus:ring-brand-500 focus:outline-none" />
          </div>
          <div>
            <label for="password" class="block text-sm font-medium text-gray-300 mb-1">Password</label>
            <input id="password" v-model="form.password" type="password" required minlength="8" maxlength="128"
              autocomplete="new-password"
              class="w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2.5 text-sm text-gray-100 focus:border-brand-500 focus:ring-1 focus:ring-brand-500 focus:outline-none" />
            <p class="text-gray-500 text-xs mt-1">At least 8 characters</p>
          </div>
        </template>

        <!-- Step 2: Jellyfin Connection -->
        <template v-if="currentStep === 2">
          <div>
            <label for="jellyfin_url" class="block text-sm font-medium text-gray-300 mb-1">Jellyfin URL</label>
            <input id="jellyfin_url" v-model="form.jellyfin_url" type="url" placeholder="https://jellyfin.example.com"
              class="w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2.5 text-sm text-gray-100 placeholder-gray-500 focus:border-brand-500 focus:ring-1 focus:ring-brand-500 focus:outline-none" />
          </div>
          <div>
            <label for="jellyfin_key" class="block text-sm font-medium text-gray-300 mb-1">API Key</label>
            <input id="jellyfin_key" v-model="form.jellyfin_api_key" type="password" placeholder="Paste your Jellyfin API key"
              class="w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2.5 text-sm text-gray-100 placeholder-gray-500 focus:border-brand-500 focus:ring-1 focus:ring-brand-500 focus:outline-none" />
            <p class="text-gray-500 text-xs mt-1">Optional — can be configured later</p>
          </div>
          <button type="button" @click="testJellyfin" :disabled="testLoading || !form.jellyfin_url || !form.jellyfin_api_key"
            class="rounded-lg border border-gray-700 px-4 py-2 text-sm font-medium text-gray-300 hover:bg-gray-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
            {{ testLoading ? 'Testing…' : 'Test Connection' }}
          </button>
          <p v-if="testResult" class="text-sm" :class="testResult.ok ? 'text-green-400' : 'text-red-400'">
            <template v-if="testResult.ok">
              ✓ Connected — {{ testResult.server_name }} v{{ testResult.server_version }} ({{ testResult.latency_ms }}ms)
            </template>
            <template v-else>
              ✗ {{ testResult.error }}
            </template>
          </p>
        </template>

        <!-- Step 3: Confirm -->
        <template v-if="currentStep === 3">
          <div class="bg-gray-900 rounded-lg border border-gray-800 p-4 space-y-2 text-sm">
            <div class="flex justify-between"><span class="text-gray-400">Admin</span><span class="text-gray-100 font-medium">{{ form.username }}</span></div>
            <div class="flex justify-between"><span class="text-gray-400">Jellyfin</span><span class="text-gray-100">{{ form.jellyfin_url || '(skip for now)' }}</span></div>
          </div>
          <p class="text-xs text-gray-500 text-center">Your credentials are encrypted before being stored.</p>
        </template>

        <p v-if="error" class="text-red-400 text-sm">{{ error }}</p>

        <div class="flex gap-3 pt-2">
          <button v-if="currentStep > 1" type="button" @click="currentStep--"
            class="flex-1 rounded-lg border border-gray-700 px-4 py-2.5 text-sm font-medium text-gray-300 hover:bg-gray-800 transition-colors">
            Back
          </button>
          <button v-if="currentStep < 3" type="button" @click="currentStep++"
            class="flex-1 rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-brand-700 transition-colors">
            Next
          </button>
          <button v-if="currentStep === 3" type="submit" :disabled="loading"
            class="flex-1 rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50 transition-colors">
            {{ loading ? 'Setting up...' : 'Finish Setup' }}
          </button>
        </div>
      </form>

      <div v-else class="text-center py-12">
        <div class="w-16 h-16 rounded-full bg-green-600/20 flex items-center justify-center mx-auto mb-4">
          <span class="text-2xl">🍿</span>
        </div>
        <h2 class="text-xl font-semibold">All set!</h2>
        <p class="text-gray-400 text-sm mt-2">Your newsletter instance is ready.</p>
        <router-link to="/login"
          class="inline-block mt-6 rounded-lg bg-brand-600 px-6 py-2.5 text-sm font-semibold text-white hover:bg-brand-700 transition-colors">
          Go to Dashboard
        </router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from "vue";
import { useRouter } from "vue-router";
import axios from "axios";

const router = useRouter();

const currentStep = ref(1);
const statusLoading = ref(true);
const loading = ref(false);
const testLoading = ref(false);
const error = ref("");
const setupRequired = ref(false);
const setupDone = ref(false);
const testResult = ref(null);

const form = reactive({
  username: "",
  password: "",
  jellyfin_url: "",
  jellyfin_api_key: "",
});

onMounted(async () => {
  try {
    const { data } = await axios.get("/api/v1/setup/status");
    setupRequired.value = data.setup_required;
  } catch {
    setupRequired.value = false;
  } finally {
    statusLoading.value = false;
  }
});

async function testJellyfin() {
  testResult.value = null;
  testLoading.value = true;
  try {
    const { data } = await axios.post("/api/v1/setup/test-jellyfin", {
      jellyfin_url: form.jellyfin_url,
      jellyfin_api_key: form.jellyfin_api_key,
    });
    testResult.value = data;
  } catch (e) {
    testResult.value = { ok: false, error: e.response?.data?.detail || e.message || "Test failed" };
  } finally {
    testLoading.value = false;
  }
}

function extractError(e) {
  const detail = e.response?.data?.detail;
  if (!detail) return e.message || "Setup failed. Please try again.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    return detail.map((d) => `${d.loc?.join(".") || ""}: ${d.msg}`).join("; ");
  }
  return "Setup failed. Please try again.";
}

async function handleSubmit() {
  error.value = "";
  loading.value = true;
  try {
    const { data } = await axios.post("/api/v1/setup", form);
    setupDone.value = true;
    localStorage.setItem("access_token", data.access_token);
    localStorage.setItem("refresh_token", data.refresh_token);
  } catch (e) {
    error.value = extractError(e);
  } finally {
    loading.value = false;
  }
}
</script>
