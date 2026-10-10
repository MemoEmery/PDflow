// Endereço do servidor. Vazio = mesmo endereço do site (Docker único ou desenvolvimento com proxy).
// Na Vercel, defina VITE_API_URL com o endereço do servidor (ex.: https://pdflow-api.onrender.com).
export const API: string = ((import.meta.env.VITE_API_URL as string | undefined) || "").replace(/\/+$/, "");
