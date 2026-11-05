from abc import ABC, abstractmethod

from services.report_document import ReportDocument


class ReportExporter(ABC):
    """A format a report can be taken away in, which a report lists among its exporters and which any report may add one of its own to."""

    # The segment of the address the file is asked for at, written the way every other segment of an address is.
    code: str = ""

    # The catalogue key of the button that asks for it.
    label: str = ""

    media_type: str = ""
    extension: str = ""

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        # A format missing any of these answers a file nobody can name, open or ask for, so it fails where it is written.
        if not (cls.code and cls.label and cls.media_type and cls.extension):
            raise TypeError(f"{cls.__name__} declares a code, a label, a media type and an extension")

    @abstractmethod
    def render(self, document: ReportDocument) -> bytes:
        """The file itself, written away from the loop that answers every other request because writing one costs cpu."""
