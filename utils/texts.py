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
        "/settings — edit profile, disclaimer, delete data\n"
        "/about — about this bot and credits\n"
        "/deleteme — permanently delete all your data\n"
        "/cancel — stop the current setup step\n\n"
        "Workout plans, logging and progress tracking are coming soon."
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
}

# Phase 6: add more language dicts here (or load them from files).
LANGUAGES = {"en": EN}
DEFAULT_LANGUAGE = "en"


def t(key: str, lang: str = DEFAULT_LANGUAGE, **kwargs) -> str:
    """Look up a text by key and fill in {placeholders}. Falls back to English."""
    texts = LANGUAGES.get(lang, EN)
    template = texts.get(key) or EN.get(key) or key
    return template.format(**kwargs) if kwargs else template
