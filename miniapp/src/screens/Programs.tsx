/*
 * All programs: tabs Current / Available / Created.
 * Available = built-in programs you can start. Created = every saved program
 * (yours, and ones you switched away from, with your changes). Starting or
 * activating a program makes it current and opens the Plan tab.
 */
import { useEffect, useState } from "react";
import {
  activateProgram, deleteProgram, listPrograms, listTemplates, startTemplate,
  type ProgramItem, type Template,
} from "../lib/planApi";
import { planErrorKey, programName } from "../lib/planText";
import { goBack, navigate } from "../lib/router";
import { bindNativeBack, haptic } from "../lib/telegram";
import type { TextKey } from "../i18n";
import { ArrowLeft } from "../components/Icons";
import { Plus } from "../components/PlanIcons";
import "./plan.css";

type T = (key: TextKey, vars?: Record<string, string | number>) => string;
type Tab = "current" | "available" | "created";
const TABS: Tab[] = ["current", "available", "created"];

export function Programs({ t }: { t: T }) {
  const [tab, setTab] = useState<Tab>("current");
  const [items, setItems] = useState<ProgramItem[] | null>(null);
  const [templates, setTemplates] = useState<Template[] | null>(null);
  const [error, setError] = useState<TextKey | null>(null);
  const [busy, setBusy] = useState(false);
  const [armed, setArmed] = useState<number | null>(null);

  useEffect(() => bindNativeBack(() => goBack({ name: "plan" })), []);

  useEffect(() => {
    let live = true;
    setError(null);
    setItems(null);
    setTemplates(null);
    setArmed(null);
    const load = tab === "available"
      ? listTemplates().then((r) => { if (live) setTemplates(r.items); })
      : listPrograms(tab).then((r) => { if (live) setItems(r.items); });
    load.catch((e) => { if (live) setError(planErrorKey(e)); });
    return () => { live = false; };
  }, [tab]);

  async function act(action: () => Promise<unknown>, after: () => void) {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await action();
      haptic.success();
      after();
    } catch (e) {
      haptic.error();
      setError(planErrorKey(e));
    } finally {
      setBusy(false);
    }
  }

  const meta = (p: { workouts_per_week: number; weeks: number; goal: string }) =>
    `${t("programs_meta", { days: p.workouts_per_week, weeks: p.weeks })} · ${t(("goal_" + p.goal) as TextKey)}`;
  const loading = !error && (tab === "available" ? templates === null : items === null);

  return (
    <main className="programs">
      <header className="editor-header">
        <button type="button" className="round-button round-back" aria-label={t("back")}
                onClick={() => goBack({ name: "plan" })}><ArrowLeft /></button>
        <h1 className="editor-title">{t("programs_title")}</h1>
        <button type="button" className="round-button round-close" aria-label={t("programs_create")}
                onClick={() => { haptic.tap(); navigate({ name: "programNew" }); }}><Plus /></button>
      </header>

      <div className="segmented" role="tablist">
        {TABS.map((name) => (
          <button key={name} type="button" role="tab" aria-selected={tab === name}
                  className={"segment" + (tab === name ? " segment-on" : "")}
                  onClick={() => { haptic.select(); setTab(name); }}>
            {t(("programs_tab_" + name) as TextKey)}
          </button>
        ))}
      </div>
      {tab !== "current" && <p className="muted small programs-note">{t("programs_switch_note")}</p>}

      {error && <p className="notice editor-error" role="alert">{t(error)}</p>}
      {loading && <div className="spinner center-spinner" aria-label={t("loading")} />}

      {tab === "available" && templates?.map((tpl) => (
        <article key={tpl.key} className="card program-card">
          <div className="program-text">
            <h2 className="program-name">{t(tpl.name_key as TextKey)}</h2>
            <p className="muted small">{meta(tpl)}</p>
          </div>
          <button type="button" className="button-primary button-small" disabled={busy}
                  onClick={() => void act(() => startTemplate(tpl.key), () => navigate({ name: "plan" }))}>
            {t("programs_start")}
          </button>
        </article>
      ))}

      {tab !== "available" && items?.length === 0 && <p className="empty">{t("programs_empty_created")}</p>}
      {tab !== "available" && items?.map((p) => (
        <article key={p.id} className="card program-card">
          <div className="program-text">
            <h2 className="program-name">{programName(p, t)}</h2>
            <p className="muted small">{meta(p)}</p>
            {p.status === "current" && <span className="tag">{t("programs_current_badge")}</span>}
          </div>
          {p.status === "current" ? (
            <button type="button" className="button-secondary button-small"
                    onClick={() => { haptic.tap(); navigate({ name: "planEdit" }); }}>{t("plan_edit_split")}</button>
          ) : (
            <div className="program-actions">
              <button type="button" className="button-primary button-small" disabled={busy}
                      onClick={() => void act(() => activateProgram(p.id), () => navigate({ name: "plan" }))}>
                {t("programs_activate")}
              </button>
              <button type="button" className={"button-link" + (armed === p.id ? " danger" : "")} disabled={busy}
                      onClick={() => {
                        if (armed !== p.id) {
                          haptic.warning();
                          setArmed(p.id);
                          return;
                        }
                        void act(() => deleteProgram(p.id),
                                 () => setItems((list) => list?.filter((x) => x.id !== p.id) ?? null));
                      }}>
                {armed === p.id ? t("editor_confirm") : t("programs_delete")}
              </button>
            </div>
          )}
        </article>
      ))}
    </main>
  );
}
