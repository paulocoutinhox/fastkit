from enum import StrEnum


class BannerPlacement(StrEnum):
    HOME = "home"
    APP_SPACE1 = "app_space1"
    APP_SPACE2 = "app_space2"
    APP_SPACE3 = "app_space3"


class BannerCountKind(StrEnum):
    VIEW = "view"
    CLICK = "click"
