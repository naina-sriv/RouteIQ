import os
from dotenv import load_dotenv

load_dotenv()

OSRM_BASE = os.getenv("OSRM_BASE", "http://router.project-osrm.org")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
MAX_STOPS = int(os.getenv("MAX_STOPS", "20"))
SOLVER_TIME_LIMIT_SECONDS = int(os.getenv("SOLVER_TIME_LIMIT_SECONDS", "5"))
POSITION_STACK_API_KEY = os.getenv("POSITION_STACK_API_KEY", "")
