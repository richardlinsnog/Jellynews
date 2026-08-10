

<template>
  <div>
    <h1 class="text-2xl font-bold text-white mb-6">Subscribers</h1>

    <!-- Toolbar -->
    <div class="flex flex-wrap items-center justify-between gap-4 mb-6">
      <div class="flex items-center gap-3">
        <select
          v-model="filterActive"
          @change="fetchSubscribers"
          class="px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
        >
          <option :value="null">All</option>
          <option :value="true">Active</option>
          <option :value="false">Inactive</option>
        </select>
        <span class="text-sm text-gray-400">{{ total }} total</span>
      </div>

      <div class="flex items-center gap-3">
        <button
          @click="showAdd = true"
          class="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium rounded-lg transition-colors"
        >
          + Add
        </button>
        <label
          class="px-4 py-1.5 bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium rounded-lg transition-colors cursor-pointer"
        >
          📄 Import CSV
          <input type="file" accept=".csv" class="hidden" @change="handleCsvUpload" />
        </label>
      </div>
    </div>

    <!-- Add Modal -->
    <div v-if="showAdd" class="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div class="bg-gray-800 rounded-xl shadow-2xl w-full max-w-md p-6 border border-gray-700">
        <h2 class="text-lg font-semibold text-white mb-4">Add Subscriber</h2>
        <form @submit.prevent="addSubscriber">
          <label class="block text-sm text-gray-400 mb-1">Type</label>
          <select
            v-model="newType"
            class="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 mb-3"
          >
            <option value="email">Email</option>
            <option value="telegram">Telegram</option>
          </select>
          <label class="block text-sm text-gray-400 mb-1">Destination</label>
          <input
            v-model="newDestination"
            type="text"
            required
            :placeholder="newType === 'email' ? 'email@example.com' : 'chat_id'"
            class="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 mb-4"
          />
          <p v-if="addError" class="text-red-400 text-sm mb-3">{{ addError }}</p>
          <div class="flex justify-end gap-2">
            <button
              type="button"
              @click="showAdd = false; addError = ''"
              class="px-4 py-1.5 text-sm text-gray-300 hover:text-white transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              :disabled="adding"
              class="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
            >
              {{ adding ? 'Adding...' : 'Add' }}
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- CSV Result Modal -->
    <div v-if="csvResult" class="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div class="bg-gray-800 rounded-xl shadow-2xl w-full max-w-md p-6 border border-gray-700">
        <h2 class="text-lg font-semibold text-white mb-4">Import Results</h2>
        <div class="space-y-2 text-sm text-gray-300 mb-4">
          <p>✅ Imported: <span class="text-green-400 font-medium">{{ csvResult.imported }}</span></p>
          <p>⏭️ Skipped (duplicates): <span class="text-yellow-400 font-medium">{{ csvResult.skipped }}</span></p>
          <p v-if="csvResult.errors.length">❌ Errors: <span class="text-red-400 font-medium">{{ csvResult.errors.length }}</span></p>
          <ul v-if="csvResult.errors.length" class="mt-2 max-h-32 overflow-y-auto space-y-1">
            <li v-for="(err, i) in csvResult.errors" :key="i" class="text-red-400 text-xs">{{ err }}</li>
          </ul>
        </div>
        <div class="flex justify-end">
          <button
            @click="csvResult = null; fetchSubscribers()"
            class="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium rounded-lg transition-colors"
          >
            OK
          </button>
        </div>
      </div>
    </div>

    <!-- Table -->
    <div v-if="loading" class="text-gray-400 text-sm py-8 text-center">Loading...</div>
    <div v-else-if="error" class="text-red-400 text-sm py-8 text-center">{{ error }}</div>
    <div v-else-if="!subscribers.length" class="text-gray-500 text-sm py-8 text-center">
      No subscribers yet.
    </div>
    <div v-else class="overflow-x-auto">
      <table class="w-full text-sm text-left text-gray-300">
        <thead class="text-xs uppercase text-gray-500 border-b border-gray-700">
          <tr>
            <th class="py-3 px-4">Type</th>
            <th class="py-3 px-4">Destination</th>
            <th class="py-3 px-4">Status</th>
            <th class="py-3 px-4">Added</th>
            <th class="py-3 px-4">Unsubscribed</th>
            <th class="py-3 px-4 w-10"></th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="s in subscribers"
            :key="s.id"
            class="border-b border-gray-800 hover:bg-gray-750 transition-colors"
          >
            <td class="py-3 px-4">
              <span class="px-2 py-0.5 rounded-full text-xs font-medium border bg-indigo-900/50 text-indigo-400 border-indigo-800">
                {{ s.destination_type || 'email' }}
              </span>
            </td>
            <td class="py-3 px-4 font-medium text-white">{{ s.destination }}</td>
            <td class="py-3 px-4">
              <span
                :class="s.active ? 'bg-green-900/50 text-green-400 border-green-800' : 'bg-gray-700/50 text-gray-500 border-gray-600'"
                class="px-2 py-0.5 rounded-full text-xs font-medium border"
              >
                {{ s.active ? 'Active' : 'Unsubscribed' }}
              </span>
            </td>
            <td class="py-3 px-4 text-gray-500">{{ formatDate(s.created_at) }}</td>
            <td class="py-3 px-4 text-gray-500">{{ s.unsubscribed_at ? formatDate(s.unsubscribed_at) : '—' }}</td>
            <td class="py-3 px-4 text-right">
              <button
                @click="confirmDelete(s)"
                class="text-gray-600 hover:text-red-400 transition-colors text-xs"
                title="Delete"
              >
                🗑️
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Delete Confirm -->
    <div v-if="deleting" class="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div class="bg-gray-800 rounded-xl shadow-2xl w-full max-w-sm p-6 border border-gray-700">
        <h2 class="text-lg font-semibold text-white mb-2">Delete Subscriber</h2>
        <p class="text-sm text-gray-400 mb-4">
          Remove <span class="text-white font-medium">{{ deleting.destination }}</span>?
        </p>
        <div class="flex justify-end gap-2">
          <button
            @click="deleting = null"
            class="px-4 py-1.5 text-sm text-gray-300 hover:text-white transition-colors"
          >
            Cancel
          </button>
          <button
            @click="doDelete"
            class="px-4 py-1.5 bg-red-600 hover:bg-red-500 text-white text-sm font-medium rounded-lg transition-colors"
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../services/api.js'

const subscribers = ref([])
const total = ref(0)
const loading = ref(true)
const error = ref('')
const filterActive = ref(null)

const showAdd = ref(false)
const newType = ref('email')
const newDestination = ref('')
const adding = ref(false)
const addError = ref('')

const csvResult = ref(null)
const deleting = ref(null)

function formatDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('en-US', {
    year: 'numeric', month: 'short', day: 'numeric',
  })
}

async function fetchSubscribers() {
  loading.value = true
  error.value = ''
  try {
    const params = new URLSearchParams()
    if (filterActive.value !== null) params.set('only_active', filterActive.value)
    params.set('limit', '200')
    const { data } = await api.get(`/subscribers?${params.toString()}`)
    subscribers.value = data.items
    total.value = data.total
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to load subscribers'
  } finally {
    loading.value = false
  }
}

async function addSubscriber() {
  adding.value = true
  addError.value = ''
  try {
    await api.post('/subscribers', {
      destination_type: newType.value,
      destination: newDestination.value.trim(),
    })
    showAdd.value = false
    newDestination.value = ''
    newType.value = 'email'
    await fetchSubscribers()
  } catch (e) {
    addError.value = e.response?.data?.detail || 'Failed to add subscriber'
  } finally {
    adding.value = false
  }
}

async function handleCsvUpload(e) {
  const file = e.target.files[0]
  if (!file) return
  try {
    const form = new FormData()
    form.append('file', file)
    const { data } = await api.post('/subscribers/import', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    csvResult.value = data
  } catch (e) {
    csvResult.value = {
      imported: 0,
      skipped: 0,
      errors: [e.response?.data?.detail || 'Import failed'],
    }
  } finally {
    e.target.value = ''
  }
}

function confirmDelete(s) {
  deleting.value = s
}

async function doDelete() {
  if (!deleting.value) return
  try {
    await api.delete(`/subscribers/${deleting.value.id}`)
    deleting.value = null
    await fetchSubscribers()
  } catch (e) {
    addError.value = e.response?.data?.detail || 'Failed to delete'
    deleting.value = null
  }
}

onMounted(fetchSubscribers)
</script>
