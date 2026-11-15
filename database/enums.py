"""
Fixed choices used across the app. Stored in the database as plain strings
(their .value), which works the same in SQLite and PostgreSQL.
"""
from enum import Enum


class Goal(str, Enum):
    BULK = "bulk"
    LEAN_BULK = "lean_bulk"
    RECOMP = "recomp"


class Sex(str, Enum):
    MALE = "male"
    FEMALE = "female"
    # Calculator uses the midpoint of the male and female formulas.
    UNSPECIFIED = "unspecified"


class Experience(str, Enum):
    BEGINNER = "beginner"          # < 1 year of consistent training
    INTERMEDIATE = "intermediate"  # 1-3 years
    ADVANCED = "advanced"          # 3+ years


class Equipment(str, Enum):
    FULL_GYM = "full_gym"
    HOME_DUMBBELLS = "home_dumbbells"
    BODYWEIGHT = "bodyweight"


class Injury(str, Enum):
    SHOULDER = "shoulder"
    ELBOW_WRIST = "elbow_wrist"
    LOWER_BACK = "lower_back"
    KNEE = "knee"
    HIP = "hip"


class Diet(str, Enum):
    NONE = "none"
    VEGETARIAN = "vegetarian"
    VEGAN = "vegan"
    PESCATARIAN = "pescatarian"
