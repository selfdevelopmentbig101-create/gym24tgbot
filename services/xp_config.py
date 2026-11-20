"""
Levels, XP and character rules: the ONE place to tune them.

XP is calculated from what you already logged (nothing extra is stored):
  total XP = workouts + PRs + weeks your weekly goal was met.
Every profile starts at Rookie (level 1) with 0 XP, no matter what experience
was picked during onboarding - experience only shapes the training plan.
"""
from services import energy_config

# (level key, XP needed). The Mini App translates level_<key>.
# A consistent 3-workouts-a-week trainee with weekly goals met earns ~260 XP/week:
# Rookie -> Beginner after ~2 weeks, Regular ~7, Advanced ~17, Pro ~35 weeks.
LEVELS: tuple[tuple[str, int], ...] = (
    ("rookie", 0),
    ("beginner", 600),
    ("regular", 1800),
    ("advanced", 4500),
    ("pro", 9000),
)

XP_PER_WORKOUT = 60     # a finished workout with at least one working set
XP_PER_PR = 30          # each new personal record (estimated 1RM)
XP_PER_GOAL_WEEK = 80   # each week (Mon-Sun) with at least your planned number of workouts

# Character mood and energy
RECOVERY_HOURS = 24          # energy is back to 100% this long after a workout
CELEBRATE_HOURS = 3          # celebrating for this long after finishing a workout...
CELEBRATE_PR_HOURS = 12      # ...or longer if that workout had a PR
TIRED_BELOW = energy_config.LOW_ENERGY  # energy under this -> tired
