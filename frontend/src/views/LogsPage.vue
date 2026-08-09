

<template>
  <div>
    <h1 class="text-2xl font-bold text-white mb-6">Delivery Logs</h1>

    <!-- Filters -->
    <div class="flex flex-wrap items-center gap-3 mb-6">
      <div class="flex items-center gap-2">
        <label class="text-sm text-gray-400">Channel:</label>
        <select
          v-model="filterChannel"
          @change="fetchLogs"
          class="px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
        >
          <option :value="null">All</option>
          <option v-for="ch in channels" :key="ch.id" :value="ch.id">{{ ch.name }}</option>
        </select>
      </div>
      <div class="flex items-center gap-2">
        <label class="text-sm text-gray-400">Status:</label>
        <select
          v-model="filterSuccess"
          @change="fetchLogs"
          class="px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
        >
          <option :value="null">All</option>
          <option :value="true">Success</option>
          <option :value="false">Failed</option>
        </select>
      </div>
      <button
        @click="refreshLogs"
        class="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded-lg text-sm transition-colors"
      >
        Refresh
      </button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="flex justify-center py-12">
      <div class="animate-spin h-8 w-8 border-2 border-indigo-500 border-t-transparent rounded-full" />
    </div>

    <!-- Error -->
    <div v-else-if="error" class="bg-red-900/30 border border-red-800 rounded-lg p-4 text-red-300">
      {{ error }}
      <button @click="fetchLogs" class="ml-2 underline">Retry</button>
    </div>

    <!-- Logs Table -->
    <div v-else-if="logs.length > 0" class="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full text-sm text-left">
          <thead class="bg-gray-750 border-b border-gray-700">
            <tr>
              <th class="px-4 py-3 text-gray-400 font-medium">ID</th>
              <th class="px-4 py-3 text-gray-400 font-medium">Channel</th>
              <th class="px-4 py-3 text-gray-400 font-medium">Status</th>
              <th class="px-4 py-3 text-gray-400 font-medium">Message</th>
              <th class="px-4 py-3 text-gray-400 font-medium">Date</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-700">
            <tr
              v-for="log in logs"
              :key="log.id"
              class="hover:bg-gray-750 transition-colors"
            >
              <td class="px-4 py-3 text-gray-400 font-mono text-xs">{{ log.id }}</td>
              <td class="px-4 py-3 text-gray-200">{{ getChannelName(log.channel_id) }}</td>
              <td class="px-4 py-3">
                <span
                  :class="log.success ? 'bg-green-900/50 text-green-400' : 'bg-red-900/50 text-red-400'"
                  class="text-xs px-2 py-0.5 rounded-full font-medium"
                >
                  {{ log.success ? 'Success' : 'Failed' }}
                </span>
              </td>
              <td class="px-4 py-3 text-gray-400 max-w-xs truncate" :title="log.status_message || ''">
                {{ log.status_message || '—' }}
              </td>
              <td class="px-4 py-3 text-gray-500 text-xs whitespace-nowrap">
                {{ formatDate(log.created_at) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Empty -->
    <div v-else class="text-center py-12 text-gray-400">
      <p class="text-lg">No delivery logs found.</p>
      <p class="text-sm mt-1">Logs appear here after newsletters are sent.</p>
    </div>

    <!-- Pagination -->
    <div v-if="total > limit" class="flex items-center justify-center gap-2 pt-6">
      <button
        @click="page--; fetchLogs()"
        :disabled="page <= 1"
        class="px-3 py-1 text-sm rounded bg-gray-800 text-gray-300 hover:bg-gray-700 disabled:opacity-40 disabled:cursor-not-allowed"
      >
        Previous
      </button>
      <span class="text-sm text-gray-400">Page {{ page }} of {{ Math.ceil(total / limit) }}</span>
      <button
        @click="page++; fetchLogs()"
        :disabled="page * limit >= total"
        class="px-3 py-1 text-sm rounded bg-gray-800 text-gray-300 hover:bg-gray-700 disabled:opacity-40 disabled:cursor-not-allowed"
      >
        Next
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../services/api'

const logs = ref([])
const total = ref(0)
const page = ref(1)
const limit = 50
const loading = ref(true)
const error = ref('')
const filterChannel = ref(null)
const filterSuccess = ref(null)
const channels = ref([])

function formatDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function getChannelName(id) {
  const ch = channels.value.find(c => c.id === id)
  return ch ? ch.name : `#${id}`
}

async function fetchChannels() {
  try {
    const { data } = await api.get('/api/v1/channels')
    channels.value = data.items || data || []
  } catch {
    // Non-blocking; logs still render with channel IDs
  }
}

async function fetchLogs() {
  loading.value = true
  error.value = ''
  try {
    const params = new URLSearchParams()
    params.set('skip', (page.value - 1) * limit)
    params.set('limit', limit)
    if (filterChannel.value) params.set('channel_id', filterChannel.value)
    if (filterSuccess.value !== null) params.set('success', filterSuccess.value.toString())

    const { data } = await api.get(`/api/v1/logs?${params.toString()}`)
    logs.value = data.items
    total.value = data.total
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || 'Failed to load logs'
  } finally {
    loading.value = false
  }
}

function refreshLogs() {
  page.value = 1
  fetchLogs()
}

onMounted(() => {
  fetchChannels()
  fetchLogs()
})
</script>

