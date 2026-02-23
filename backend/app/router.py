import importlib
import pkgutil
from app.extractors.base import BaseExtractor
from app.extractors import __path__ as extractors_path


class ExtractorRouter:
    def __init__(self):
        self._extractors: list[BaseExtractor] = []
        self._discover()

    def _discover(self):
        """Auto-discover all extractor modules."""
        for _, name, _ in pkgutil.iter_modules(extractors_path):
            if name == "base":
                continue
            module = importlib.import_module(f"app.extractors.{name}")
            for attr in dir(module):
                cls = getattr(module, attr)
                if (
                    isinstance(cls, type)
                    and issubclass(cls, BaseExtractor)
                    and cls is not BaseExtractor
                ):
                    self._extractors.append(cls())

    def resolve(self, url: str) -> BaseExtractor | None:
        """Find the extractor that handles this URL."""
        for extractor in self._extractors:
            if extractor.matches(url):
                return extractor
        return None

    @property
    def supported_platforms(self) -> list[str]:
        return [e.platform_name for e in self._extractors]
