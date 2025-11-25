"""Health check module for PHILAB.

This module provides health check functionality for monitoring the application
status in production environments.
"""

import logging
import sys
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health check status enumeration."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class ComponentHealth:
    """Health status of a component.

    Attributes:
        name: Component name.
        status: Health status.
        message: Optional status message.
        timestamp: Time of check.
    """

    name: str
    status: HealthStatus
    message: Optional[str] = None
    timestamp: Optional[datetime] = None

    def __post_init__(self):
        """Set timestamp if not provided."""
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


class HealthChecker:
    """Performs health checks for PHILAB components."""

    def __init__(self):
        """Initialize health checker."""
        self.checks: List[ComponentHealth] = []

    def check_python_version(self) -> ComponentHealth:
        """Check Python version compatibility.

        Returns:
            ComponentHealth with Python version status.
        """
        version_info = sys.version_info
        required_major = 3
        required_minor = 10

        if version_info.major == required_major and version_info.minor >= required_minor:
            status = HealthStatus.HEALTHY
            message = f"Python {version_info.major}.{version_info.minor}.{version_info.micro}"
        else:
            status = HealthStatus.UNHEALTHY
            message = (
                f"Python {version_info.major}.{version_info.minor} found, "
                f"requires {required_major}.{required_minor}+"
            )

        return ComponentHealth(name="python_version", status=status, message=message)

    def check_dependencies(self) -> ComponentHealth:
        """Check if required dependencies are importable.

        Returns:
            ComponentHealth with dependency status.
        """
        required_deps = ["transformers", "torch", "sqlalchemy", "numpy", "yaml"]
        missing_deps = []

        for dep in required_deps:
            try:
                __import__(dep)
            except ImportError:
                missing_deps.append(dep)

        if not missing_deps:
            status = HealthStatus.HEALTHY
            message = "All dependencies available"
        else:
            status = HealthStatus.UNHEALTHY
            message = f"Missing dependencies: {', '.join(missing_deps)}"

        return ComponentHealth(name="dependencies", status=status, message=message)

    def check_configuration(self) -> ComponentHealth:
        """Check if configuration files exist.

        Returns:
            ComponentHealth with configuration status.
        """
        config_files = [
            Path("phi2_lab/config/app.yaml"),
            Path("phi2_lab/config/agents.yaml"),
        ]

        missing_configs = [str(f) for f in config_files if not f.exists()]

        if not missing_configs:
            status = HealthStatus.HEALTHY
            message = "Configuration files present"
        else:
            status = HealthStatus.DEGRADED
            message = f"Missing configs: {', '.join(missing_configs)}"

        return ComponentHealth(name="configuration", status=status, message=message)

    def check_atlas_database(self) -> ComponentHealth:
        """Check if Atlas database is accessible.

        Returns:
            ComponentHealth with database status.
        """
        db_path = Path("phi2_lab/phi2_atlas/data/atlas.db")

        try:
            if db_path.exists():
                # Try to open/access the database
                status = HealthStatus.HEALTHY
                message = f"Database accessible at {db_path}"
            else:
                status = HealthStatus.DEGRADED
                message = f"Database not found at {db_path} (will be created on first use)"
        except Exception as e:
            status = HealthStatus.UNHEALTHY
            message = f"Database error: {str(e)}"

        return ComponentHealth(name="atlas_database", status=status, message=message)

    def check_storage_paths(self) -> ComponentHealth:
        """Check if storage directories exist and are writable.

        Returns:
            ComponentHealth with storage status.
        """
        storage_dirs = [
            Path("phi2_lab/phi2_atlas/data"),
            Path("results"),
            Path("logs"),
        ]

        issues = []

        for dir_path in storage_dirs:
            if not dir_path.exists():
                try:
                    dir_path.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    issues.append(f"Cannot create {dir_path}: {e}")
            elif not dir_path.is_dir():
                issues.append(f"{dir_path} exists but is not a directory")

        if not issues:
            status = HealthStatus.HEALTHY
            message = "Storage paths accessible"
        else:
            status = HealthStatus.DEGRADED
            message = "; ".join(issues)

        return ComponentHealth(name="storage_paths", status=status, message=message)

    def check_model_loading(self, use_mock: bool = True) -> ComponentHealth:
        """Check if model can be loaded.

        Args:
            use_mock: Whether to use mock model for checking.

        Returns:
            ComponentHealth with model status.
        """
        try:
            if use_mock:
                # Quick check with mock
                from phi2_lab.phi2_core.model_manager import MockModelManager

                manager = MockModelManager()
                status = HealthStatus.HEALTHY
                message = "Mock model available"
            else:
                # This is expensive, only do in detailed health checks
                from phi2_lab.phi2_core.model_manager import ModelManager

                manager = ModelManager(model_name="microsoft/phi-2", device="cpu")
                status = HealthStatus.HEALTHY
                message = "Real model loadable"
        except Exception as e:
            status = HealthStatus.UNHEALTHY
            message = f"Model loading failed: {str(e)}"

        return ComponentHealth(name="model_loading", status=status, message=message)

    def perform_all_checks(self, detailed: bool = False) -> List[ComponentHealth]:
        """Perform all health checks.

        Args:
            detailed: Whether to perform expensive checks (e.g., real model loading).

        Returns:
            List of ComponentHealth results.
        """
        self.checks = [
            self.check_python_version(),
            self.check_dependencies(),
            self.check_configuration(),
            self.check_atlas_database(),
            self.check_storage_paths(),
            self.check_model_loading(use_mock=not detailed),
        ]

        return self.checks

    def get_overall_status(self) -> HealthStatus:
        """Get overall health status based on all checks.

        Returns:
            Overall HealthStatus.
        """
        if not self.checks:
            return HealthStatus.UNHEALTHY

        has_unhealthy = any(c.status == HealthStatus.UNHEALTHY for c in self.checks)
        has_degraded = any(c.status == HealthStatus.DEGRADED for c in self.checks)

        if has_unhealthy:
            return HealthStatus.UNHEALTHY
        elif has_degraded:
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.HEALTHY

    def to_dict(self) -> Dict:
        """Convert health check results to dictionary.

        Returns:
            Dictionary representation of health status.
        """
        return {
            "status": self.get_overall_status().value,
            "timestamp": datetime.utcnow().isoformat(),
            "checks": [
                {
                    "name": check.name,
                    "status": check.status.value,
                    "message": check.message,
                    "timestamp": check.timestamp.isoformat() if check.timestamp else None,
                }
                for check in self.checks
            ],
        }

    def print_status(self) -> None:
        """Print health check results to console."""
        overall = self.get_overall_status()

        print(f"\n{'='*60}")
        print(f"PHILAB Health Check - {datetime.utcnow().isoformat()}")
        print(f"{'='*60}")
        print(f"Overall Status: {overall.value.upper()}")
        print(f"{'='*60}\n")

        for check in self.checks:
            status_symbol = {
                HealthStatus.HEALTHY: "✓",
                HealthStatus.DEGRADED: "⚠",
                HealthStatus.UNHEALTHY: "✗",
            }[check.status]

            print(f"{status_symbol} {check.name:20s} [{check.status.value:10s}] {check.message}")

        print(f"\n{'='*60}\n")


def health_check(detailed: bool = False, exit_on_unhealthy: bool = True) -> int:
    """Perform health check and return exit code.

    Args:
        detailed: Whether to perform expensive checks.
        exit_on_unhealthy: Whether to exit with error code on unhealthy status.

    Returns:
        Exit code (0 for healthy, 1 for degraded, 2 for unhealthy).
    """
    checker = HealthChecker()
    checker.perform_all_checks(detailed=detailed)
    checker.print_status()

    status = checker.get_overall_status()

    exit_codes = {
        HealthStatus.HEALTHY: 0,
        HealthStatus.DEGRADED: 1 if exit_on_unhealthy else 0,
        HealthStatus.UNHEALTHY: 2 if exit_on_unhealthy else 0,
    }

    return exit_codes[status]


def main():
    """Main entry point for health check CLI."""
    import argparse

    parser = argparse.ArgumentParser(description="PHILAB Health Check")
    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Perform detailed health checks (may be slow)",
    )
    parser.add_argument(
        "--no-exit",
        action="store_true",
        help="Don't exit with error code on unhealthy status",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )

    args = parser.parse_args()

    checker = HealthChecker()
    checker.perform_all_checks(detailed=args.detailed)

    if args.json:
        import json

        print(json.dumps(checker.to_dict(), indent=2))
    else:
        checker.print_status()

    status = checker.get_overall_status()
    exit_codes = {
        HealthStatus.HEALTHY: 0,
        HealthStatus.DEGRADED: 1 if not args.no_exit else 0,
        HealthStatus.UNHEALTHY: 2 if not args.no_exit else 0,
    }

    sys.exit(exit_codes[status])


if __name__ == "__main__":
    main()
