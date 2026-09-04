from fastapi import FastAPI

from helpers import cors, errors, head, headers, locale, log, payload, rate_limiter, router, sentry, site, static, tracing
from helpers.lifespan import lifespan
from helpers.settings import settings

log.setup()

# The tracker is armed before the app exists, so a failure while it is being built is reported too.
sentry.setup()

app = FastAPI(title=settings.name, version=settings.version, lifespan=lifespan)
rate_limiter.setup(app)
cors.setup(app)
locale.setup(app)
tracing.setup(app)
headers.setup(app)
head.setup(app)
# Added last so it wraps everything else: a body past the ceiling is refused at the door and nothing behind it holds one.
payload.setup(app)
# The site draws the page for an address that names nothing, and this is where the two are introduced.
errors.setup(app, site.not_found, site.broke)
site.setup(app)

router.setup(app)

# The admin, the build and the local media are mounted before the site, which is what takes every path that is left.
static.setup(app)
router.setup_site(app)
