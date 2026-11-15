/* All programs (reference image 2, "All Cycles"): Current / Available / Created tabs. */
import { useEffect, useState } from "react";
import { getPrograms, type Programs as ProgramsData, type ProgramSummary, type TemplateInfo } from "../lib/api";
import { goBack, navigate } from "../lib/router";
import { bindNativeBack, haptic } from "../lib/telegram";
import { percent, programName, type T } from "../lib/plan";
import type { TextKey } from "../i18n";
import { ArrowLeft, Plus } from "../components/Icons";

type Tab = "current" | "available" | "created";
const TAB_KEY = "gym24.programs.tab";

export function Programs({ t }: { t: T }) {
  const [data, setData] = useState<ProgramsData | null>(null);
  const [failed, setFailed] = useState(false);
  const [tab, setTab] = useState<Tab>(() => (sessionStorage.getItem(TAB_KEY) as Tab) || "current");

  useEffect(() => {
    getPrograms().then(setData).catch(() => setFailed(true));
  }, []);
  useEffect(() => { sessionStorage.setItem(TAB_KEY, tab); }, [tab]);
  const back = () => goBack({ name: "plan" });
  useEffect(() => bindNativeBack(back), []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <main className="programs">
      <header className="screen-header">
        <button type="button" className="round-button round-back" onClick={back} aria-label={t("back")}><ArrowLeft /></button>
        <h1 className="screen-header-title">{t("all_programs")}</h1>
        <span className="round-spacer" />
      </header>

      <div className="segmented" role="tablist">
        {(["current", "available", "created"] as Tab[]).map((id) => (
          <button key={id} type="button" role="tab" aria-selected={tab === id}
                  className={"segment" + (tab === id ? " segment-on" : "")}
                  onClick={() => { haptic.select(); setTab(id); }}>
            {t(("tab_" + id) as TextKey)}
            {id === "created" && data && data.created.length > 0 && <span className="segment-count">{data.created.length}</span>}
          </button>
        ))}
      </div>

      {failed && <p className="muted center-text" role="alert">{t("error_generic")}</p>}
      {!data && !failed && <div className="spinner center-spinner" aria-label={t("loading")} />}

      {data && tab === "current" && (data.current
        ? <ProgramCard p={data.current} t={t} />
        : <p className="muted center-text">{t("no_current_program")}</p>)}

      {data && tab === "available" && (
        <div className="stack">
          {data.available.map((tpl) => <TemplateCard key={tpl.days} tpl={tpl} t={t} />)}
        </div>
      )}

      {data && tab === "created" && (
        <div className="stack">
          {data.created.length === 0 && <p className="muted center-text">{t("no_created")}</p>}
          {data.created.map((p) => <ProgramCard key={p.id} p={p} t={t} />)}
        </div>
      )}

      <button type="button" className="button-primary create-button"
              onClick={() => { haptic.tap(); navigate({ name: "programNew" }); }}>
        <Plus /> {t("create_program")}
      </button>
    </main>
  );
}

function ProgramCard({ p, t }: { p: ProgramSummary; t: T }) {
  return (
    <button type="button" className={"card program-card" + (p.is_current ? " program-card-current" : "")}
            onClick={() => { haptic.tap(); navigate({ name: "program", id: p.id }); }}>
      {p.is_current && <span className="badge-current">{t("current")}</span>}
      <span className="program-name">{programName(p, t)}</span>
      <span className="program-sub">
        {t(("tgoal_" + p.goal) as TextKey)} · {t("per_week", { n: p.workouts_per_week })} · {t("weeks_n", { n: p.weeks })}
      </span>
      {p.is_current && (
        <>
          <span className="program-progress">
            <span>{t("week_of", { n: p.week ?? 1, total: p.weeks })}</span>
            <span>{t("percent_done", { n: percent(p.completed, p.total) })}</span>
          </span>
          <span className="progress-track"><span style={{ width: percent(p.completed, p.total) + "%" }} /></span>
        </>
      )}
      <span className="day-chips">
        {p.day_names.map((d) => (
          <span key={d.id} className="day-chip">{d.name || (t(("day_" + d.name_key) as TextKey) + " " + d.suffix).trim()}</span>
        ))}
      </span>
    </button>
  );
}

function TemplateCard({ tpl, t }: { tpl: TemplateInfo; t: T }) {
  return (
    <button type="button" className="card program-card"
            onClick={() => { haptic.tap(); navigate({ name: "template", days: tpl.days }); }}>
      {tpl.recommended && <span className="badge-recommended">{t("recommended")}</span>}
      <span className="program-name">{t(("split_" + tpl.split) as TextKey)}</span>
      <span className="program-sub">{t("per_week", { n: tpl.days })} · {t(("split_" + tpl.split + "_desc") as TextKey)}</span>
      <span className="day-chips">
        {tpl.day_keys.map((k, i) => <span key={i} className="day-chip">{t(("day_" + k) as TextKey)}</span>)}
      </span>
    </button>
  );
}
