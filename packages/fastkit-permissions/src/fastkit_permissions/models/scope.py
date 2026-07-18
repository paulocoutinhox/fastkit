from enum import Enum


class PermissionScope(str, Enum):
    global_ = "global"
    tenant = "tenant"
    own = "own"
    custom = "custom"
