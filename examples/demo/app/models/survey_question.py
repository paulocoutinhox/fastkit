from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from fastkit_db.base import Base, PrimaryKeyMixin, TimestampMixin


class SurveyQuestion(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "demo_survey_question"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    survey_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("demo_survey.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    def display_label(self) -> str:
        return self.name
