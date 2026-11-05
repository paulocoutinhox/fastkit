from reports.purchases_report import PurchasesReport
from reports.subscriptions_report import SubscriptionsReport
from services.report import Report

# Every report the panel offers, by the code it answers at, which is the one place a report is made known.
REPORTS: dict[str, Report] = {report.code: report for report in (PurchasesReport(), SubscriptionsReport())}
