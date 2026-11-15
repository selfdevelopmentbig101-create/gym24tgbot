"""
Energy and training-volume limits: the ONE place to tune them.

Based on common rules of thumb, not medical advice:
- a productive session is usually about 6-8 exercises and 15-25 hard sets;
- for muscle growth, about 10-20 hard sets per muscle group per week.
Going above these still works: Gym24 only shows a warning, it never blocks.
"""

# ---- One session ----
SESSION_ENERGY = 100            # the energy bar at the start of a workout
SESSION_EXERCISES_HIGH = 8      # more exercises than this -> "very demanding" warning
SESSION_HARD_SETS_HIGH = 25     # more hard sets than this -> "very demanding" warning
SESSION_HARD_SETS_TYPICAL = (15, 25)

# Energy one hard set costs. About 25 mixed sets use the whole bar.
SET_COST_COMPOUND = 4.8         # squats, presses, rows... (many muscles, heavy)
SET_COST_ISOLATION = 3.2        # curls, raises, extensions...
SET_COST_TIMED = 2.5            # holds like the plank

# ---- One week, per muscle group ----
WEEKLY_SETS_LOW = 10            # fewer: "low" (fine, just a smaller growth stimulus)
WEEKLY_SETS_HIGH = 20           # more: "high" warning for that muscle
SECONDARY_MUSCLE_FACTOR = 0.5   # a set counts half for the muscles that only help

# ---- Character (Stage 6) ----
LOW_ENERGY = 25                 # below this the character looks tired
