

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
        <button
          v-if="selectedIds.length > 0"
          @click="doBulkActivate"
          class="px-3 py-1.5 bg-green-700 hover:bg-green-600 text-white text-sm font-medium rounded-lg transition-colors"
        >
          Activate ({{ selectedIds.length }})
        </button>
        <button
          v-if="selectedIds.length > 0"
          @click="doBulkDeactivate"
          class="px-3 py-1.5 bg-gray-600 hover:bg-gray-500 text-white text-sm font-medium rounded-lg transition-colors"
        >
          Deactivate ({{ selectedIds.length }})
        </button>
        <button
          v-if="selectedIds.length > 0"
          @click="confirmBulkDelete"
          class="px-3 py-1.5 bg-red-700 hover:bg-red-600 text-white text-sm font-medium rounded-lg transition-colors"
        >
          Delete ({{ selectedIds.length }})
        </button>
      </div>

      <div class="flex items-center gap-3">
        <button
          @click="openForm(null)"
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
        <button
          @click="importJellyfinUsers"
          :disabled="importingJellyfin"
          class="px-4 py-1.5 bg-purple-600 hover:bg-purple-500 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
        >
          {{ importingJellyfin ? 'Importing...' : '🎬 Import/Sync Jellyfin Users' }}
        </button>
      </div>
    </div>

    <!-- Unified Form Modal (Add / Edit) -->
    <div v-if="showForm" class="fixed inset-0 z-50 grid place-items-center overflow-y-auto bg-black/60 py-8" @click.self="closeForm">
      <div class="bg-gray-800 rounded-xl shadow-2xl w-full max-w-md p-6 border border-gray-700 max-h-[90vh] overflow-y-auto m-4">
        <h2 class="text-lg font-semibold text-white mb-4">{{ editing ? 'Edit' : 'Add' }} Subscriber</h2>
        <form @submit.prevent="saveSubscriber">
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-sm text-gray-400 mb-1">Name</label>
              <input v-model="form.name" type="text" maxlength="255"
                class="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
            </div>
            <div>
              <label class="block text-sm text-gray-400 mb-1">Email</label>
              <input v-model="form.email" type="email" maxlength="320"
                class="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
            </div>
            <div>
              <label class="block text-sm text-gray-400 mb-1">Phone</label>
              <input v-model="form.phone" type="text" maxlength="60"
                class="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
            </div>
            <div>
              <label class="block text-sm text-gray-400 mb-1">Telegram Chat ID</label>
              <input v-model="form.telegram_chat_id" type="text" maxlength="120"
                class="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
            </div>
            <div class="col-span-2">
              <label class="block text-sm text-gray-400 mb-1">Tags <span class="text-gray-600">(comma-separated)</span></label>
              <input v-model="form.tags" type="text" maxlength="500" placeholder="e.g. testing, kids"
                class="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
            </div>
          </div>
          <label v-if="editing" class="flex items-center gap-2 text-sm text-gray-300 mt-3 mb-4">
            <input type="checkbox" v-model="form.active" class="rounded bg-gray-800 border-gray-700" />
            Active
          </label>
          <p v-if="formError" class="text-red-400 text-sm mb-3">{{ formError }}</p>
          <div class="flex justify-end gap-2">
            <button
              type="button"
              @click="closeForm"
              class="px-4 py-1.5 text-sm text-gray-300 hover:text-white transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              :disabled="saving"
              class="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
            >
              {{ saving ? 'Saving...' : (editing ? 'Save' : 'Add') }}
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- CSV Result / Jellyfin Result Modal -->
    <div v-if="csvResult" class="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div class="bg-gray-800 rounded-xl shadow-2xl w-full max-w-md p-6 border border-gray-700">
        <h2 class="text-lg font-semibold text-white mb-4">Import Results</h2>
        <div class="space-y-2 text-sm text-gray-300 mb-4">
          <p>✅ Imported: <span class="text-green-400 font-medium">{{ csvResult.imported }}</span></p>
          <p v-if="csvResult.updated != null">🔄 Updated: <span class="text-blue-400 font-medium">{{ csvResult.updated }}</span></p>
          <p>⏭️ Skipped: <span class="text-yellow-400 font-medium">{{ csvResult.skipped }}</span></p>
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
            <th class="py-3 px-2 w-8">
              <input type="checkbox" :checked="allSelected" @change="toggleAll" class="h-4 w-4 rounded border-gray-600 bg-gray-700 text-indigo-600" />
            </th>
            <th class="py-3 px-2">Name</th>
            <th class="py-3 px-2">Email</th>
            <th class="py-3 px-2">Phone</th>
            <th class="py-3 px-2">Telegram</th>
            <th class="py-3 px-2">Tags</th>
            <th class="py-3 px-2">Status</th>
            <th class="py-3 px-2 w-10"></th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="s in subscribers"
            :key="s.id"
            class="border-b border-gray-800 hover:bg-gray-750 transition-colors"
          >
            <td class="py-3 px-2">
              <input type="checkbox" :value="s.id" v-model="selectedIds" class="h-4 w-4 rounded border-gray-600 bg-gray-700 text-indigo-600" />
            </td>
            <td class="py-3 px-2 text-white truncate max-w-[140px]">{{ s.name || '—' }}</td>
            <td class="py-3 px-2 text-gray-400 truncate max-w-[180px]">{{ s.email || '—' }}</td>
            <td class="py-3 px-2 text-gray-400 truncate max-w-[120px]">{{ s.phone || '—' }}</td>
            <td class="py-3 px-2 text-gray-400 truncate max-w-[120px]">{{ s.telegram_chat_id || '—' }}</td>
            <td class="py-3 px-2 text-gray-400 truncate max-w-[140px]">
              <span v-if="s.tags" class="text-xs text-indigo-400">{{ s.tags }}</span>
              <span v-else class="text-gray-600">—</span>
            </td>
            <td class="py-3 px-2">
              <span
                :class="s.active ? 'bg-green-900/50 text-green-400 border-green-800' : 'bg-gray-700/50 text-gray-500 border-gray-600'"
                class="px-2 py-0.5 rounded-full text-xs font-medium border whitespace-nowrap"
              >
                {{ s.active ? 'Active' : 'Inactive' }}
              </span>
            </td>
            <td class="py-3 px-2 text-right">
              <div class="flex items-center gap-1 justify-end">
                <button
                  @click="openForm(s)"
                  class="text-gray-600 hover:text-blue-400 transition-colors text-xs"
                  title="Edit"
                >
                  ✏️
                </button>
                <button
                  @click="confirmDelete(s)"
                  class="text-gray-600 hover:text-red-400 transition-colors text-xs"
                  title="Delete"
                >
                  🗑️
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Bulk Delete Confirm -->
    <div v-if="bulkDeleting" class="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div class="bg-gray-800 rounded-xl shadow-2xl w-full max-w-sm p-6 border border-gray-700">
        <h2 class="text-lg font-semibold text-white mb-2">Delete Subscribers</h2>
        <p class="text-sm text-gray-400 mb-4">
          Permanently remove {{ selectedIds.length }} subscriber(s)?
        </p>
        <div class="flex justify-end gap-2">
          <button
            @click="bulkDeleting = false"
            class="px-4 py-1.5 text-sm text-gray-300 hover:text-white transition-colors"
          >
            Cancel
          </button>
          <button
            @click="doBulkDelete"
            class="px-4 py-1.5 bg-red-600 hover:bg-red-500 text-white text-sm font-medium rounded-lg transition-colors"
          >
            Delete {{ selectedIds.length }}
          </button>
        </div>
      </div>
    </div>

    <!-- Single Delete Confirm -->
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
import { ref, reactive, computed, onMounted } from 'vue'
import api from '../services/api.js'

const subscribers = ref([])
const total = ref(0)
const loading = ref(true)
const error = ref('')
const filterActive = ref(null)
const selectedIds = ref([])

const showForm = ref(false)
const editing = ref(null)
const saving = ref(false)
const formError = ref('')

const form = reactive({
  name: '',
  email: '',
  phone: '',
  telegram_chat_id: '',
  tags: '',
  active: true,
})

const csvResult = ref(null)
const deleting = ref(null)
const bulkDeleting = ref(false)
const importingJellyfin = ref(false)

const allSelected = computed(() => {
  return subscribers.value.length > 0 && selectedIds.value.length === subscribers.value.length
})

function toggleAll() {
  if (allSelected.value) {
    selectedIds.value = []
  } else {
    selectedIds.value = subscribers.value.map(s => s.id)
  }
}

function formatDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('en-US', {
    year: 'numeric', month: 'short', day: 'numeric',
  })
}



function resetForm() {
  form.name = ''
  form.email = ''
  form.phone = ''
  form.telegram_chat_id = ''
  form.tags = ''
  form.active = true
  formError.value = ''
  editing.value = null
}

function closeForm() {
  showForm.value = false
  resetForm()
}

function openForm(subscriber) {
  resetForm()
  if (subscriber) {
    editing.value = subscriber
    form.name = subscriber.name || ''
    form.email = subscriber.email || ''
    form.phone = subscriber.phone || ''
    form.telegram_chat_id = subscriber.telegram_chat_id || ''
    form.tags = subscriber.tags || ''
    form.active = subscriber.active
  }
  showForm.value = true
}

async function saveSubscriber() {
  saving.value = true
  formError.value = ''
  try {
    const payload = {
      name: form.name || null,
      email: form.email || null,
      phone: form.phone || null,
      telegram_chat_id: form.telegram_chat_id || null,
      tags: form.tags || null,
    }

    if (editing.value) {
      payload.active = form.active
      await api.patch(`/subscribers/${editing.value.id}`, payload)
    } else {
      await api.post('/subscribers', payload)
    }

    closeForm()
    await fetchSubscribers()
  } catch (e) {
    formError.value = e.response?.data?.detail || 'Failed to save subscriber'
  } finally {
    saving.value = false
  }
}

async function fetchSubscribers() {
  loading.value = true
  error.value = ''
  try {
    const params = new URLSearchParams()
    if (filterActive.value !== null) params.set('only_active', filterActive.value)
    params.set('limit', '500')
    const { data } = await api.get(`/subscribers?${params.toString()}`)
    subscribers.value = data.items
    total.value = data.total
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to load subscribers'
  } finally {
    loading.value = false
  }
}

async function handleCsvUpload(e) {
  const file = e.target.files[0]
  if (!file) return
  try {
    const formData = new FormData()
    formData.append('file', file)
    const { data } = await api.post('/subscribers/import', formData, {
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
    selectedIds.value = selectedIds.value.filter(id => id !== deleting.value.id)
    await fetchSubscribers()
  } catch (e) {
    deleting.value = null
  }
}

function confirmBulkDelete() {
  bulkDeleting.value = true
}

async function doBulkDelete() {
  if (!selectedIds.value.length) return
  try {
    await api.post('/subscribers/bulk-delete', selectedIds.value)
    bulkDeleting.value = false
    selectedIds.value = []
    await fetchSubscribers()
  } catch (e) {
    bulkDeleting.value = false
  }
}

async function doBulkActivate() {
  if (!selectedIds.value.length) return
  try {
    await api.post('/subscribers/bulk-activate', selectedIds.value)
    selectedIds.value = []
    await fetchSubscribers()
  } catch (e) {
    alert(e.response?.data?.detail || 'Failed to activate subscribers')
  }
}

async function doBulkDeactivate() {
  if (!selectedIds.value.length) return
  try {
    await api.post('/subscribers/bulk-deactivate', selectedIds.value)
    selectedIds.value = []
    await fetchSubscribers()
  } catch (e) {
    alert(e.response?.data?.detail || 'Failed to deactivate subscribers')
  }
}

async function importJellyfinUsers() {
  importingJellyfin.value = true
  try {
    const { data } = await api.post('/jellyfin/users/import')
    csvResult.value = {
      imported: data.imported,
      skipped: data.skipped,
      errors: [],
    }
  } catch (e) {
    csvResult.value = {
      imported: 0,
      skipped: 0,
      errors: [e.response?.data?.detail || 'Jellyfin import failed'],
    }
  } finally {
    importingJellyfin.value = false
  }
}

onMounted(fetchSubscribers)
</script>
