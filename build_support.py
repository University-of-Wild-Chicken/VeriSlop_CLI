"""Copy canonical runtime resources into built distributions without source copies."""
from pathlib import Path

from setuptools.command.build_py import build_py


EXAMPLE_FILES = (
    "request.txt",
    "draft.json",
    "interpretation.json",
    "formalization/Contract.lean",
    "formalization/formalization.json",
    "python/bounded_increment.py",
    "python/bindings.json",
)


class BuildPy(build_py):
    """Keep repository schemas/examples canonical and package their exact bytes."""

    def run(self):
        super().run()
        root = Path(__file__).resolve().parent
        resources = [(path, Path("schemas") / path.name)
                     for path in sorted((root / "schemas").glob("*.schema.json"))]
        if not resources:
            raise FileNotFoundError("The source distribution is missing schemas/*.schema.json")
        resources += [(root / "examples" / name, Path("examples") / name)
                      for name in EXAMPLE_FILES]
        for source, relative in resources:
            target = Path(self.build_lib) / "verislop" / relative
            self.mkpath(str(target.parent))
            self.copy_file(str(source), str(target))
