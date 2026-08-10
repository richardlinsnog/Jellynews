<template>
  <div class="flex h-screen bg-gray-950">
    <aside class="w-64 flex-shrink-0 border-r border-gray-800 bg-gray-900 flex flex-col">
      <div class="h-16 flex items-center px-6 border-b border-gray-800">
        <span class="text-lg font-semibold tracking-tight">🍿 JellyNews</span>
      </div>
      <nav class="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        <router-link v-for="item in nav" :key="item.to" :to="item.to"
          class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors"
          :class="route.path === item.to || (item.to !== '/' && route.path.startsWith(item.to))
            ? 'bg-brand-600/20 text-brand-500'
            : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800'">
          <span class="w-5 text-center">{{ item.icon }}</span>
          <span>{{ item.label }}</span>
        </router-link>
      </nav>
      <div class="p-3 border-t border-gray-800">
        <button @click="auth.logout(); $router.push('/login')"
          class="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-gray-400 hover:text-gray-200 hover:bg-gray-800 transition-colors">
          <span class="w-5 text-center">⏻</span> Logout
        </button>
      </div>
    </aside>
    <main class="flex-1 overflow-y-auto p-8">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { useRoute } from "vue-router";
import { useAuthStore } from "../../stores/auth";

const route = useRoute();
const auth = useAuthStore();

const nav = [
  { to: "/", label: "Dashboard", icon: "📊" },
  { to: "/templates", label: "Templates", icon: "🎨" },
  { to: "/channels", label: "Channels", icon: "📡" },
  { to: "/news", label: "News", icon: "📝" },
  { to: "/subscribers", label: "Subscribers", icon: "👥" },
  { to: "/settings", label: "Settings", icon: "⚙️" },
  { to: "/logs", label: "Logs", icon: "📋" },
];
</script>
