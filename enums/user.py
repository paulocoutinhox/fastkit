from enums.user_role import UserRole

# Who works in the panel, named one by one: derived as every role but one, a role added later would reach it the day it is written.
PANEL_ROLES = (UserRole.EDITOR, UserRole.ADMINISTRATOR)
