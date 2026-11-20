/*
 * Profile tab: the character (large) with level, XP and what the next level needs,
 * your stats, how XP is earned, achievements (with progress), and settings:
 * edit profile, language, reminders, credits, delete my data.
 */
import { useEffect, useState } from "react";
import type { AppConfig, LanguageCode, Me } from "../lib/api";
import { deleteMyData, getAchievements, getLevel, type AchievementList, type LevelView } from "../lib/profileApi";
import { navigate } from "../lib/router";
import { bindNativeBack, haptic } from "../lib/telegram";
import type { TextKey } from "../i18n";
import { Character } from "../components/Character";
import { useCelebration } from "../components/Celebration";
import { xpLine } from "../components/CharacterCard";
import { Bell, Bin, Globe, Heart, Pencil } from "../components/ProfileIcons";
import { ChevronRight } from "../components/Icons";
import "../components/Character.css";
import "./profile.css";

type T = (key: TextKey, vars?: Record<string, string | number>) => string;

const LANGUAGES: { code: LanguageCode; label: string }[] = [
  { code: "en", label: "English" },
  { code: "ru", label: "Русский" },
  { code: "uz", label: "O‘zbekcha" },
];

export function Profile({ t, me, config, saving, onLanguage, onDeleted }: {
  t: T; me: Me; config: AppConfig | null; saving: LanguageCode | null;
  onLanguage: (code: LanguageCode) => void; onDeleted: () => void;
}) {
  const [view, setView] = useState<LevelView | null>(null);
  const [achievements, setAchievements] = useState<AchievementList | null>(null);
  const [error, setError] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteFailed, setDeleteFailed] = useState(false);

  useEffect(() => bindNativeBack(null), []); // a tab: no Back button
  useEffect(() => {
    Promise.all([getLevel(), getAchievements()])
      .then(([level, list]) => { setView(level); setAchievements(list); })
      .catch(() => setError(true));
  }, [me.language_effective]);
  const celebration = useCelebration(view ? view.level : null, achievements ? achievements.unlocked : null, t);

  async function onDelete() {
    setDeleting(true);
    setDeleteFailed(false);
    try {
      await deleteMyData();
      haptic.success();
      onDeleted();
    } catch {
      haptic.error();
      setDeleteFailed(true);
      setDeleting(false);
    }
  }

  const rank = view ? t(("rank_" + view.level.key) as TextKey) : "";

  return (
    <main className="profile">
      <h1 className="screen-title left">{t("profile_title")}</h1>

      {error && <p className="notice" role="alert">{t("error_generic")}</p>}
      {!view && !error && <div className="spinner center-spinner" aria-label={t("loading")} />}

      {view && (
        <section className="card profile-hero">
          <Character level={view.level.index} mood={view.mood} size={170} label={rank} />
          <h2 className="profile-rank">{t("char_level", { n: view.level.index + 1, rank })}</h2>
          <p className="muted small">{t("char_xp", { xp: view.level.xp })} · {t(("mood_" + view.mood) as TextKey)}</p>
          <span className="xp-bar profile-xp" role="meter" aria-valuemin={0} aria-valuemax={100}
                aria-valuenow={view.level.progress} aria-label={xpLine(view, t)}>
            <span style={{ width: `${view.level.progress}%` }} />
          </span>
          <p className="small">{xpLine(view, t)}</p>
          <ol className="rank-steps" aria-hidden>
            {view.levels.map((l, i) => (
              <li key={l.key}
                  className={i < view.level.index ? "rank-on" : i === view.level.index ? "rank-on rank-current" : ""}>
                {t(("rank_" + l.key) as TextKey)}
              </li>
            ))}
          </ol>
          <div className="char-chips">
            <span>{t("char_streak", { n: view.streak_weeks })}</span>
            <span>{t("char_week", { done: view.week_done, goal: view.week_goal })}</span>
            <span>{t("char_energy", { n: view.energy })}</span>
          </div>
        </section>
      )}

      {view && (
        <section className="card">
          <h2 className="card-title">{t("stats_title")}</h2>
          <div className="profile-stats">
            <Stat value={view.stats.workouts} label={t("stat_workouts")} />
            <Stat value={view.stats.prs} label={t("stat_prs")} />
            <Stat value={view.stats.goal_weeks} label={t("stat_weeks")} />
            <Stat value={view.stats.volume_t} label={t("stat_volume")} />
          </div>
          <h3 className="profile-subtitle">{t("xp_title")}</h3>
          <ul className="profile-xp-rules">
            <li>{t("xp_workout", { n: view.xp_rules.workout })}</li>
            <li>{t("xp_pr", { n: view.xp_rules.pr })}</li>
            <li>{t("xp_week", { n: view.xp_rules.goal_week })}</li>
          </ul>
        </section>
      )}

      {achievements && (
        <section className="card">
          <h2 className="card-title">{t("ach_title", { n: achievements.unlocked, total: achievements.total })}</h2>
          <ul className="badge-grid">
            {achievements.items.map((a) => (
              <li key={a.code} className={"badge" + (a.unlocked ? " badge-on" : "")}>
                <span className="badge-emoji" aria-hidden>{a.emoji}</span>
                <span className="badge-name">{t(("ach_name_" + a.code) as TextKey)}</span>
                {!a.unlocked && (
                  <span className="badge-progress">
                    {t("ach_progress", { n: Math.floor(a.progress), total: a.threshold })}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="card settings">
        <h2 className="card-title">{t("settings_title")}</h2>
        <button type="button" className="settings-row" onClick={() => { haptic.tap(); navigate({ name: "profileEdit" }); }}>
          <Pencil /><span>{t("settings_edit")}</span><ChevronRight />
        </button>
        <div className="settings-row settings-static">
          <Globe /><span>{t("settings_language")}</span>
        </div>
        <div className="language-pills" role="radiogroup" aria-label={t("settings_language")}>
          {LANGUAGES.map(({ code, label }) => (
            <button key={code} type="button" role="radio" aria-checked={me.language_effective === code}
                    className={"pill" + (me.language_effective === code ? " pill-on" : "")}
                    disabled={saving !== null} onClick={() => { haptic.select(); onLanguage(code); }}>
              {label}
            </button>
          ))}
        </div>
        <div className="settings-row settings-static">
          <Bell /><span>{t("settings_reminders")}<small>{t("settings_reminders_hint")}</small></span>
        </div>
        <div className="settings-row settings-static">
          <Heart /><span>{t("settings_credits")}<small>{config?.attribution}</small></span>
        </div>
        <p className="muted small">{t("settings_disclaimer")}</p>
        <button type="button" className="settings-row settings-danger"
                onClick={() => { haptic.warning(); setConfirmDelete(true); }}>
          <Bin /><span>{t("delete_title")}</span>
        </button>
      </section>

      {confirmDelete && (
        <div className="sheet-backdrop" onClick={() => !deleting && setConfirmDelete(false)}>
          <div className="sheet" role="dialog" aria-modal="true" aria-label={t("delete_title")}
               onClick={(e) => e.stopPropagation()}>
            <div className="sheet-handle" />
            <h2 className="sheet-title">{t("delete_title")}</h2>
            <p>{t("delete_text")}</p>
            {deleteFailed && <p className="notice" role="alert">{t("error_generic")}</p>}
            <div className="sheet-actions">
              <button type="button" className="button-link" disabled={deleting}
                      onClick={() => setConfirmDelete(false)}>{t("delete_cancel")}</button>
              <button type="button" className="button-primary button-danger" disabled={deleting}
                      onClick={() => void onDelete()}>
                {deleting ? <span className="spinner spinner-small" /> : t("delete_confirm")}
              </button>
            </div>
          </div>
        </div>
      )}
      {celebration}
    </main>
  );
}

function Stat({ value, label }: { value: number; label: string }) {
  return (
    <div className="profile-stat">
      <b>{value}</b>
      <span>{label}</span>
    </div>
  );
}
