import axios from "axios";
import { useAuthStore } from "../stores/auth";

const api = axios.create({ baseURL: "/api/v1" });

api.interceptors.request.use((config) => {
  const auth = useAuthStore();
  if (auth.token) config.headers.Authorization = `Bearer ${auth.token}`;
  return config;
});

api.interceptors.response.use(
  (r) => r,
  async (error) => {
    const auth = useAuthStore();
    if (error.response?.status === 401 && auth.token && !error.config._retry) {
      error.config._retry = true;
      try {
        const { data } = await axios.post("/api/v1/auth/refresh", {
          refresh_token: auth.refreshToken,
        });
        auth.setTokens(data);
        error.config.headers.Authorization = `Bearer ${data.access_token}`;
        return api(error.config);
      } catch {
        auth.logout();
        return Promise.reject(error);
      }
    }
    return Promise.reject(error);
  },
);

export default api;
