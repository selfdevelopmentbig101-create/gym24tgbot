"""
All user-facing texts, in one place.

Phase 6 (multi-language) moves these into one file per language; handlers
already call t("key"), so they won't need to change.
Texts use Telegram HTML formatting (<b>bold</b>, <i>italic</i>).
"""

EN: dict[str, str] = {
    # ----- General -----
    "start_welcome_back": (
        "💪 Welcome back! Your profile is set up.\n\n"
        "/profile — your targets\n/settings — edit profile\n/help — all commands"
    ),
    "help": (
        "<b>Commands</b>\n"
        "/start — start or resume setup\n"
        "/profile — your profile and daily calorie/protein targets\n"
        "/plan — your workout plan\n"
        "/workout — start or continue today's workout\n"
        "/progress — weight, PRs and charts\n"
        "/weight — log body weight (e.g. /weight 75.4)\n"
        "/measure — log a body measurement\n"
        "/food — log meals, daily calories and protein\n"
        "/reminders — workout and weigh-in reminders\n"
        "/exercises — exercise library\n"
        "/settings — edit profile, disclaimer, delete data\n"
        "/about — about this bot and credits\n"
        "/deleteme — permanently delete all your data\n"
        "/cancel — stop the current setup step\n\n"
        "Log food: /food (or /food 650 40 for kcal and protein)."
    ),
    "about": (
        "<b>Muscle Gain Bot</b>\n"
        "Workout plans, logging, progress tracking and nutrition targets for "
        "bulking, lean bulking and recomposition.\n\n"
        "Nutrition targets use the Mifflin-St Jeor equation with a moderate surplus.\n\n"
        "<b>Credits</b>\n{attribution}"
    ),
    "need_profile": "You don't have a profile yet. Send /start to set one up (about 1 minute).",
    "cancelled": "Cancelled. Send /start to continue setup any time.",
    "nothing_to_cancel": "There's nothing to cancel.",
    "rate_limited": "⏳ Too fast — please wait a few seconds.",
    "error": "😕 Something went wrong. Please try again. If it keeps happening, send /start.",
    "stale_button": "This button is no longer active.",

    # ----- Disclaimer -----
    "disclaimer": (
        "⚠️ <b>Health disclaimer</b>\n\n"
        "This bot gives general fitness and nutrition guidance. It is <b>not medical advice</b> "
        "and does not replace a doctor, physiotherapist or registered dietitian.\n\n"
        "Consult a qualified professional before starting a new training or nutrition plan, "
        "especially if you have a medical condition, injury, eating disorder history, or are "
        "under 18, pregnant or taking medication. Stop exercising and seek help if you feel "
        "pain, dizziness or chest discomfort."
    ),
    "btn_accept_disclaimer": "✅ I understand",
    "onboarding_intro": "Great! 10 quick questions to set up your plan. Most are one tap.",

    # ----- Onboarding questions -----
    "q_goal": "<b>What's your goal?</b>\n\n"
              "• <b>Bulk</b> — maximum muscle gain, some fat gain\n"
              "• <b>Lean bulk</b> — slower gain, minimal fat\n"
              "• <b>Recomposition</b> — build muscle and lose fat at maintenance calories",
    "q_age": "<b>How old are you?</b>\nType a number, e.g. <code>27</code>",
    "q_sex": "<b>Sex</b>\nUsed only for the calorie formula.",
    "q_height_cm": "<b>Your height?</b>\nType it in cm, e.g. <code>178</code> "
                   "(also accepts <code>1.78m</code> or <code>5'10</code>)",
    "q_weight_kg": "<b>Your body weight?</b>\nType it in kg, e.g. <code>72.5</code> "
                   "(also accepts <code>160 lb</code>)",
    "q_experience": "<b>Training experience?</b>",
    "q_training_days": "<b>How many days per week can you train?</b>",
    "q_equipment": "<b>What equipment do you have?</b>",
    "q_injuries": "<b>Any injuries or limitations?</b>\n"
                  "Tap all that apply, then <b>Done</b>. We'll avoid exercises that stress them.",
    "q_diet": "<b>Diet preference?</b>",
    "current_value": "\n\nCurrent: <b>{value}</b>",
    "step_progress": "<i>Step {n}/{total}</i>\n",

    # ----- Validation errors -----
    "err_not_a_number": "Please send just a number, e.g. <code>75</code>.",
    "err_age": "Please enter an age between 16 and 80.",
    "err_height": "Please enter a height between 130 and 220 cm (e.g. <code>178</code>).",
    "err_weight": "Please enter a weight between 35 and 250 kg (e.g. <code>72.5</code>).",
    "err_generic": "That answer isn't valid. Please use the buttons.",
    "err_use_buttons": "Please tap one of the buttons above.",

    # ----- Buttons and labels -----
    "btn_back": "⬅️ Back",
    "btn_done": "✅ Done",
    "btn_none": "None",
    "btn_edit_profile": "✏️ Edit profile",
    "btn_disclaimer": "🩺 Health disclaimer",
    "btn_delete_data": "🗑 Delete my data",
    "btn_delete_confirm": "🗑 Yes, delete everything",
    "btn_delete_cancel": "Keep my data",
    "btn_back_to_profile": "⬅️ Back to profile",

    "goal_bulk": "Bulk",
    "goal_lean_bulk": "Lean bulk",
    "goal_recomp": "Recomposition",
    "sex_male": "Male",
    "sex_female": "Female",
    "sex_unspecified": "Prefer not to say",
    "experience_beginner": "Beginner (under 1 yr)",
    "experience_intermediate": "Intermediate (1–3 yrs)",
    "experience_advanced": "Advanced (3+ yrs)",
    "equipment_full_gym": "🏋️ Full gym",
    "equipment_home_dumbbells": "🏠 Home + dumbbells",
    "equipment_bodyweight": "🤸 Bodyweight only",
    "injury_shoulder": "Shoulder",
    "injury_elbow_wrist": "Elbow / wrist",
    "injury_lower_back": "Lower back",
    "injury_knee": "Knee",
    "injury_hip": "Hip",
    "injuries_none": "None",
    "diet_none": "No restrictions",
    "diet_vegetarian": "Vegetarian",
    "diet_vegan": "Vegan",
    "diet_pescatarian": "Pescatarian",
    "days_value": "{days} days",

    "field_goal": "Goal",
    "field_age": "Age",
    "field_sex": "Sex",
    "field_height_cm": "Height",
    "field_weight_kg": "Weight",
    "field_experience": "Experience",
    "field_training_days": "Training days",
    "field_equipment": "Equipment",
    "field_injuries": "Injuries",
    "field_diet": "Diet",

    # ----- Profile and targets -----
    "profile": (
        "👤 <b>Your profile</b>\n"
        "Goal: <b>{goal}</b>\n"
        "Age: <b>{age}</b> · Sex: <b>{sex}</b>\n"
        "Height: <b>{height} cm</b> · Weight: <b>{weight} kg</b>\n"
        "Experience: <b>{experience}</b>\n"
        "Training: <b>{days} days/week</b> · <b>{equipment}</b>\n"
        "Injuries: <b>{injuries}</b>\n"
        "Diet: <b>{diet}</b>"
    ),
    "targets": (
        "🍽 <b>Daily targets</b>\n"
        "Calories: <b>{calories} kcal</b> ({surplus_text})\n"
        "Protein: <b>{protein} g</b> ({protein_basis})\n\n"
        "<i>Maintenance (TDEE) ≈ {tdee} kcal · BMR ≈ {bmr} kcal</i>\n"
        "{gain_text}"
    ),
    "surplus_positive": "+{kcal} kcal surplus",
    "surplus_zero": "maintenance",
    "protein_per_kg": "≈{g_per_kg} g/kg",
    "protein_per_reference_kg": "{g_per_kg} g/kg of a healthy reference weight, {basis} kg",
    "gain_range": "Aim to gain about <b>{low}–{high} kg per week</b>. "
                  "If you gain faster, you're adding mostly fat.",
    "gain_recomp": "Aim to keep your body weight roughly stable while your strength goes up.",
    "targets_footer": "<i>Estimates only — we'll fine-tune them from your weekly weigh-ins.</i>",
    "note_high_bmi_bulk": "💡 With your current body weight, <b>lean bulk</b> or "
                          "<b>recomposition</b> usually gives better results than a full bulk. "
                          "You can change your goal in /settings.",
    "note_under_18": "💡 You're under 18: please involve a parent and a doctor before changing "
                     "your diet, and focus on good technique over heavy weights.",
    "onboarding_done": "🎉 <b>All set!</b> Here's your starting point.",
    "profile_updated": "✅ Updated.",

    # ----- Settings / edit / delete -----
    "settings": "⚙️ <b>Settings</b>",
    "edit_pick_field": "Which field do you want to change?",
    "delete_confirm": (
        "⚠️ This permanently deletes <b>all</b> your data: profile, and any workouts, "
        "logs and progress. This can't be undone.\n\nAre you sure?"
    ),
    "delete_done": "✅ All your data has been deleted. Send /start if you ever want to come back.",
    "delete_nothing": "We don't have any data stored for you.",
    "delete_kept": "👍 Nothing was deleted.",

    # ----- Exercise library and cards -----
    "library_pick_group": "📚 <b>Exercise library</b>\nPick a muscle group:",
    "library_pick_group_filtered": "📚 <b>Exercise library</b>\n"
                                   "Showing exercises that fit your equipment and level. Pick a muscle group:",
    "library_empty": "No exercises in this group fit your equipment and level.",
    "no_exercises_loaded": "The exercise list isn't loaded yet. Ask the admin to run import_exercises.py.",
    "card_library_position": "📚 {pos} of {total}",
    "card_plan_position": "📋 {day} · exercise {pos} of {total}",
    "card_prescription": "<b>{sets} × {reps}</b> · rest {rest}",
    "card_form_tips": "📝 <b>Form tips</b>\n{tips}",
    "card_form_tips_missing": "📝 <i>Form tips coming soon.</i>",
    "btn_next": "⏭ Next",
    "btn_substitute": "🔄 Substitute",
    "btn_log_set": "✍️ Log set",
    "btn_back_to_groups": "⬅️ Muscle groups",
    "btn_back_to_plan": "⬅️ Plan",
    "no_substitute": "No substitute fits your equipment, level and injuries.",
    "substituted": "Swapped in your plan ✅",
    "reps_range": "{low}–{high}",
    "seconds_range": "{low}–{high} s",
    "rest_seconds": "{seconds} s",
    "rest_minutes": "{minutes} min",

    # ----- Plan -----
    "plan_header": "🗓 <b>Your plan: {split}</b> · {days} days a week",
    "plan_day_header": "<b>Day {n} · {name}</b>",
    "plan_line": "• {name} — {sets} × {reps}",
    "plan_footer": "Rest 2–3 min between sets of big lifts, 60–90 s for smaller ones. "
                   "Tap a day to go through its exercises.",
    "plan_empty": "Couldn't build a plan: the exercise list isn't loaded yet.",
    "plan_ready": "🗓 Your training plan is ready: /plan",
    "plan_rebuilt": "🗓 Your plan was rebuilt for the new settings: /plan",
    "plan_regenerated": "🔁 New plan generated.",
    "plan_changed": "Your plan has changed. Open /plan again.",
    "btn_new_plan": "🔁 New plan",
    "btn_day": "{n} · {name}",

    "split_full_body": "Full body",
    "split_upper_lower": "Upper / Lower",
    "split_upper_lower_ppl": "Upper / Lower + Push / Pull / Legs",
    "split_ppl": "Push / Pull / Legs",
    "day_full_body": "Full Body",
    "day_upper": "Upper",
    "day_lower": "Lower",
    "day_push": "Push",
    "day_pull": "Pull",
    "day_legs": "Legs",

    "muscle_chest": "Chest",
    "muscle_back": "Back",
    "muscle_shoulders": "Shoulders",
    "muscle_biceps": "Biceps",
    "muscle_triceps": "Triceps",
    "muscle_quads": "Quads",
    "muscle_hamstrings": "Hamstrings",
    "muscle_glutes": "Glutes",
    "muscle_calves": "Calves",
    "muscle_core": "Core",
    "gear_barbell": "Barbell",
    "gear_dumbbell": "Dumbbell",
    "gear_machine": "Machine",
    "gear_cable": "Cable",
    "gear_bodyweight": "Bodyweight",
    "gear_band": "Resistance band",
    "gear_ab_wheel": "Ab wheel",
    "gear_stability_ball": "Stability ball",
    "level_beginner": "Beginner",
    "level_intermediate": "Intermediate",
    "level_advanced": "Advanced",
    "move_compound": "Compound",
    "move_isolation": "Isolation",

    # ----- Workout logger -----
    "workout_overview": "🏋️ <b>Today: Day {n} · {name}</b>",
    "workout_line": "• {name} — {sets} × {reps}",
    "workout_line_last": "   <i>last: {last}</i>",
    "workout_overview_footer": "Tap <b>Start</b> to log your sets. Wrong day? Pick another below.",
    "btn_start_workout": "▶️ Start workout",
    "btn_workout": "🏋️ Start workout",
    "workout_card_header": "🏋️ <b>{day}</b> · exercise {pos} of {total}",
    "workout_target": "🎯 Target {sets} × {reps} · rest {rest}",
    "workout_last_time": "📜 Last time: {sets}",
    "workout_first_time": "📜 First time: pick a weight you could lift for about 2 more reps "
                          "than the target ({low}–{high}), with good form.",
    "workout_today": "<b>Today</b>",
    "workout_set_line": "{n}. {set}",
    "workout_next_set": "➡️ <b>Set {n} of {total}</b>",
    "workout_extra_set": "➡️ Extra set {n} (target was {total})",
    "workout_exercise_done": "✅ All sets done. Tap <b>Next</b>.",
    "workout_resting": "⏱ Resting: {time} left. I'll message you.",
    "workout_type_hint": "<i>Tip: you can also type a set, e.g. 62.5x8, or just 8 for reps.</i>",
    "workout_list": "📋 <b>Exercises</b>: tap one to jump to it.",
    "hint_add_weight": "💡 You hit {reps} on every set: add weight → <b>{weight}</b> × {low}–{high}.",
    "hint_add_reps": "💡 Same weight ({weight}), aim for <b>{reps}</b> on your weakest set.",
    "hint_repeat": "💡 Stay at {weight} and get at least {low} on every set.",
    "hint_reduce": "💡 Missed the target two workouts in a row: drop to <b>{weight}</b> and build back up.",
    "hint_add_load": "💡 You hit {high} reps on every set: add a backpack/weight vest or try a harder variation.",
    "hint_add_time": "💡 Aim for <b>{seconds} s</b> this time.",
    "btn_log": "✅ Log {set}",
    "btn_same_as_last": "🔁 Same as last time ({set})",
    "btn_undo": "↩️ Undo",
    "btn_swap": "🔄 Swap",
    "btn_next_exercise": "⏭ Next",
    "btn_exercise_list": "📋 Exercises",
    "btn_finish": "🏁 Finish",
    "btn_back_to_card": "⬅️ Back",
    "set_logged": "Logged ✅",
    "set_undone": "Removed: {set}",
    "nothing_to_undo": "No sets to undo yet.",
    "swap_after_sets": "You've already logged sets for this exercise. Swap it before the first set.",
    "swapped": "Swapped for {name}",
    "rest_over": "⏰ <b>Rest over!</b> {name}: set {n}, {set}",
    "rest_over_next": "⏰ <b>Rest over!</b> Next exercise: {name}",
    "workout_done": "🏁 <b>Workout done: {day}</b>\n⏱ {minutes} min · {sets} sets · {volume} kg lifted",
    "workout_done_line": "• <b>{name}</b>: {sets}",
    "workout_next_time": "💡 <b>Next time</b>",
    "next_add_weight": "• {name}: add weight → {weight}",
    "next_add_reps": "• {name}: same weight, aim for {reps}",
    "next_repeat": "• {name}: repeat {weight}, get {low}+ on every set",
    "next_reduce": "• {name}: drop to {weight} and build back up",
    "next_add_load": "• {name}: add load or try a harder variation",
    "next_add_time": "• {name}: aim for {seconds} s",
    "workout_next_day": "Next workout: <b>Day {n} · {name}</b>. Rest well and hit your protein 💪",
    "workout_discarded": "Workout closed. Nothing was logged, so nothing was saved.",
    "no_active_workout": "No workout in progress. Send /workout to start one.",
    "workout_ended": "This workout has ended. Send /workout to start a new one.",
    "start_workout_first": "Start a workout first: /workout",
    "err_set_weight": "Weight must be between 0 and 500 kg.",
    "err_set_reps": "Reps must be between 1 and 100 (seconds: up to 600).",
    "unit_reps": "{n} reps",
    "unit_seconds": "{n} s",
    "btn_weight_minus": "−2.5 kg",
    "btn_weight_plus": "+2.5 kg",
    "btn_reps_minus": "−1 rep",
    "btn_reps_plus": "+1 rep",
    "btn_secs_minus": "−5 s",
    "btn_secs_plus": "+5 s",
    "new_pr": "🏆 New PR! {name}: estimated 1RM {value} kg (was {previous} kg)",
    "workout_prs": "🏆 <b>New PRs:</b> {names}",

    # ----- Progress -----
    "progress_header": "📈 <b>Your progress</b>",
    "progress_weight": "⚖️ Body weight: <b>{weight} kg</b>{avg}",
    "progress_weight_avg": " (7-day average {avg} kg)",
    "progress_no_weight": "⚖️ No weigh-ins yet. Tap <b>Log weight</b>.",
    "progress_trend": "📊 Trend: <b>{trend} kg/week</b>. {verdict}",
    "progress_trend_wait": "📊 Weekly trend appears after two weeks of weigh-ins.",
    "trend_on_track": "On track ✅",
    "trend_slow": "Slower than your goal ({low}–{high} kg/week). If it stays like this for "
                  "2–3 weeks, add about 150 kcal a day.",
    "trend_fast": "Faster than your goal ({low}–{high} kg/week), so likely extra fat. "
                  "If it stays like this for 2–3 weeks, eat about 150 kcal a day less.",
    "trend_recomp_off": "Your weight is changing more than expected for recomposition. "
                        "Check you're near your calorie target.",
    "progress_workouts": "🏋️ Workouts: <b>{week}</b> in the last 7 days · <b>{month}</b> in the last 30",
    "progress_top_prs": "🏆 Best lifts (estimated 1RM):",
    "progress_pr_line": "• {name}: <b>{e1rm} kg</b> ({weight} kg × {reps})",
    "progress_measurements": "📏 Latest: {values}",
    "btn_log_weight": "⚖️ Log weight",
    "btn_log_measurement": "📏 Log measurement",
    "btn_chart_weight": "📈 Weight chart",
    "btn_chart_strength": "💪 Strength chart",
    "btn_chart_volume": "📊 Volume chart",
    "btn_chart_measure": "📏 Measurements chart",
    "btn_prs": "🏆 All PRs",
    "btn_week": "Week",
    "btn_month": "Month",
    "btn_back_to_progress": "⬅️ Progress",
    "weight_prompt": "⚖️ <b>Log body weight</b>\nAdjust and tap <b>Log</b>, or just type it (e.g. 75.4).\n"
                     "<i>Best: in the morning, after the toilet, before eating.</i>",
    "btn_save_weight": "✅ Log {value} kg",
    "weight_logged": "✅ Logged <b>{weight} kg</b>.",
    "targets_updated": "🍽 Your daily targets were updated: <b>{calories} kcal</b>, <b>{protein} g</b> protein.",
    "measure_pick": "📏 <b>Which measurement?</b>\n<i>Measure relaxed, same time of day, tape snug but not tight.</i>",
    "measure_prompt": "📏 <b>{kind}</b>: adjust and tap <b>Log</b>, or type the value in cm.",
    "measure_prompt_first": "📏 <b>{kind}</b>: type the value in cm (e.g. 82.5).",
    "btn_save_measure": "✅ Log {value} cm",
    "measure_logged": "✅ {kind}: <b>{value} cm</b> logged.",
    "err_measurement": "Please enter a value between 15 and 200 cm.",
    "measure_waist": "Waist",
    "measure_chest": "Chest",
    "measure_arm": "Arm",
    "measure_thigh": "Thigh",
    "measure_hips": "Hips",
    "strength_pick": "💪 <b>Strength chart</b>: pick an exercise:",
    "strength_none": "No weighted sets logged yet. Log a workout first: /workout",
    "chart_no_data": "Not enough data for this chart yet. Keep logging!",
    "chart_weight_title": "Body weight (last {days} days)",
    "chart_strength_title": "{name}: estimated 1RM (last {days} days)",
    "chart_volume_title": "Training volume per day (last {days} days)",
    "chart_measure_title": "Measurements (last {days} days)",
    "prs_header": "🏆 <b>Personal records</b> (estimated 1RM)",
    "prs_line": "• {name}: <b>{e1rm} kg</b> from {weight} kg × {reps} · heaviest {heaviest} kg",
    "prs_none": "No PRs yet. Log a few workouts and they'll appear here.",

    # ----- Reminders -----
    "reminders_off": "⏰ <b>Reminders</b> are off.\nTo turn them on, tap the button that shows "
                     "<b>your current time</b> (this sets your time zone):\n"
                     "<i>Or type a time zone name like Europe/Berlin.</i>",
    "reminders_tz_pick": "🌍 Tap the button that shows <b>your current time</b>:\n"
                         "<i>Or type a time zone name like Europe/Berlin (adjusts for daylight saving).</i>",
    "reminders_view": (
        "⏰ <b>Reminders</b>\n"
        "💪 Workouts: <b>{workout}</b>\n"
        "⚖️ Weigh-in: <b>{weighin}</b>\n"
        "🔔 Missed-workout nudge: <b>{nudge}</b>\n"
        "🍽 Nutrition summary: <b>{summary}</b>\n"
        "🌍 Time zone: <b>{tz}</b> (your time now {now})"
    ),
    "reminders_workout_on": "{days} at {time}",
    "reminders_off_short": "off",
    "reminders_weighin_daily": "every day at {time}",
    "reminders_weighin_weekly": "{day} at {time}",
    "reminders_nudge_on": "on, at {time} if you haven't trained",
    "reminders_tz_fixed_note": "<i>Fixed offset: re-pick it after daylight saving changes.</i>",
    "btn_rem_workout": "💪 Workouts: {state}",
    "btn_rem_days": "📅 Days",
    "btn_rem_time": "🕕 {time}",
    "btn_rem_weighin": "⚖️ Weigh-in: {state}",
    "btn_rem_weighin_day": "📅 {day}",
    "btn_rem_nudge": "🔔 Nudge: {state}",
    "btn_rem_tz": "🌍 Time zone",
    "btn_rem_all_off": "🔕 Turn all off",
    "state_on": "on",
    "state_off": "off",
    "weighin_off": "off",
    "weighin_daily": "daily",
    "weighin_weekly": "weekly",
    "rem_pick_time": "🕕 Pick a time:",
    "rem_pick_days": "📅 Tap your training days, then <b>Done</b>:",
    "rem_tz_invalid": "I don't know that time zone. Tap a button or try a name like Europe/London.",
    "rem_all_off_done": "🔕 All reminders are off. Turn them on again any time with /reminders.",
    "weekday_0": "Mon", "weekday_1": "Tue", "weekday_2": "Wed", "weekday_3": "Thu",
    "weekday_4": "Fri", "weekday_5": "Sat", "weekday_6": "Sun",
    "remind_workout": "💪 <b>Workout day!</b> Today: Day {n} · {name}.\nReady when you are.",
    "remind_weighin": "⚖️ <b>Weigh-in time</b>, ideally now, before eating.",
    "remind_nudge": "🤔 No workout today yet. Life happens! Want to move it?",
    "remind_nudge_streak": "You've missed {n} planned workouts in a row. A lighter schedule you can "
                           "stick to beats a perfect one you can't.",
    "btn_resched_tomorrow": "⏰ Tomorrow at {time}",
    "btn_resched_2days": "📅 In 2 days",
    "btn_resched_skip": "Skip this one",
    "btn_fewer_days": "📉 Switch to {n} days/week",
    "resched_done": "👍 I'll remind you {day} at {time}.",
    "resched_skipped": "👍 No problem. Rest up and get the next one.",
    "fewer_days_done": "✅ Switched to {n} days a week. Your plan and reminders were updated: /plan",
    "reminders_hint": "⏰ Want reminders for workouts and weigh-ins? /reminders",

    # ----- Nutrition -----
    "food_today": "Today",
    "food_yesterday": "Yesterday",
    "food_summary_title": "🍽 <b>{title}</b>",
    "food_kcal_line": "🔥 Calories: <b>{value}</b> / {target} kcal\n{bar}",
    "food_protein_line": "🥩 Protein: <b>{value}</b> / {target} g\n{bar}",
    "food_left": "Left: <b>{kcal} kcal</b> · <b>{protein} g</b> protein",
    "food_over": "Over by {kcal} kcal · protein left: {protein} g",
    "food_entry_line": "• {time} {name}{servings}: {kcal} kcal, {protein} g",
    "food_nothing_yet": "Nothing logged yet today. Tap a food below.",
    "food_nothing_day": "Nothing logged that day.",
    "food_week_avg": "📊 Last {days} logged days: avg <b>{kcal} kcal</b> · <b>{protein} g</b> protein",
    "food_hint_protein": "💡 Easy protein: {ideas}",
    "food_hint_over": "💡 Above target today. That's fine now and then; what counts is your weekly average.",
    "food_hint_short": "💡 {kcal} kcal short. A shake, a bowl of oats or a PB sandwich closes the gap.",
    "food_hint_great": "💪 Targets hit. Great day!",
    "food_manual_tip": "<i>Tip: type /food 650 40 to log any meal (kcal, protein).</i>",
    "food_evening_header": "🌙 <b>Daily summary</b>",
    "food_cat_protein": "🥩 Protein",
    "food_cat_carbs": "🍚 Carbs",
    "food_cat_fruit_veg": "🥦 Fruit and veg",
    "food_cat_snacks": "🥜 Snacks and fats",
    "food_cat_meals": "🍲 Meals",
    "food_cat_header": "<b>{category}</b>: tap to log 1 serving",
    "food_list_line": "• {name} ({serving}): {kcal} kcal, {protein} g",
    "food_cat_empty": "Nothing here fits your diet preference.",
    "food_logged": "✅ <b>{name}</b>{serving}{servings}: {kcal} kcal, {protein} g protein\n"
                   "<i>Different amount? Tap ×½ to ×2.</i>",
    "food_removed": "Removed: {name}",
    "food_entry_gone": "That entry no longer exists.",
    "food_edit_header": "🗑 Tap an entry to delete it:",
    "food_edit_empty": "No entries to delete.",
    "food_manual_prompt": "✍️ <b>Manual entry</b>\nType calories and protein, optionally with a name:\n"
                          "<code>650 40</code> or <code>chicken wrap 650 40</code>",
    "btn_food_manual": "✍️ Manual",
    "btn_food_edit": "🗑 Edit",
    "btn_food_prev_day": "◀️ Previous day",
    "btn_food_next_day": "Next day ▶️",
    "btn_food_back": "⬅️ Food",
    "btn_food_delete": "🗑 {name} ({kcal} kcal)",
    "btn_log_food": "🍽 Log food",
    "err_manual_format": "Please type calories then protein, e.g. <code>650 40</code> or "
                         "<code>chicken wrap 650 40</code>.",
    "err_meal_kcal": "Calories for one entry must be between 1 and 3000.",
    "err_meal_protein_range": "Protein for one entry must be between 0 and 300 g.",
    "err_meal_protein": "That's more protein than the calories allow (1 g protein = 4 kcal). "
                        "Check the numbers.",
    "reminders_summary_on": "at {time} (if you logged food)",
    "btn_rem_summary": "🍽 Summary: {state}",
}

# Phase 6: add more language dicts here (or load them from files).
LANGUAGES = {"en": EN}
DEFAULT_LANGUAGE = "en"


def t(key: str, lang: str = DEFAULT_LANGUAGE, **kwargs) -> str:
    """Look up a text by key and fill in {placeholders}. Falls back to English."""
    texts = LANGUAGES.get(lang, EN)
    template = texts.get(key) or EN.get(key) or key
    return template.format(**kwargs) if kwargs else template


def label(prefix: str, value: str, lang: str = DEFAULT_LANGUAGE) -> str:
    """
    Text for a data value, e.g. label("muscle", "quads") -> "Quads".
    Unknown values (a new muscle group in the JSON) fall back to a tidied
    version of the value itself, so new data never breaks the bot.
    """
    key = f"{prefix}_{value.replace(' ', '_').replace('-', '_')}"
    texts = LANGUAGES.get(lang, EN)
    if key in texts or key in EN:
        return t(key, lang)
    return value.replace("_", " ").replace("-", " ").capitalize()
