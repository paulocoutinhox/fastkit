from enum import StrEnum


class BannerPlacement(StrEnum):
    HOME = "home"
    APP_SPACE1 = "app-space1"
    APP_SPACE2 = "app-space2"
    APP_SPACE3 = "app-space3"


class BannerCountKind(StrEnum):
    VIEW = "view"
    CLICK = "click"
