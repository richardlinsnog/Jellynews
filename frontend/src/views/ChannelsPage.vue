<template>
  <div>
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold">Channels</h1>
      <button @click="showForm = true"
        class="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 transition-colors">
        + New Channel
      </button>
    </div>

    <div v-if="loading" class="text-gray-400 text-sm">Loading channels...</div>

    <div v-else-if="!channels.length" class="text-center py-16">
      <p class="text-gray-400 text-sm">No channels configured yet.</p>
      <button @click="showForm = true"
        class="mt-4 rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 transition-colors">
        + Create your first channel
      </button>
    </div>

    <div v-else class="space-y-3">
      <div v-for="ch in channels" :key="ch.id"
        class="bg-gray-900 border border-gray-800 rounded-xl p-5 flex items-center justify-between">
        <div class="flex items-center gap-4">
          <span class="w-3 h-3 rounded-full" :class="ch.active ? 'bg-green-500' : 'bg-gray-600'"></span>
          <div>
            <h3 class="font-medium text-gray-100">{{ ch.label }}</h3>
            <p class="text-xs text-gray-400">
              {{ ch.channel_type }}
              <span v-if="ch.template_id"> · template: {{ ch.template_id }}</span>
              <span> · {{ ch.language }}</span>
            </p>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <button @click="testChannel(ch)"
            class="rounded-lg border border-gray-700 px-3 py-1.5 text-xs font-medium text-gray-300 hover:bg-gray-800 transition-colors">
            {{ testingId === ch.id ? 'Testing...' : 'Test' }}
          </button>
          <button @click="editChannel(ch)"
            class="rounded-lg border border-gray-700 px-3 py-1.5 text-xs font-medium text-gray-300 hover:bg-gray-800 transition-colors">
            Edit
          </button>
          <button @click="deleteChannel(ch)"
            class="rounded-lg border border-red-800 px-3 py-1.5 text-xs font-medium text-red-400 hover:bg-red-900/20 transition-colors">
            Delete
          </button>
        </div>
      </div>
    </div>

    <!-- Test result toast -->
    <div v-if="testResult" class="fixed bottom-6 right-6 z-50 rounded-lg px-4 py-3 text-sm shadow-lg"
      :class="testResult.status === 'ok' ? 'bg-green-900/80 text-green-300 border border-green-700' : 'bg-red-900/80 text-red-300 border border-red-700'">
      {{ testResult.message }}
      <button @click="testResult = null" class="ml-3 text-gray-400 hover:text-white">&times;</button>
    </div>

    <!-- Create/Edit modal -->
    <div v-if="showForm" class="fixed inset-0 z-50 flex items-center justify-center bg-black/60" @click.self="closeForm">
      <div class="bg-gray-900 border border-gray-700 rounded-xl w-full max-w-lg m-4">
        <div class="flex items-center justify-between p-5 border-b border-gray-800">
          <h2 class="text-lg font-semibold">{{ editing ? 'Edit' : 'New' }} Channel</h2>
          <button @click="closeForm" class="text-gray-400 hover:text-gray-200 text-xl">&times;</button>
        </div>
        <form @submit.prevent="saveChannel" class="p-5 space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-300 mb-1">Type</label>
            <select v-model="form.channel_type" :disabled="!!editing" required
              class="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-100 focus:border-brand-500 focus:outline-none">
              <option v-for="t in channelTypes" :key="t" :value="t">{{ t }}</option>
            </select>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-300 mb-1">Name</label>
            <input v-model="form.label" type="text" required
              class="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-100 focus:border-brand-500 focus:outline-none" />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-300 mb-1">Template</label>
            <select v-model="form.template_id"
              class="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-100 focus:border-brand-500 focus:outline-none">
              <option value="">(default)</option>
              <option v-for="t in templates" :key="t.template_id" :value="t.template_id">{{ t.name }}</option>
            </select>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-300 mb-1">Language</label>
            <select v-model="form.language"
              class="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-100 focus:border-brand-500 focus:outline-none">
              <option value="en">English</option>
              <option value="pt">Português</option>
              <option value="es">Español</option>
            </select>
          </div>
          <div>
            <label class="flex items-center gap-2 text-sm text-gray-300">
              <input type="checkbox" v-model="form.active" class="rounded bg-gray-800 border-gray-700" />
              Active
            </label>
          </div>
          <div v-if="configKeys.length">
            <label class="block text-sm font-medium text-gray-300 mb-2">Configuration</label>
            <div v-for="key in configKeys" :key="key" class="mb-2">
              <label class="text-xs text-gray-400 block mb-0.5">{{ key }}</label>
              <input v-model="form.config[key]" type="password"
                class="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-100 focus:border-brand-500 focus:outline-none"
                :placeholder="editing ? '(leave empty to keep current)' : 'Enter value'" />
            </div>
          </div>
          <p v-if="formError" class="text-red-400 text-sm">{{ formError }}</p>
          <div class="flex gap-3 pt-2">
            <button type="button" @click="closeForm"
              class="flex-1 rounded-lg border border-gray-700 px-4 py-2.5 text-sm font-medium text-gray-300 hover:bg-gray-800">Cancel</button>
            <button type="submit" :disabled="saving"
              class="flex-1 rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50">
              {{ saving ? 'Saving...' : (editing ? 'Update' : 'Create') }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from "vue";
import api from "../services/api";

const channels = ref([]);
const channelTypes = ref([]);
const templates = ref([]);
const loading = ref(true);
const showForm = ref(false);
const editing = ref(null);
const saving = ref(false);
const formError = ref("");
const testingId = ref(null);
const testResult = ref(null);
const configKeys = ref([]);

const form = reactive({
  channel_type: "email",
  label: "",
  template_id: "",
  language: "en",
  active: true,
  config: {},
});

onMounted(async () => {
  const [chRes, typesRes, tmpRes] = await Promise.allSettled([
    api.get("/channels"),
    api.get("/channels/types"),
    api.get("/templates"),
  ]);
  if (chRes.status === "fulfilled") channels.value = chRes.value.data;
  if (typesRes.status === "fulfilled") channelTypes.value = typesRes.value.data.available_types || [];
  if (tmpRes.status === "fulfilled") templates.value = tmpRes.value.data;
  loading.value = false;
});

function resetForm() {
  form.channel_type = "email";
  form.label = "";
  form.template_id = "";
  form.language = "en";
  form.active = true;
  form.config = {};
  formError.value = "";
  editing.value = null;
}

function closeForm() {
  showForm.value = false;
  resetForm();
}

function editChannel(ch) {
  editing.value = ch;
  form.channel_type = ch.channel_type;
  form.label = ch.label;
  form.template_id = ch.template_id || "";
  form.language = ch.language;
  form.active = ch.active;
  form.config = {};
  formError.value = "";
  showForm.value = true;
}

async function saveChannel() {
  saving.value = true;
  formError.value = "";
  try {
    const payload = {
      channel_type: form.channel_type,
      label: form.label,
      config: form.config,
      active: form.active,
      template_id: form.template_id || null,
      language: form.language,
    };
    if (editing.value) {
      const cleanPayload = { ...payload };
      if (!Object.keys(form.config).length) delete cleanPayload.config;
      await api.patch(`/channels/${editing.value.id}`, cleanPayload);
    } else {
      await api.post("/channels", payload);
    }
    const { data } = await api.get("/channels");
    channels.value = data;
    closeForm();
  } catch (e) {
    formError.value = e.response?.data?.detail || "Failed to save channel";
  } finally {
    saving.value = false;
  }
}

async function testChannel(ch) {
  testingId.value = ch.id;
  try {
    const { data } = await api.post(`/channels/${ch.id}/test`);
    testResult.value = data;
  } catch (e) {
    testResult.value = { status: "error", message: e.response?.data?.detail || "Test failed" };
  } finally {
    testingId.value = null;
  }
}

async function deleteChannel(ch) {
  if (!confirm(`Delete channel "${ch.label}"? This cannot be undone.`)) return;
  try {
    await api.delete(`/channels/${ch.id}`);
    const { data } = await api.get("/channels");
    channels.value = data;
  } catch (e) {
    alert(e.response?.data?.detail || "Failed to delete channel");
  }
}
</script>
