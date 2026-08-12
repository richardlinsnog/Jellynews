
<template>
  <div>
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-white">News</h1>
      <div v-if="!editing && !creating" class="flex items-center gap-2">
        <button
          v-if="selectedIds.length > 0"
          @click="sendSelected"
          :disabled="sendingSelected"
          class="px-4 py-2 bg-green-700 hover:bg-green-600 text-white rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
        >
          {{ sendingSelected ? 'Sending...' : `Send Selected (${selectedIds.length})` }}
        </button>
        <button
          @click="startCreate"
          class="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-medium transition-colors"
        >
          + New Article
        </button>
      </div>
    </div>

    <!-- Loading state -->
    <div v-if="loading" class="flex justify-center py-12">
      <div class="animate-spin h-8 w-8 border-2 border-indigo-500 border-t-transparent rounded-full" />
    </div>

    <!-- Error state -->
    <div v-else-if="loadError" class="bg-red-900/30 border border-red-800 rounded-lg p-4 text-red-300">
      {{ loadError }}
      <button @click="fetchNews" class="ml-2 underline">Retry</button>
    </div>

    <!-- News List -->
    <div v-else-if="!editing && !creating" class="space-y-4">
      <div v-if="news.length === 0" class="text-center py-12 text-gray-400">
        <p class="text-lg">No custom articles yet.</p>
        <p class="text-sm mt-1">Click "+ New Article" to write your first news piece.</p>
      </div>

      <div
        v-for="item in news"
        :key="item.id"
        class="bg-gray-800 rounded-lg border border-gray-700 p-5 hover:border-gray-600 transition-colors"
      >
        <div class="flex items-start gap-3">
          <input
            v-if="item.status !== 'sent'"
            type="checkbox"
            :value="item.id"
            v-model="selectedIds"
            class="mt-1.5 h-4 w-4 rounded border-gray-600 bg-gray-700 text-indigo-600 focus:ring-indigo-500"
          />
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 mb-1">
              <h3 class="text-lg font-semibold text-white truncate">{{ item.title }}</h3>
              <span
                :class="statusBadgeClass(item.status)"
                class="text-xs px-2 py-0.5 rounded-full font-medium"
              >
                {{ statusLabel(item.status) }}
              </span>
            </div>
            <p class="text-sm text-gray-400 line-clamp-2">{{ item.body_text || stripHtml(item.body_html) }}</p>
            <p class="text-xs text-gray-500 mt-2">
              {{ formatDate(item.created_at) }}
              <span v-if="item.updated_at">· updated {{ formatDate(item.updated_at) }}</span>
            </p>
          </div>
          <div class="flex items-center gap-1 shrink-0">
            <button @click="startEdit(item)" class="p-1.5 text-gray-400 hover:text-white hover:bg-gray-700 rounded transition-colors" title="Edit">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/></svg>
            </button>
            <button @click="confirmDelete(item)" class="p-1.5 text-gray-400 hover:text-red-400 hover:bg-gray-700 rounded transition-colors" title="Delete">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
            </button>
          </div>
        </div>
      </div>

      <!-- Pagination -->
      <div v-if="total > limit" class="flex items-center justify-center gap-2 pt-4">
        <button
          @click="page--; fetchNews()"
          :disabled="page <= 1"
          class="px-3 py-1 text-sm rounded bg-gray-800 text-gray-300 hover:bg-gray-700 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Previous
        </button>
        <span class="text-sm text-gray-400">Page {{ page }} of {{ Math.ceil(total / limit) }}</span>
        <button
          @click="page++; fetchNews()"
          :disabled="page * limit >= total"
          class="px-3 py-1 text-sm rounded bg-gray-800 text-gray-300 hover:bg-gray-700 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Next
        </button>
      </div>
    </div>

    <!-- Editor (Create / Edit) -->
    <div v-else class="bg-gray-800 rounded-lg border border-gray-700 p-6">
      <h2 class="text-lg font-semibold text-white mb-4">
        {{ creating ? 'New Article' : 'Edit Article' }}
      </h2>

      <div class="mb-4">
        <label class="block text-sm font-medium text-gray-300 mb-1">Title</label>
        <input
          v-model="form.title"
          type="text"
          maxlength="255"
          placeholder="Article title..."
          class="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
        <p class="text-xs text-gray-500 mt-1">{{ form.title.length }}/255</p>
      </div>

      <div class="mb-4">
        <label class="block text-sm font-medium text-gray-300 mb-1">Content</label>
        <div class="bg-gray-900 border border-gray-700 rounded-lg overflow-hidden">
          <EditorContent :editor="editor" class="prose prose-invert max-w-none min-h-[300px] p-4" />
        </div>
      </div>

      <div class="flex items-center gap-4 mb-6">
        <label class="text-sm font-medium text-gray-300">Status</label>
        <select
          v-model="form.status"
          class="px-3 py-1.5 bg-gray-900 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
        >
          <option v-for="s in STATUS_OPTIONS" :key="s" :value="s">{{ s }}</option>
        </select>
      </div>

      <div v-if="saveError" class="bg-red-900/30 border border-red-800 rounded-lg p-3 text-red-300 text-sm mb-4">
        {{ saveError }}
      </div>

      <div class="flex items-center gap-3">
        <button
          @click="save"
          :disabled="saving || !form.title.trim() || !editor || editor.isEmpty"
          class="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <span v-if="saving" class="inline-flex items-center gap-2">
            <span class="animate-spin h-3 w-3 border-2 border-white border-t-transparent rounded-full" />
            Saving...
          </span>
          <span v-else>{{ creating ? 'Create' : 'Save Changes' }}</span>
        </button>
        <button
          @click="cancelEdit"
          :disabled="saving"
          class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
        >
          Cancel
        </button>
      </div>
    </div>

    <!-- Delete confirmation toast -->
    <div
      v-if="deleting"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
    >
      <div class="bg-gray-800 rounded-lg border border-gray-700 p-6 max-w-sm w-full mx-4 shadow-xl">
        <h3 class="text-lg font-semibold text-white mb-2">Delete Article?</h3>
        <p class="text-sm text-gray-400 mb-4">This will permanently delete <strong class="text-white">{{ deleting.title }}</strong>. This action cannot be undone.</p>
        <div class="flex items-center justify-end gap-3">
          <button @click="deleting = null" class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded-lg text-sm transition-colors">Cancel</button>
          <button @click="doDelete" :disabled="deleteLoading" class="px-4 py-2 bg-red-700 hover:bg-red-600 text-white rounded-lg text-sm transition-colors disabled:opacity-50">
            <span v-if="deleteLoading">Deleting...</span>
            <span v-else>Delete</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { EditorContent, useEditor } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import Underline from '@tiptap/extension-underline'
import Link from '@tiptap/extension-link'
import Image from '@tiptap/extension-image'
import Placeholder from '@tiptap/extension-placeholder'
import api from '../services/api'

const news = ref([])
const total = ref(0)
const page = ref(1)
const limit = 50
const loading = ref(true)
const loadError = ref('')
const saveError = ref('')
const saving = ref(false)
const creating = ref(false)
const editing = ref(null)
const deleting = ref(null)
const deleteLoading = ref(false)

const STATUS_OPTIONS = ['draft', 'scheduled', 'sent']

const form = ref({ title: '', body_html: '', status: 'draft' })

const selectedIds = ref([])
const sendingSelected = ref(false)

const editor = useEditor({
  extensions: [
    StarterKit.configure({ table: false }),
    Underline,
    Link.configure({ openOnClick: false, HTMLAttributes: { rel: 'noopener noreferrer', target: '_blank' } }),
    Image.configure({ inline: true }),
    Placeholder.configure({ placeholder: 'Write your article content...' }),
  ],
  content: '',
  editorProps: {
    attributes: {
      class: 'outline-none',
    },
  },
})

function statusLabel(s) {
  return s.charAt(0).toUpperCase() + s.slice(1)
}

function statusBadgeClass(s) {
  if (s === 'sent') return 'bg-green-900/50 text-green-400'
  if (s === 'scheduled') return 'bg-blue-900/50 text-blue-400'
  return 'bg-yellow-900/50 text-yellow-400'
}

function stripHtml(html) {
  const div = document.createElement('div')
  div.innerHTML = html
  return div.textContent || ''
}

function formatDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

async function fetchNews() {
  loading.value = true
  loadError.value = ''
  try {
    const skip = (page.value - 1) * limit
    const { data } = await api.get(`/news?skip=${skip}&limit=${limit}`)
    news.value = data.items
    total.value = data.total
  } catch (e) {
    loadError.value = e.response?.data?.detail || e.message || 'Failed to load news'
  } finally {
    loading.value = false
  }
}

function startCreate() {
  creating.value = true
  editing.value = null
  form.value = { title: '', body_html: '', status: 'draft' }
  saveError.value = ''
  if (editor.value) {
    editor.value.commands.clearContent()
  }
}

function startEdit(item) {
  creating.value = false
  editing.value = item.id
  form.value = { title: item.title, body_html: item.body_html, status: item.status }
  saveError.value = ''
  if (editor.value) {
    editor.value.commands.setContent(item.body_html)
  }
}

function cancelEdit() {
  creating.value = false
  editing.value = null
  saveError.value = ''
  selectedIds.value = []
}

async function sendSelected() {
  if (!selectedIds.value.length) return
  sendingSelected.value = true
  saveError.value = ''
  try {
    for (const id of selectedIds.value) {
      await api.patch(`/news/${id}`, { status: 'scheduled' })
    }
    // Refresh the list
    await fetchNews()
    selectedIds.value = []
  } catch (e) {
    saveError.value = e.response?.data?.detail || e.message || 'Send failed'
  } finally {
    sendingSelected.value = false
  }
}

async function save() {
  if (!editor.value) return
  saving.value = true
  saveError.value = ''

  const payload = {
    title: form.value.title.trim(),
    body_html: editor.value.getHTML(),
    status: form.value.status,
  }

  try {
    if (creating.value) {
      const { data } = await api.post('/news', payload)
      news.value.unshift(data)
      total.value++
    } else {
      const { data } = await api.patch(`/news/${editing.value}`, payload)
      const idx = news.value.findIndex(n => n.id === editing.value)
      if (idx !== -1) news.value[idx] = data
    }

    creating.value = false
    editing.value = null
  } catch (e) {
    saveError.value = e.response?.data?.detail || e.message || 'Save failed'
  } finally {
    saving.value = false
  }
}

function confirmDelete(item) {
  deleting.value = item
}

async function doDelete() {
  if (!deleting.value) return
  deleteLoading.value = true
  try {
    await api.delete(`/news/${deleting.value.id}`)
    news.value = news.value.filter(n => n.id !== deleting.value.id)
    total.value = Math.max(0, total.value - 1)
  } catch (e) {
    saveError.value = e.response?.data?.detail || e.message || 'Delete failed'
  } finally {
    deleteLoading.value = false
    deleting.value = null
  }
}

onMounted(fetchNews)

// Re-hydrate editor after mount for any pending content
watch([creating, editing], () => {
  if (creating.value && editor.value) {
    editor.value.commands.clearContent()
  }
})

onBeforeUnmount(() => {
  editor.value?.destroy()
})
</script>
