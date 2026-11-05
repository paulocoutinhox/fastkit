"""What a postal code stands for, in the shape the address form of this side is written in."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PostalAddress:
    line1: str = ""
    district: str = ""
    city: str = ""
    state: str = ""
