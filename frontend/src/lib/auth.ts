"use client";

import { useEffect, useState } from "react";
import { api } from "./api";
import type { User } from "@/types";

export function useAuth() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.auth
      .me()
      .then((data) => setUser(data as User))
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  return { user, loading, isAuthenticated: !!user };
}
