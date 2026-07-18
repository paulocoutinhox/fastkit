from app.admin.activity_log import ActivityLogAdmin
from app.admin.category import CategoryAdmin
from app.admin.content import ContentAdmin
from app.admin.geo_sample import GeoSampleAdmin
from app.admin.language import LanguageAdmin
from app.admin.product import ProductAdmin
from app.admin.report_run import ReportRunAdmin
from app.admin.role import RoleAdmin
from app.admin.scheduled_task import ScheduledTaskAdmin
from app.admin.showcase import ShowcaseAdmin
from app.admin.subcategory import SubcategoryAdmin
from app.admin.survey import SurveyAdmin
from app.admin.task_execution import TaskExecutionAdmin
from app.admin.tenant import TenantAdmin
from app.admin.user import UserAdmin
from app.admin.helpers import category_options, subcategory_options

ADMIN_RESOURCES = [
    UserAdmin,
    CategoryAdmin,
    SubcategoryAdmin,
    SurveyAdmin,
    ProductAdmin,
    ShowcaseAdmin,
    GeoSampleAdmin,
    TenantAdmin,
    RoleAdmin,
    LanguageAdmin,
    ContentAdmin,
    ScheduledTaskAdmin,
    TaskExecutionAdmin,
    ReportRunAdmin,
    ActivityLogAdmin,
]

__all__ = [
    "ADMIN_RESOURCES",
    "ActivityLogAdmin",
    "CategoryAdmin",
    "ContentAdmin",
    "GeoSampleAdmin",
    "LanguageAdmin",
    "ProductAdmin",
    "ReportRunAdmin",
    "RoleAdmin",
    "ScheduledTaskAdmin",
    "ShowcaseAdmin",
    "SubcategoryAdmin",
    "SurveyAdmin",
    "TaskExecutionAdmin",
    "TenantAdmin",
    "UserAdmin",
    "category_options",
    "subcategory_options",
]
