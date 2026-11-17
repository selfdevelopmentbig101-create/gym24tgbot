"""
Applies the small edits of the guided-workout change to existing files.

Run it ONCE from the project root (the folder with bot.py), after copying the new files
from this zip into the project:

    python apply_patches.py

It checks every edit first; if any expected piece of code is not found (for example the file
was changed since), it stops WITHOUT touching anything and tells you which one. Running it a
second time is safe: edits that are already applied are skipped. Line endings (LF / CRLF)
are kept. It never touches .env or any secrets.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# file -> list of (old text, new text). `old` must appear exactly once.
PATCHES: dict[str, list[tuple[str, str]]] = {
    # ---------------------------------------------------------------- Mini App
    "miniapp/src/lib/router.ts": [
        (" *   /workout/live          live logger for the workout in progress\n",
         " *   /workout/live          live logger for the workout in progress\n"
         " *   /workout/go            guided workout: countdown, exercise screen, rest, summary\n"),
        ('  | { name: "workoutLive" }\n',
         '  | { name: "workoutLive" }\n  | { name: "workoutGuided" }\n'),
        ('  if (parts[0] === "workout") return parts[1] === "live" ? { name: "workoutLive" } : { name: "workout" };\n',
         '  if (parts[0] === "workout") {\n'
         '    if (parts[1] === "live") return { name: "workoutLive" };\n'
         '    if (parts[1] === "go") return { name: "workoutGuided" };\n'
         '    return { name: "workout" };\n'
         '  }\n'),
        ('    case "workoutLive": return "/workout/live";\n',
         '    case "workoutLive": return "/workout/live";\n    case "workoutGuided": return "/workout/go";\n'),
    ],
    "miniapp/src/App.tsx": [
        (" *     /workout/live         live logger (rest timer, supersets, notes, PRs, finish summary)\n",
         " *     /workout/live         live logger (rest timer, supersets, notes, PRs, finish summary)\n"
         " *     /workout/go           guided workout (countdown, exercise screen, rest timer, summary)\n"),
        ('import { TrainDay } from "./screens/TrainDay";\n',
         'import { TrainDay } from "./screens/TrainDay";\nimport { Workout } from "./screens/Workout";\n'),
        ('    } else if (route.name === "workoutLive") {\n      screen = <Logger t={t} />;\n',
         '    } else if (route.name === "workoutLive") {\n      screen = <Logger t={t} />;\n'
         '    } else if (route.name === "workoutGuided") {\n'
         '      screen = <Workout t={t} attribution={state.config.attribution} />;\n'),
        ('        {screen}\n        <TabBar current={route} t={t} />\n',
         '        {screen}\n        {route.name !== "workoutGuided" && <TabBar current={route} t={t} />}\n'),
    ],
    "miniapp/src/screens/TrainDay.tsx": [
        ('import { bindNativeBack, haptic } from "../lib/telegram";\n',
         'import { bindNativeBack, haptic } from "../lib/telegram";\nimport { markFreshStart } from "../lib/guidedSession";\n'),
        ('      await startWorkout(selected, force);\n      haptic.success();\n      navigate({ name: "workoutLive" });\n',
         '      const started = await startWorkout(selected, force);\n      markFreshStart(started.id);   // opens with the 3-2-1 countdown\n'
         '      haptic.success();\n      navigate({ name: "workoutGuided" });\n'),
        ('onClick={() => { haptic.tap(); navigate({ name: "workoutLive" }); }}>{t("train_continue")}</button>',
         'onClick={() => { haptic.tap(); navigate({ name: "workoutGuided" }); }}>{t("train_continue")}</button>'),
    ],
    "miniapp/src/screens/Home.tsx": [
        ('import { bindNativeBack, haptic } from "../lib/telegram";\n',
         'import { bindNativeBack, haptic } from "../lib/telegram";\nimport { markFreshStart } from "../lib/guidedSession";\n'),
        ('      await startWorkout(view.next_workout.index);\n      haptic.success();\n      navigate({ name: "workoutLive" });\n',
         '      const started = await startWorkout(view.next_workout.index);\n      markFreshStart(started.id);   // opens with the 3-2-1 countdown\n'
         '      haptic.success();\n      navigate({ name: "workoutGuided" });\n'),
        ('onClick={() => { haptic.tap(); navigate({ name: "workoutLive" }); }}>{t("home_continue")}</button>',
         'onClick={() => { haptic.tap(); navigate({ name: "workoutGuided" }); }}>{t("home_continue")}</button>'),
    ],
    "miniapp/src/lib/telegram.ts": [
        ("  disableVerticalSwipes?(): void;\n",
         "  disableVerticalSwipes?(): void;\n"
         "  showConfirm?(message: string, callback: (confirmed: boolean) => void): void;\n"),
        ("/** Telegram's user id, ONLY for keying local drafts on this device. Never sent to the API. */\n",
         "/** Ask a yes/no question: Telegram's own popup when available, the browser's otherwise. */\n"
         "export function confirmDialog(message: string, onResult: (confirmed: boolean) => void): void {\n"
         "  const app = getWebApp();\n"
         "  if (app?.showConfirm && app.isVersionAtLeast(\"6.2\")) {\n"
         "    try {\n"
         "      app.showConfirm(message, onResult);\n"
         "      return;\n"
         "    } catch {\n"
         "      /* fall back to the browser's dialog */\n"
         "    }\n"
         "  }\n"
         "  onResult(window.confirm(message));\n"
         "}\n"
         "\n"
         "/** Phone vibration where the browser allows it (mostly Android). Haptics cover the rest. */\n"
         "export function vibrate(pattern: number | number[]): void {\n"
         "  safe(() => navigator.vibrate?.(pattern));\n"
         "}\n"
         "\n"
         "/** Telegram's user id, ONLY for keying local drafts on this device. Never sent to the API. */\n"),
    ],
    "miniapp/src/lib/trainApi.ts": [
        ("export interface WorkoutItem {\n",
         "/** Exercise pictures for the guided screen (start + peak frames loop; kind is null without images). */\n"
         "export interface ItemMedia {\n"
         "  kind: \"animation\" | \"photo\" | null;\n"
         "  start: string | null;\n"
         "  peak: string | null;\n"
         "  still: string | null;\n"
         "}\n\n"
         "export interface WorkoutItem {\n"),
        ("  rest_seconds: number;\n  note: string | null;\n",
         "  rest_seconds: number;\n  media?: ItemMedia | null;\n  note: string | null;\n"),
    ],
    "miniapp/src/i18n/index.ts": [
        ('import homeRu from "./home.ru.json";\n',
         'import homeRu from "./home.ru.json";\n'
         'import guidedEn from "./guided.en.json";\n'
         'import guidedRu from "./guided.ru.json";\n'
         'import guidedUz from "./guided.uz.json";\n'),
        ("...profileEn, ...homeEn };", "...profileEn, ...homeEn, ...guidedEn };"),
        ("...homeRu }, uz };", "...homeRu, ...guidedRu }, uz: { ...uz, ...guidedUz } };"),
    ],
    # ----------------------------------------------------------------- Backend
    "services/train.py": [
        ('ImageFor = Callable[[str], "str | None"]   # exercise id -> thumbnail URL\n',
         'ImageFor = Callable[[str], "str | None"]   # exercise id -> thumbnail URL\n'
         'MediaFor = Callable[[str], "dict | None"]  # exercise id -> {"kind", "start", "peak", "still"} (guided screen)\n'),
        ("async def overview(session: AsyncSession, user: User, image_for: ImageFor) -> dict:\n",
         "async def overview(session: AsyncSession, user: User, image_for: ImageFor,\n"
         "                   media_for: MediaFor | None = None) -> dict:\n"),
        ('        "active": await workout_view(session, user, active, image_for) if active else None,\n',
         '        "active": await workout_view(session, user, active, image_for, media_for) if active else None,\n'),
        ("async def workout_view(session: AsyncSession, user: User, ws: WorkoutSession, image_for: ImageFor) -> dict:\n",
         "async def workout_view(session: AsyncSession, user: User, ws: WorkoutSession, image_for: ImageFor,\n"
         "                       media_for: MediaFor | None = None) -> dict:\n"),
        ('            "equipment": ex.equipment, "image": image_for(ex.id),\n            "sets": item["sets"],',
         '            "equipment": ex.equipment, "image": image_for(ex.id),\n'
         '            "media": media_for(ex.id) if media_for else None,\n'
         '            "sets": item["sets"],'),
    ],
    "api/routes/train.py": [
        ("async def _view(request: Request, user: User, session: AsyncSession, ws) -> dict:\n"
         "    return await train.workout_view(session, user, ws, _images(request))\n",
         "def _media(request: Request):\n"
         "    \"\"\"Start/peak/still image URLs of an exercise, for the guided workout screen.\"\"\"\n"
         "    folder = request.app.state.exercise_images\n"
         "\n"
         "    def build(exercise_id: str) -> dict:\n"
         "        found = library.media(exercise_id, folder)\n"
         "        return {\"kind\": found.kind, \"start\": found.start, \"peak\": found.peak, \"still\": found.still}\n"
         "\n"
         "    return build\n"
         "\n"
         "\n"
         "async def _view(request: Request, user: User, session: AsyncSession, ws) -> dict:\n"
         "    return await train.workout_view(session, user, ws, _images(request), _media(request))\n"),
        ("    return await _guard(train.overview(session, user, _images(request)))\n",
         "    return await _guard(train.overview(session, user, _images(request), _media(request)))\n"),
    ],
}


def read(path: Path) -> tuple[str, bool]:
    raw = path.read_bytes().decode("utf-8")
    crlf = "\r\n" in raw
    return raw.replace("\r\n", "\n"), crlf


def main(root: Path = ROOT) -> int:
    results: dict[Path, tuple[str, bool]] = {}
    problems: list[str] = []
    for name, edits in PATCHES.items():
        path = root / name
        if not path.is_file():
            problems.append(f"{name}: file not found (run this from the project root)")
            continue
        text, crlf = read(path)
        for old, new in edits:
            if new in text:
                continue                                   # already applied (new text contains the old)
            count = text.count(old)
            if count != 1:
                first = old.strip().splitlines()[0][:70]
                problems.append(f"{name}: expected 1 match, found {count} for: {first}")
                continue
            text = text.replace(old, new, 1)
        results[path] = (text, crlf)

    if problems:
        print("Nothing was changed. These edits could not be applied:")
        for line in problems:
            print("  -", line)
        return 1

    for path, (text, crlf) in results.items():
        out = text.replace("\n", "\r\n") if crlf else text
        path.write_bytes(out.encode("utf-8"))
        print("patched", path.relative_to(root).as_posix())
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path.cwd()))
