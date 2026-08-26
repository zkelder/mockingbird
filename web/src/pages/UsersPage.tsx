import { useEffect, useState } from "react";
import { apiClient, ApiError } from "../api/client";
import type { AuditLogEntry, CurrentUser, UserRole, UserSummary } from "../api/types";
import { PageHeader } from "../components/PageHeader";
import { StatusPill } from "../components/StatusPill";

interface UsersPageProps {
  currentUser: CurrentUser;
}

const ROLE_OPTIONS: UserRole[] = ["viewer", "reviewer", "administrator"];

function describeAuditAction(action: string): string {
  // A handful of the most common actions get a calmer label; anything else
  // (there are ~20 distinct action strings across review/camera/storage/
  // backup/user mutations -- see docs/local-identity-multi-user-contract.md
  // "Audit") falls back to its own raw dotted name, which is still legible.
  const labels: Record<string, string> = {
    "user.bootstrap_administrator": "First-run administrator created",
    "user.created": "User created",
    "user.role_changed": "Role changed",
    "user.enabled": "User enabled",
    "user.disabled": "User disabled",
    "user.password_reset": "Password reset by administrator",
    "user.password_changed_self": "Password changed",
    "review.corrected": "Review correction",
    "review.reopened": "Review reopened",
    "review.bulk_corrected": "Bulk review correction",
    "review.fast_review_undo": "Fast Review undo",
    "camera.created": "Camera added",
    "camera.reconfigured": "Camera reconfigured",
    "camera.archived": "Camera archived",
    "camera_node.paired": "Camera Node paired",
    "camera_node.pairing_revoked": "Camera Node pairing revoked",
    "camera_node.replaced": "Camera Node replaced",
    "zone.created": "Zone created",
    "zone.updated": "Zone updated",
    "zone.deleted": "Zone deleted",
    "zone.privacy_changed": "Privacy/Ignore Zone changed",
    "storage.retention_updated": "Storage retention policy updated",
    "backup.restored": "Backup restored",
    "settings.installation_updated": "Installation settings updated",
  };
  return labels[action] ?? action;
}

function CreateUserForm({ onCreated }: { onCreated: (user: UserSummary) => void }) {
  const [displayName, setDisplayName] = useState("");
  const [loginIdentity, setLoginIdentity] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<UserRole>("viewer");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      const user = await apiClient.createUser({
        display_name: displayName,
        login_identity: loginIdentity,
        password,
        role,
      });
      onCreated(user);
      setDisplayName("");
      setLoginIdentity("");
      setPassword("");
      setRole("viewer");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not create the user.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form className="panel page-stack auth-form" onSubmit={(event) => void handleSubmit(event)}>
      <h2>Add a user</h2>
      {error ? <div className="error-panel">{error}</div> : null}
      <label>
        Display name
        <input
          onChange={(event) => setDisplayName(event.target.value)}
          type="text"
          value={displayName}
        />
      </label>
      <label>
        Login identity
        <input
          autoComplete="off"
          onChange={(event) => setLoginIdentity(event.target.value)}
          type="text"
          value={loginIdentity}
        />
      </label>
      <label>
        Temporary password
        <input
          autoComplete="new-password"
          minLength={10}
          onChange={(event) => setPassword(event.target.value)}
          type="password"
          value={password}
        />
        <span className="meta-text">At least 10 characters. They can change it after signing in.</span>
      </label>
      <label>
        Role
        <select onChange={(event) => setRole(event.target.value as UserRole)} value={role}>
          {ROLE_OPTIONS.map((option) => (
            <option key={option} value={option}>
              {option[0].toUpperCase() + option.slice(1)}
            </option>
          ))}
        </select>
      </label>
      <button
        className="primary-action"
        disabled={isSubmitting || !displayName || !loginIdentity || password.length < 10}
        type="submit"
      >
        {isSubmitting ? "Adding…" : "Add user"}
      </button>
    </form>
  );
}

function ResetPasswordControl({ user }: { user: UserSummary }) {
  const [isOpen, setIsOpen] = useState(false);
  const [newPassword, setNewPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) {
    return (
      <button className="text-action" onClick={() => setIsOpen(true)} type="button">
        Reset password
      </button>
    );
  }

  async function handleReset() {
    setError(null);
    setIsSubmitting(true);
    try {
      await apiClient.resetUserPassword(user.id, { new_password: newPassword });
      setMessage(`Password reset. ${user.display_name} was signed out everywhere.`);
      setNewPassword("");
      setIsOpen(false);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not reset the password.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="auth-form inline-reset-password">
      {error ? <div className="error-panel">{error}</div> : null}
      {message ? <div className="notice-panel">{message}</div> : null}
      <label>
        New password for {user.display_name}
        <input
          autoComplete="new-password"
          minLength={10}
          onChange={(event) => setNewPassword(event.target.value)}
          type="password"
          value={newPassword}
        />
      </label>
      <div className="button-row">
        <button
          className="primary-action"
          disabled={isSubmitting || newPassword.length < 10}
          onClick={() => void handleReset()}
          type="button"
        >
          {isSubmitting ? "Saving…" : "Save new password"}
        </button>
        <button className="secondary-action" onClick={() => setIsOpen(false)} type="button">
          Cancel
        </button>
      </div>
    </div>
  );
}

export function UsersPage({ currentUser }: UsersPageProps) {
  const [users, setUsers] = useState<UserSummary[]>([]);
  const [auditLog, setAuditLog] = useState<AuditLogEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [rowError, setRowError] = useState<string | null>(null);

  async function load() {
    setIsLoading(true);
    setError(null);
    try {
      const [usersResult, auditResult] = await Promise.all([
        apiClient.listUsers(),
        apiClient.getAuditLog(50),
      ]);
      setUsers(usersResult);
      setAuditLog(auditResult);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not load users.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function handleRoleChange(user: UserSummary, role: UserRole) {
    setRowError(null);
    try {
      const updated = await apiClient.updateUserRole(user.id, { role });
      setUsers((current) => current.map((item) => (item.id === updated.id ? updated : item)));
    } catch (caught) {
      setRowError(caught instanceof ApiError ? caught.message : "Could not change that user's role.");
    }
  }

  async function handleToggleEnabled(user: UserSummary) {
    setRowError(null);
    try {
      const updated = await apiClient.setUserEnabled(user.id, { enabled: !user.enabled });
      setUsers((current) => current.map((item) => (item.id === updated.id ? updated : item)));
    } catch (caught) {
      setRowError(
        caught instanceof ApiError ? caught.message : "Could not change that user's access.",
      );
    }
  }

  if (isLoading) {
    return <div className="panel">Loading…</div>;
  }
  if (error) {
    return <div className="error-panel">{error}</div>;
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Administration"
        title="Users"
        description="Local accounts for this Host. Roles are Viewer, Reviewer, and Administrator -- see the account menu to change your own password."
      />
      {rowError ? <div className="error-panel">{rowError}</div> : null}
      <section className="panel page-stack">
        {/* Mobile & Remote Experience v1 (Phase 10): the only raw <table> in
            the frontend -- an admin-only, low-row-count surface where
            horizontal scroll is a genuinely appropriate, well-understood
            pattern rather than justifying a one-off stacked-card rebuild or
            a new generic responsive-table framework. Every column stays
            visible, in its familiar shape, just scrollable at narrow
            widths. */}
        <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Login identity</th>
              <th>Role</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((user) => (
              <tr key={user.id}>
                <td>
                  {user.display_name}
                  {user.id === currentUser.id ? <span className="meta-text"> (you)</span> : null}
                </td>
                <td>{user.login_identity}</td>
                <td>
                  <select
                    disabled={user.id === currentUser.id}
                    onChange={(event) => void handleRoleChange(user, event.target.value as UserRole)}
                    value={user.role}
                  >
                    {ROLE_OPTIONS.map((option) => (
                      <option key={option} value={option}>
                        {option[0].toUpperCase() + option.slice(1)}
                      </option>
                    ))}
                  </select>
                </td>
                <td>
                  <StatusPill label={user.enabled ? "Active" : "Disabled"} tone={user.enabled ? "good" : "quiet"} />
                </td>
                <td className="button-row">
                  <button
                    className="secondary-action"
                    disabled={user.id === currentUser.id}
                    onClick={() => void handleToggleEnabled(user)}
                    type="button"
                  >
                    {user.enabled ? "Disable" : "Enable"}
                  </button>
                  <ResetPasswordControl user={user} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </section>
      <CreateUserForm onCreated={(user) => setUsers((current) => [...current, user])} />
      <section className="panel page-stack">
        <h2>Recent activity</h2>
        {auditLog.length === 0 ? (
          <p className="meta-text">No audited actions yet.</p>
        ) : (
          <ul className="audit-log-list">
            {auditLog.map((entry) => (
              <li key={entry.id}>
                <span className="meta-text">{new Date(entry.created_at).toLocaleString()}</span>
                <strong>{describeAuditAction(entry.action)}</strong>
                <span>{entry.actor_display_name ?? "Unattributed"}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
