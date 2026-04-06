"""
Minimal compatibility shim for packages that still import pkg_resources
only to look up their own installed version.

This keeps small legacy dependencies working on newer Python environments
without pulling in the full setuptools pkg_resources module at runtime.
"""

from importlib.metadata import version, PackageNotFoundError


class Distribution:
    def __init__(self, project_name: str):
        self.project_name = project_name
        try:
            self.version = version(project_name)
        except PackageNotFoundError:
            self.version = "0"


def get_distribution(project_name: str) -> Distribution:
    return Distribution(project_name)
