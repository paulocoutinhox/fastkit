from pydantic import BaseModel, Field, model_validator

from config.base import SLUG
from enums.consent_category import ConsentCategory


class ConsentSettings(BaseModel):
    """What a visitor is asked to allow, and how long the answer is kept before it is asked again."""

    cookie: str = f"{SLUG}_consent"
    max_age: int = 60 * 60 * 24 * 180

    # The answer is kept against the version it was given about, so changing what is asked asks everybody again.
    version: int = 1

    # What this instance asks about, in the order the page draws it. `necessary` is never in here: nobody is asked about it.
    optional: list[ConsentCategory] = Field(default_factory=lambda: [ConsentCategory.PREFERENCES, ConsentCategory.ANALYTICS, ConsentCategory.MARKETING])

    @model_validator(mode="after")
    def nobody_is_asked_about_what_makes_the_page_exist(self):
        if ConsentCategory.NECESSARY in self.optional:
            raise ValueError("the necessary category is what the site needs to answer at all, so it is never one a visitor is asked to allow")

        return self
