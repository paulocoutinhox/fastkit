from fastkit_reports.contracts.definition import ReportDefinition


class ReportRegistry:
    def __init__(self):
        self._definitions: dict[str, ReportDefinition] = {}

    def register(self, definition: ReportDefinition) -> None:
        if definition.name in self._definitions:
            raise ValueError(f"report '{definition.name}' is already registered")

        self._definitions[definition.name] = definition

    def get(self, name: str) -> ReportDefinition:
        definition = self._definitions.get(name)

        if definition is None:
            raise KeyError(f"report '{name}' is not registered")

        return definition

    def names(self) -> list[str]:
        return list(self._definitions.keys())
