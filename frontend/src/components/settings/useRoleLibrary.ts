import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  createRole,
  deleteRole,
  getRoleLibrarySettings,
  replaceRole,
  updateDefaultRoleCount,
} from "../../api";
import type { RoleDefinition, RoleInput, RoleLibrarySettings } from "../../types";

function errorMessage(error: unknown): string {
  if (error instanceof ApiError && error.status === 409) {
    return error.message;
  }
  return error instanceof Error ? error.message : "Something went wrong. Please try again.";
}

export function useRoleLibrary() {
  const [settings, setSettings] = useState<RoleLibrarySettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [operationError, setOperationError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [countSaving, setCountSaving] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      setSettings(await getRoleLibrarySettings());
    } catch (error) {
      setLoadError(errorMessage(error));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const next = await getRoleLibrarySettings();
        if (active) setSettings(next);
      } catch (error) {
        if (active) setLoadError(errorMessage(error));
      } finally {
        if (active) setLoading(false);
      }
    }
    void load();
    return () => {
      active = false;
    };
  }, []);

  const saveRole = useCallback(async (input: RoleInput, roleId?: string) => {
    setSaving(true);
    setOperationError(null);
    try {
      const saved = roleId ? await replaceRole(roleId, input) : await createRole(input);
      setSettings((current) => {
        if (!current) return current;
        const exists = current.roles.some((role) => role.id === saved.id);
        const roles = exists
          ? current.roles.map((role) => (role.id === saved.id ? saved : role))
          : [...current.roles, saved];
        return { ...current, roles };
      });
      return saved;
    } catch (error) {
      setOperationError(errorMessage(error));
      return null;
    } finally {
      setSaving(false);
    }
  }, []);

  const removeRole = useCallback(async (role: RoleDefinition) => {
    setSaving(true);
    setOperationError(null);
    try {
      await deleteRole(role.id);
      setSettings((current) =>
        current
          ? { ...current, roles: current.roles.filter((item) => item.id !== role.id) }
          : current,
      );
      return true;
    } catch (error) {
      setOperationError(errorMessage(error));
      return false;
    } finally {
      setSaving(false);
    }
  }, []);

  const changeCount = useCallback(async (count: number) => {
    setCountSaving(true);
    setOperationError(null);
    try {
      setSettings(await updateDefaultRoleCount(count));
    } catch (error) {
      setOperationError(errorMessage(error));
    } finally {
      setCountSaving(false);
    }
  }, []);

  return {
    settings,
    loading,
    loadError,
    operationError,
    saving,
    countSaving,
    refresh,
    saveRole,
    removeRole,
    changeCount,
    clearOperationError: () => setOperationError(null),
  };
}
