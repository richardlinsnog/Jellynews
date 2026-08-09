<template>
  <div class="flex min-h-screen items-center justify-center bg-gray-950 px-4">
    <div class="w-full max-w-sm">
      <div class="text-center mb-8">
        <h1 class="text-2xl font-bold tracking-tight">🍿 JellyNews</h1>
        <p class="text-gray-400 mt-1 text-sm">Sign in to your instance</p>
      </div>
      <form @submit.prevent="handleSubmit" class="space-y-4">
        <div>
          <label for="username" class="block text-sm font-medium text-gray-300 mb-1">Username</label>
          <input id="username" v-model="username" type="text" required minlength="3" maxlength="150"
            pattern="^[a-zA-Z0-9_-]+$" autocomplete="username"
            class="w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2.5 text-sm text-gray-100 placeholder-gray-500
                   focus:border-brand-500 focus:ring-1 focus:ring-brand-500 focus:outline-none transition-colors" />
        </div>
        <div>
          <label for="password" class="block text-sm font-medium text-gray-300 mb-1">Password</label>
          <input id="password" v-model="password" type="password" required minlength="8" maxlength="128"
            autocomplete="current-password"
            class="w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2.5 text-sm text-gray-100 placeholder-gray-500
                   focus:border-brand-500 focus:ring-1 focus:ring-brand-500 focus:outline-none transition-colors" />
        </div>
        <p v-if="error" class="text-red-400 text-sm">{{ error }}</p>
        <button type="submit" :disabled="loading"
          class="w-full rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-brand-700
                 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
          {{ loading ? 'Signing in...' : 'Sign in' }}
        </button>
      </form>
      <p class="mt-6 text-center text-xs text-gray-500">
        <router-link to="/setup" class="hover:text-gray-300 transition-colors">Need to set up? Run the wizard</router-link>
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "../stores/auth";

const router = useRouter();
const auth = useAuthStore();

const username = ref("");
const password = ref("");
const loading = ref(false);
const error = ref("");

async function handleSubmit() {
  error.value = "";
  loading.value = true;
  try {
    await auth.login(username.value, password.value);
    router.push("/");
  } catch (e) {
    error.value = e.response?.data?.detail || "Login failed. Check your credentials.";
  } finally {
    loading.value = false;
  }
}
</script>
