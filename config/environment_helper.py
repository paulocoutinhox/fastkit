from config.settings import Settings


class EnvironmentHelper:
    @staticmethod
    def derive(base: Settings, **overrides) -> Settings:
        """An environment starts from the one below it and states only what it changes, rebuilt so an override revalidates."""
        return Settings(**{**base.model_dump(), **overrides})
