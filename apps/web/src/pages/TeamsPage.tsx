import { type FormEvent, useEffect, useState } from "react";
import {
  type CurrentUser,
  type Team,
  type TeamDetail,
  addTeamMember,
  createTeam,
  deleteTeam,
  getTeam,
  listTeams,
  listUsers,
  removeTeamMember,
} from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { inputClass } from "../components/formStyles";
import { useErrorMessage } from "../i18n/useErrorMessage";
import Button from "../components/Button";
import EmptyState from "../components/EmptyState";
import FormField from "../components/FormField";
import Modal from "../components/Modal";
import PageHeader from "../components/PageHeader";
import { useToast } from "../components/Toast";
import { useI18n } from "../i18n/I18nContext";

export default function TeamsPage() {
  const { user } = useAuth();
  const { t } = useI18n();
  const toast = useToast();
  const errorMessage = useErrorMessage();
  const isAdmin = user?.role === "admin";

  const [teams, setTeams] = useState<Team[]>([]);
  const [users, setUsers] = useState<CurrentUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [addOpen, setAddOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  // Member-management modal for the selected team.
  const [detail, setDetail] = useState<TeamDetail | null>(null);
  const [addUserId, setAddUserId] = useState("");

  async function reload() {
    setLoading(true);
    try {
      const [tm, us] = await Promise.all([
        listTeams(),
        isAdmin ? listUsers() : Promise.resolve([] as CurrentUser[]),
      ]);
      setTeams(tm);
      setUsers(us);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    try {
      await createTeam({ name, description: description || null });
      setAddOpen(false);
      setName("");
      setDescription("");
      toast.success(t("teams.created"));
      await reload();
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  async function onDelete(id: string) {
    if (!window.confirm(t("teams.confirmDelete"))) return;
    try {
      await deleteTeam(id);
      toast.success(t("teams.deleted"));
      await reload();
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  async function openMembers(id: string) {
    setAddUserId("");
    try {
      setDetail(await getTeam(id));
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  async function onAddMember() {
    if (!detail || !addUserId) return;
    try {
      await addTeamMember(detail.id, addUserId);
      setAddUserId("");
      setDetail(await getTeam(detail.id));
      await reload();
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  async function onRemoveMember(userId: string) {
    if (!detail) return;
    try {
      await removeTeamMember(detail.id, userId);
      setDetail(await getTeam(detail.id));
      await reload();
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  const memberIds = new Set(detail?.members.map((m) => m.user_id));
  const addable = users.filter((u) => !memberIds.has(u.id));

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("teams.title")}
        subtitle={t("teams.subtitle")}
        actions={isAdmin && <Button onClick={() => setAddOpen(true)}>{t("teams.add")}</Button>}
      />
      {error && <p className="text-sm text-red-400">{error}</p>}

      {loading ? (
        <p className="text-sm text-slate-500">{t("common.loading")}</p>
      ) : teams.length === 0 ? (
        <EmptyState
          icon="👥"
          title={t("teams.empty")}
          body={t("teams.emptyBody")}
          action={isAdmin && <Button onClick={() => setAddOpen(true)}>{t("teams.add")}</Button>}
        />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-slate-800">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-900 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-2 font-medium">{t("teams.col.name")}</th>
                <th className="px-4 py-2 font-medium">{t("teams.col.description")}</th>
                <th className="px-4 py-2 font-medium">{t("teams.col.members")}</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {teams.map((tm) => (
                <tr key={tm.id} className="bg-slate-950">
                  <td className="px-4 py-2 font-medium text-slate-100">{tm.name}</td>
                  <td className="px-4 py-2 text-slate-400">{tm.description || "-"}</td>
                  <td className="px-4 py-2 text-slate-300">{tm.member_count}</td>
                  <td className="px-4 py-2 text-right">
                    <button
                      onClick={() => void openMembers(tm.id)}
                      className="text-xs text-sky-400 hover:text-sky-300"
                    >
                      {t("teams.members")}
                    </button>
                    {isAdmin && (
                      <button
                        onClick={() => void onDelete(tm.id)}
                        className="ml-3 text-xs text-red-400 hover:text-red-300"
                      >
                        {t("common.delete")}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal open={addOpen} onClose={() => setAddOpen(false)} title={t("teams.add")}>
        <form onSubmit={onCreate} className="space-y-3">
          <FormField label={t("teams.f.name")}>
            <input
              className={inputClass}
              placeholder="Blue team"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </FormField>
          <FormField label={t("teams.f.description")}>
            <input
              className={inputClass}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </FormField>
          <div className="flex justify-end">
            <Button type="submit">{t("teams.add")}</Button>
          </div>
        </form>
      </Modal>

      <Modal
        open={detail !== null}
        onClose={() => setDetail(null)}
        title={detail ? t("teams.membersOf", { name: detail.name }) : ""}
      >
        {detail && (
          <div className="space-y-4">
            {detail.members.length === 0 ? (
              <p className="text-sm text-slate-500">{t("teams.noMembers")}</p>
            ) : (
              <ul className="divide-y divide-slate-800 rounded-lg border border-slate-800">
                {detail.members.map((m) => (
                  <li key={m.user_id} className="flex items-center gap-3 px-3 py-2">
                    <span className="text-sm text-slate-200">{m.email}</span>
                    {m.full_name && <span className="text-xs text-slate-500">{m.full_name}</span>}
                    {isAdmin && (
                      <button
                        onClick={() => void onRemoveMember(m.user_id)}
                        className="ml-auto text-xs text-red-400 hover:text-red-300"
                      >
                        {t("common.remove")}
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            )}
            {isAdmin && (
              <div className="flex items-center gap-2">
                <select
                  className={inputClass}
                  value={addUserId}
                  onChange={(e) => setAddUserId(e.target.value)}
                >
                  <option value="">{t("teams.addMember")}</option>
                  {addable.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.email}
                    </option>
                  ))}
                </select>
                <Button onClick={() => void onAddMember()} disabled={!addUserId}>
                  {t("common.add")}
                </Button>
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
}
