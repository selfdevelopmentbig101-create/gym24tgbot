/*
 * Exercise library (Train tab): search, muscle chips, filters, A-Z list.
 * The query is kept for this session, so coming back from an exercise restores it.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { getExercises, type ExerciseItem, type ExerciseList, type LibraryQuery } from "../lib/api";
import { navigate } from "../lib/router";
import { haptic } from "../lib/telegram";
import type { TextKey } from "../i18n";
import { Close, Search, Sliders } from "../components/Icons";
import { ExerciseRow } from "../components/ExerciseRow";

type T = (key: TextKey, vars?: Record<string, string | number>) => string;

const STORE = "gym24.library.v1";
const EMPTY: LibraryQuery = { q: "", muscle: null, equipment: null, difficulty: null, home: false, fits: false };

function loadQuery(): LibraryQuery {
  try {
    return { ...EMPTY, ...JSON.parse(sessionStorage.getItem(STORE) ?? "{}") };
  } catch {
    return EMPTY;
  }
}

export function Library({ t, hasProfile, locale }: { t: T; hasProfile: boolean; locale: string }) {
  const [query, setQuery] = useState<LibraryQuery>(loadQuery);
  const [typed, setTyped] = useState(query.q);
  const [data, setData] = useState<ExerciseList | null>(null);
  const [failed, setFailed] = useState(false);
  const [sheet, setSheet] = useState(false);
  const latest = useRef(0);

  // Debounce typing; filters apply at once.
  useEffect(() => {
    const timer = setTimeout(() => setQuery((q) => (q.q === typed ? q : { ...q, q: typed })), 250);
    return () => clearTimeout(timer);
  }, [typed]);

  useEffect(() => {
    sessionStorage.setItem(STORE, JSON.stringify(query));
    const id = ++latest.current;
    setFailed(false);
    getExercises(query)
      .then((result) => { if (id === latest.current) setData(result); })
      .catch(() => { if (id === latest.current) setFailed(true); });
  }, [query]);

  const extraFilters = [query.equipment, query.difficulty, query.home || null, query.fits || null]
    .filter(Boolean).length;

  // A-Z sections; letters follow the user's language rules for sorting.
  const sections = useMemo(() => {
    const groups = new Map<string, ExerciseItem[]>();
    for (const item of data?.items ?? []) {
      const letter = item.name.charAt(0).toLocaleUpperCase(locale);
      groups.set(letter, [...(groups.get(letter) ?? []), item]);
    }
    return [...groups.entries()];
  }, [data, locale]);

  const set = (patch: Partial<LibraryQuery>) => setQuery((q) => ({ ...q, ...patch }));

  return (
    <main className="library">
      <h1 className="screen-title left">{t("library_title")}</h1>

      <div className="search-row">
        <label className="search">
          <Search />
          <input type="search" value={typed} placeholder={t("search_placeholder")} enterKeyHint="search"
                 aria-label={t("search_placeholder")} maxLength={60}
                 onChange={(e) => setTyped(e.target.value)} />
          {typed && (
            <button type="button" className="search-clear" aria-label={t("clear")} onClick={() => setTyped("")}>
              <Close />
            </button>
          )}
        </label>
        <button type="button" className={"filter-button" + (extraFilters ? " filter-button-on" : "")}
                aria-label={t("filters")} aria-expanded={sheet} onClick={() => { haptic.tap(); setSheet(true); }}>
          <Sliders />
          {extraFilters > 0 && <span className="filter-count">{extraFilters}</span>}
        </button>
      </div>

      <div className="chips" role="radiogroup" aria-label={t("muscle")}>
        {[null, ...(data?.muscles ?? [])].map((m) => (
          <button key={m ?? "all"} type="button" role="radio" aria-checked={query.muscle === m}
                  className={"chip" + (query.muscle === m ? " chip-on" : "")}
                  onClick={() => { haptic.select(); set({ muscle: m }); }}>
            {m ? t(("muscle_" + m) as TextKey) : t("all")}
          </button>
        ))}
      </div>

      {failed && <p className="muted center-text" role="alert">{t("error_generic")}</p>}
      {!data && !failed && <div className="spinner center-spinner" aria-label={t("loading")} />}

      {data && (
        <>
          <p className="result-count">{t("results", { n: data.items.length, total: data.total })}</p>
          {data.items.length === 0 ? (
            <div className="empty">
              <p>{t("no_results")}</p>
              <button type="button" className="button-link"
                      onClick={() => { setTyped(""); setQuery(EMPTY); }}>{t("reset_filters")}</button>
            </div>
          ) : (
            sections.map(([letter, items]) => (
              <section key={letter} className="az-section" aria-label={letter}>
                <h2 className="az-letter">{letter}</h2>
                <div className="rows">
                  {items.map((item) => (
                    <ExerciseRow key={item.id} item={item} t={t}
                                 onOpen={() => navigate({ name: "exercise", id: item.id })} />
                  ))}
                </div>
              </section>
            ))
          )}
        </>
      )}

      {sheet && data && (
        <div className="sheet-backdrop" onClick={() => setSheet(false)}>
          <div className="sheet" role="dialog" aria-modal="true" aria-label={t("filters")}
               onClick={(e) => e.stopPropagation()}>
            <div className="sheet-handle" />
            <h2 className="sheet-title">{t("filters")}</h2>

            <FilterGroup label={t("equipment")} value={query.equipment} t={t} prefix="equip_"
                         options={data.equipment} onChange={(equipment) => set({ equipment })} />
            <FilterGroup label={t("difficulty")} value={query.difficulty} t={t} prefix="level_"
                         options={data.difficulties} onChange={(difficulty) => set({ difficulty })} />

            <Switch label={t("home_only")} checked={query.home} onChange={(home) => set({ home })} />
            {hasProfile && <Switch label={t("fits_only")} checked={query.fits} onChange={(fits) => set({ fits })} />}

            <div className="sheet-actions">
              <button type="button" className="button-link"
                      onClick={() => set({ equipment: null, difficulty: null, home: false, fits: false })}>
                {t("reset_filters")}
              </button>
              <button type="button" className="button-primary" onClick={() => { haptic.tap(); setSheet(false); }}>
                {t("show_results", { n: data.items.length })}
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}

function FilterGroup({ label, value, options, prefix, t, onChange }: {
  label: string; value: string | null; options: string[]; prefix: string; t: T;
  onChange: (value: string | null) => void;
}) {
  return (
    <fieldset className="filter-group">
      <legend>{label}</legend>
      <div className="chips wrap" role="radiogroup" aria-label={label}>
        {[null, ...options].map((o) => (
          <button key={o ?? "any"} type="button" role="radio" aria-checked={value === o}
                  className={"chip" + (value === o ? " chip-on" : "")}
                  onClick={() => { haptic.select(); onChange(o); }}>
            {o ? t((prefix + o.replace(/ /g, "_")) as TextKey) : t("any")}
          </button>
        ))}
      </div>
    </fieldset>
  );
}

function Switch({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <button type="button" role="switch" aria-checked={checked} className="switch-row"
            onClick={() => { haptic.select(); onChange(!checked); }}>
      <span>{label}</span>
      <span className={"switch" + (checked ? " switch-on" : "")}><span /></span>
    </button>
  );
}
