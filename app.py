from fastapi import FastAPI

from helpers import cors, errors, head, headers, locale, log, payload, rate_limiter, router, sentry, site, static, tracing
from helpers.lifespan import lifespan
from helpers.settings import settings
from routes.site.base import broke, not_found

log.setup()

# The tracker is armed before the app exists, so a failure while it is being built is reported too.
sentry.setup()

app = FastAPI(title=settings.name, version=settings.version, lifespan=lifespan)

# A middleware added later wraps the ones before it, so this reads from the innermost out.
# The failure of a request becomes an answer innermost, so every middleware around it stamps that answer too, and the site draws the page for an address that names nothing.
errors.setup(app, not_found, broke)
site.setup(app, not_found)
rate_limiter.setup(app)
cors.setup(app)
# A body past the ceiling is refused before the application reads a byte of it, and inside what translates and stamps every answer so the refusal carries all of it.
payload.setup(app)
locale.setup(app)
tracing.setup(app)
headers.setup(app)
head.setup(app)

router.setup(app)

# The admin, the build and the local media are mounted before the site, which is what takes every path that is left.
static.setup(app)
router.setup_site(app)
