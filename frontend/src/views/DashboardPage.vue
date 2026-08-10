<template>
  <div>
    <h1 class="text-2xl font-bold mb-6">Dashboard</h1>

    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
      <div class="bg-gray-900 border border-gray-800 rounded-xl p-5">
        <div class="flex items-center justify-between">
          <span class="text-sm text-gray-400">Templates</span>
          <span class="w-8 h-8 rounded-lg bg-brand-600/20 flex items-center justify-center text-sm">🎨</span>
        </div>
        <p class="text-2xl font-bold mt-2">{{ stats.templates }}</p>
        <p class="text-xs text-gray-500 mt-1">installed</p>
      </div>

      <div class="bg-gray-900 border border-gray-800 rounded-xl p-5">
        <div class="flex items-center justify-between">
          <span class="text-sm text-gray-400">Channels</span>
          <span class="w-8 h-8 rounded-lg bg-green-600/20 flex items-center justify-center text-sm">📡</span>
        </div>
        <p class="text-2xl font-bold mt-2">{{ stats.channels }} / {{ stats.channelTypes }}</p>
        <p class="text-xs text-gray-500 mt-1">active / types available</p>
      </div>

      <div class="bg-gray-900 border border-gray-800 rounded-xl p-5">
        <div class="flex items-center justify-between">
          <span class="text-sm text-gray-400">Jellyfin</span>
          <span class="w-8 h-8 rounded-lg flex items-center justify-center text-sm"
            :class="jellyfinConnected ? 'bg-green-600/20' : 'bg-red-600/20'">
            {{ jellyfinConnected ? '✅' : '❌' }}
          </span>
        </div>
        <p class="text-2xl font-bold mt-2" :class="jellyfinConnected ? 'text-green-400' : 'text-red-400'">
          {{ jellyfinConnected ? 'Connected' : 'Offline' }}
        </p>
        <p class="text-xs text-gray-500 mt-1">{{ jellyfinUrl || 'Not configured' }}</p>
      </div>

      <div class="bg-gray-900 border border-gray-800 rounded-xl p-5">
        <div class="flex items-center justify-between">
          <span class="text-sm text-gray-400">Send Newsletter</span>
          <span class="w-8 h-8 rounded-lg bg-amber-600/20 flex items-center justify-center text-sm">📨</span>
        </div>
        <button @click="triggerSend" :disabled="sending"
          class="mt-3 w-full rounded-lg bg-brand-600 px-3 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50 transition-colors">
          {{ sending ? 'Sending...' : 'Send Now' }}
        </button>
        <p v-if="sendResult" class="text-xs mt-2" :class="sendResult.success ? 'text-green-400' : 'text-red-400'">
          {{ sendResult.message }}
        </p>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div class="bg-gray-900 border border-gray-800 rounded-xl p-5">
        <h2 class="text-sm font-semibold text-gray-300 mb-4">Latest from Jellyfin</h2>
        <div v-if="latestLoading" class="text-gray-500 text-sm">Loading...</div>
        <div v-else-if="!latestItems.length" class="text-gray-500 text-sm">No recent items found.</div>
        <ul v-else class="space-y-2">
          <li v-for="item in latestItems.slice(0, 8)" :key="item.item_id"
            class="flex items-center gap-3 text-sm py-1.5">
            <span class="text-xs w-16 px-1.5 py-0.5 rounded text-center font-medium"
              :class="item.item_type === 'Movie' ? 'bg-blue-600/20 text-blue-400' : item.item_type === 'Series' ? 'bg-purple-600/20 text-purple-400' : 'bg-amber-600/20 text-amber-400'">
              {{ item.item_type }}
            </span>
            <span class="text-gray-200 truncate">{{ item.item_name }}</span>
            <span v-if="item.production_year" class="text-gray-500 text-xs ml-auto">{{ item.production_year }}</span>
          </li>
        </ul>
      </div>

      <div class="bg-gray-900 border border-gray-800 rounded-xl p-5">
        <h2 class="text-sm font-semibold text-gray-300 mb-4">Channels Overview</h2>
        <div v-if="channelsLoading" class="text-gray-500 text-sm">Loading...</div>
        <div v-else-if="!channelList.length" class="text-gray-500 text-sm">No channels configured yet.</div>
        <ul v-else class="space-y-2">
          <li v-for="ch in channelList" :key="ch.id"
            class="flex items-center gap-3 text-sm py-1.5">
            <span class="w-2 h-2 rounded-full" :class="ch.active ? 'bg-green-500' : 'bg-gray-600'"></span>
            <span class="text-gray-200">{{ ch.name }}</span>
            <span class="text-xs text-gray-500 px-1.5 py-0.5 rounded bg-gray-800">{{ ch.channel_type }}</span>
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from "vue";
import api from "../services/api";

const stats = reactive({ templates: 0, channels: 0, channelTypes: 0 });
const jellyfinConnected = ref(false);
const jellyfinUrl = ref("");
const sending = ref(false);
const sendResult = ref(null);
const latestLoading = ref(true);
const latestItems = ref([]);
const channelsLoading = ref(true);
const channelList = ref([]);

onMounted(async () => {
  const [tmplRes, chRes, chTypesRes, jfHealthRes, latestRes] = await Promise.allSettled([
    api.get("/templates"),
    api.get("/channels"),
    api.get("/channels/types"),
    api.get("/jellyfin/health"),
    api.get("/jellyfin/items/latest"),
  ]);

  if (tmplRes.status === "fulfilled") stats.templates = tmplRes.value.data.length;
  if (chRes.status === "fulfilled") stats.channels = chRes.value.data.filter(c => c.active).length;
  if (chTypesRes.status === "fulfilled") stats.channelTypes = chTypesRes.value.data.types?.length || 0;
  if (jfHealthRes.status === "fulfilled") {
    jellyfinConnected.value = jfHealthRes.value.data.connected;
    jellyfinUrl.value = jfHealthRes.value.data.url || "";
  }
  if (latestRes.status === "fulfilled") {
    latestItems.value = Array.isArray(latestRes.value.data) ? latestRes.value.data : latestRes.value.data?.items || [];
    latestLoading.value = false;
  } else {
    latestLoading.value = false;
  }

  if (chRes.status === "fulfilled") {
    channelList.value = chRes.value.data;
    channelsLoading.value = false;
  } else {
    channelsLoading.value = false;
  }
});

async function triggerSend() {
  sending.value = true;
  sendResult.value = null;
  try {
    const { data } = await api.post("/newsletter/send");
    sendResult.value = { success: true, message: `Sent to ${data.results?.length || 0} channels` };
  } catch (e) {
    sendResult.value = { success: false, message: e.response?.data?.detail || "Send failed" };
  } finally {
    sending.value = false;
  }
}
</script>
