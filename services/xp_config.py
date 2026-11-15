"""
Levels, XP and character rules: the ONE place to tune them.

XP is calculated from what you already logged (nothing extra is stored):
  total XP = XP of your starting level + workouts + PRs + weeks your weekly goal was met.
The starting level comes from the onboarding experience answer.
"""
from services import energy_config

# (level key, XP needed). The Mini App translates level_<key>.
LEVELS: tuple[tuple[str, int], ...] = (
    ("rookie", 0),
    ("beginner", 600),
    ("regular", 1800),
    ("advanced", 4500),
    ("pro", 9000),
)

# Onboarding experience answer -> starting level (you start with that level's XP).
START_LEVEL = {"beginner": "rookie", "intermediate": "regular", "advanced": "advanced"}

XP_PER_WORKOUT = 60     # a finished workout with at least one working set
XP_PER_PR = 30          # each new personal record (estimated 1RM)
XP_PER_GOAL_WEEK = 80   # each week (Mon-Sun) with at least your planned number of workouts

# Character mood and energy
RECOVERY_HOURS = 24          # energy is back to 100% this long after a workout
CELEBRATE_HOURS = 3          # celebrating for this long after finishing a workout...
CELEBRATE_PR_HOURS = 12      # ...or longer if that workout had a PR
TIRED_BELOW = energy_config.LOW_ENERGY  # energy under this -> tired
