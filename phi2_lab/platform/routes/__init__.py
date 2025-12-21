"""Platform API routers."""

from .contributors import router as contributors_router
from .datasets import router as datasets_router
from .findings import router as findings_router
from .geometry import router as geometry_router
from .results import router as results_router
from .stats import router as stats_router
from .tasks import router as tasks_router
from .admin import router as admin_router

__all__ = [
    "admin_router",
    "contributors_router",
    "datasets_router",
    "findings_router",
    "geometry_router",
    "results_router",
    "stats_router",
    "tasks_router",
]
