import { defineStore } from "pinia";
import { ref, computed } from "vue";
import api from "../services/api";

export const useAuthStore = defineStore("auth", () => {
  const accessToken = ref(localStorage.getItem("access_token") || "");
  const refreshToken = ref(localStorage.getItem("refresh_token") || "");
  const user = ref(null);

  const token = computed(() => accessToken.value);
  const isAuthenticated = computed(() => !!accessToken.value);

  function setTokens(data) {
    accessToken.value = data.access_token;
    refreshToken.value = data.refresh_token;
    localStorage.setItem("access_token", data.access_token);
    localStorage.setItem("refresh_token", data.refresh_token);
  }

  async function login(username, password) {
    const { data } = await api.post("/auth/login", { username, password });
    setTokens(data);
    user.value = { username };
    return data;
  }

  function logout() {
    accessToken.value = "";
    refreshToken.value = "";
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    user.value = null;
  }

  return { accessToken, refreshToken, user, token, isAuthenticated, setTokens, login, logout };
});
