import type {
  DriveFolder,
  DriveFile,
  Job,
  JobListResponse,
  ApiKeyListResponse,
  ApiKeyCreated,
} from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    ...options,
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || "API request failed");
  }
  return res.json();
}

export const api = {
  auth: {
    me: () => fetchAPI<{ google_id: string; email: string; name: string }>("/api/auth/me"),
    loginUrl: () => `${API_BASE}/api/auth/login`,
    logout: () => fetchAPI("/api/auth/logout", { method: "POST" }),
  },
  drive: {
    listFolders: (parentId?: string) =>
      fetchAPI<{ folders: DriveFolder[] }>(
        `/api/drive/folders${parentId ? `?parent_id=${parentId}` : ""}`
      ),
    listFiles: (folderId: string) =>
      fetchAPI<{ files: DriveFile[] }>(`/api/drive/files/${folderId}`),
  },
  products: {
    list: (folderId: string, excelFileId: string) =>
      fetchAPI<{ products: string[]; category: string }>(
        `/api/products?folder_id=${folderId}&excel_file_id=${excelFileId}`
      ),
  },
  save: {
    results: (data: {
      drive_folder_id: string;
      product_id: string;
      listing?: Record<string, unknown>;
      prompts?: Record<string, unknown>;
      product_data?: Record<string, unknown>;
    }) =>
      fetchAPI<{ status: string; uploaded: { type: string; id: string; name: string }[] }>(
        "/api/save",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(data),
        }
      ),
  },
  jobs: {
    list: (page = 1, pageSize = 20) =>
      fetchAPI<JobListResponse>(`/api/jobs?page=${page}&page_size=${pageSize}`),
    get: (jobId: string) => fetchAPI<Job>(`/api/jobs/${jobId}`),
  },
  keys: {
    list: () => fetchAPI<ApiKeyListResponse>("/api/keys"),
    create: (name: string, rateLimitRpm = 60) =>
      fetchAPI<ApiKeyCreated>("/api/keys", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, rate_limit_rpm: rateLimitRpm }),
      }),
    revoke: (keyId: number) =>
      fetchAPI<{ id: number; revoked: boolean; message: string }>(`/api/keys/${keyId}`, {
        method: "DELETE",
      }),
  },
};

export { API_BASE };
