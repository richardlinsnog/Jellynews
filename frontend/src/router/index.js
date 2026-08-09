import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "../stores/auth";

const routes = [
  { path: "/login", name: "Login", component: () => import("../views/LoginPage.vue"), meta: { guest: true } },
  { path: "/setup", name: "Setup", component: () => import("../views/SetupPage.vue"), meta: { guest: true } },
  {
    path: "/",
    component: () => import("../components/layout/AppShell.vue"),
    children: [
      { path: "", name: "Dashboard", component: () => import("../views/DashboardPage.vue") },
      { path: "templates", name: "Templates", component: () => import("../views/TemplatesPage.vue") },
      { path: "channels", name: "Channels", component: () => import("../views/ChannelsPage.vue") },
      { path: "news", name: "News", component: () => import("../views/NewsPage.vue") },
      { path: "logs", name: "Logs", component: () => import("../views/LogsPage.vue") },
    ],
  },
  { path: "/:pathMatch(.*)*", redirect: "/" },
];

const router = createRouter({ history: createWebHistory(), routes });

router.beforeEach((to, _from) => {
  const auth = useAuthStore();
  if (!to.meta.guest && !auth.token) return "/login";
  return true;
});

export default router;
