# The site

The public site is rendered by the same process that answers the API. A crawler and a visitor read the same HTML, because there is no client-side application deciding what a page is.

## Addresses

No page carries a language. A page is one address, read in the language of whoever opens it:

```
/                          the home
/about
/contact
/plans
/products
/products/{slug}
/gallery
/gallery/{tag}
/content/{tag}
/newsletter
/newsletter/confirm/{token}
/newsletter/unsubscribe/{token}
/account/…                 everything behind a session
/checkout/…                what a gateway sends the buyer back to
/language                  POST: the language a visitor chose
/cookies                   what a visitor allows the site to keep
/sitemap.xml
/robots.txt
```

A tag nothing answers for is a page that does not exist. `/about` is a named address for the `about`
tag, so the text of it is a content record an operator edits like any other page.

## Which language a page is written in

A cascade that stops at the first thing that answers:

| Order | Where it comes from | Why |
| --- | --- | --- |
| 1 | the account | somebody who chose once reads the same language on the next device |
| 2 | the `fastkit_language` cookie | the only place left for somebody with no account |
| 3 | `Accept-Language` | what the browser asked for, for somebody who never chose |

Choosing is a POST, because choosing writes: `POST /language` sets the cookie, sets `language_id` on the
account when there is a session, and sends the visitor back to the page they came from. The footer draws
one flag per language offered, and the account has the same choice at `/account/language`.

## The menu says where you are

A menu item is marked when the page being read is the one that address opens or any page below it, so
`/gallery/office` marks Gallery and `/account/purchases` marks the account. The mark is weight, an
underline and `aria-current="page"`, so it is not carried by colour alone.

The home is the one address that only marks itself: every page of the site sits below it, so marking it
by that rule would mark it everywhere.

## The account

`/account` is a list of options rather than a screen: the avatar, the name and the balance of every
currency, and below it one row per page — personal data, address, language, password, subscriptions,
purchases, products and credits. Each opens a page, and each page goes back to the list.

The address form starts with the country, because the country is what decides whether the postal code can
be looked up. A country that declares a provider gets a lookup on blur that fills only what is still
empty, and a country that declares none draws a plain field.

A phone number is written the way its country writes it, and the shape is a column of the country the
same way the provider is. A zero of the mask is a digit somebody types and everything else is literal,
so Brazil ships as `(00) 00000-0000`. The country of an account is the one it writes its address in, and
an account with no address types into a plain field. What is stored is the number rather than the shape
it was written in.

## The newsletter

Nobody is on the list unless the address itself said so. A subscription is written as pending, the address is
sent a link, and only the click turns it on. The same token is how it leaves.

It has a page of its own rather than a field in the footer, and the reason is the challenge: a captcha drawn
in the footer would be a challenge minted on every page of the site, for a box almost nobody uses.

An address that has not answered yet is written to once an hour and no more. Double opt-in stops somebody
signing another person up and does nothing about writing to them, so without a window an open form is a way
to mail whoever you like as fast as the rate limit allows.

## Cookies

Nothing beyond what the site needs to answer you is kept before somebody says so. The categories are
`necessary`, `preferences`, `analytics` and `marketing`, and `site.consent.optional` says which ones this
environment asks about. `necessary` is never among them: nobody is asked about what makes the page exist.

Refusing everything is one click exactly like allowing it, and both buttons of the notice carry the same
weight. Beside the notice there is a page — `/cookies`, linked from the footer — where the answer is made and
made again, because a notice that disappears once answered would be the only chance to change your mind. The
text of the policy is a content record with the tag `cookies`, edited from the admin like any other page.

The answer is written together with the version of the question. Raising `site.consent.version` asks everybody
again, and a cookie written before it does not answer for what is asked today. A category the environment
stopped offering also stops being allowed, even where an old cookie still names it.

The consent has consequences, or it is decoration. `fastkit_language` is the only cookie of preference this
site writes, and it outlives the visit only where somebody allowed it — without that the language chosen still
holds for the visit and nothing is kept afterwards. Answering again rewrites what was already there, so
withdrawing shortens the cookie that existed instead of leaving it for another year.

Banner views and clicks use a separate signed, `httponly` visitor name, and that cookie exists only while
analytics consent is allowed. A banner counts one view and one click per visitor per day. With no analytics
consent the link still works and no count is written, and withdrawing consent deletes the visitor name.

## Promoted spaces

A banner belongs to a placement, and a placement is asked for on its own: the home of the site and three
spaces an application draws. It carries an availability window, a position, an image and a destination.

It also carries a language, by the same rule every catalogue here follows: a banner naming no language is
the banner of every reader, exactly as a row naming no tenant belongs to every tenant. The site passes the
language of the page and the API the one in `Accept-Language`.

A client addresses a banner by its `uuid`, never by the row id, and counts against that name:

| | |
| --- | --- |
| `GET /api/banners/active?placement=` | what is live right now for this tenant and language |
| `POST /api/banners/{uuid}/view` | count that it was seen |
| `POST /api/banners/{uuid}/click` | count that it was followed |
| `GET /api/meta/visitor` | a signed name an application keeps and sends back |

One visitor counts once a day for one banner, and a unique key over banner, kind, visitor and day is what
makes a repeat the same row rather than a second count. The totals on the banner survive the retention
window that prunes the impressions themselves.

The site counts through that same API rather than a route of its own. A view is counted when the banner
reaches the screen, and the click leaves with `keepalive` so it never holds the link back. Without
JavaScript the link works and nothing is counted. See [Cookies](#cookies) for what counting requires.

## When a form is refused

A form of the site never leaves through the error handler of the API. A challenge answered wrongly draws the
page again with the reason next to the field and a fresh challenge. A stale CSRF token sends the visitor back
to the page the form was drawn on, where a token this site just issued is waiting.

## Which tenant a request belongs to

The host says it. `Tenant.domain` is unique, so the site of `acme.com` is the tenant that declares it. A machine with no domain of its own — a laptop, a container behind a proxy that has not been pointed yet — names one in `site.default_tenant`. With no default and no match there is no site, and the answer says so.

## The session

Signing in mints the same JWT the API answers with and keeps it in an `httponly` cookie. The page never reads it and no script can. Signing out deletes it, and changing the password mints a new one so this device stays in while every other is put out.

## Forms

| Guard | How |
| --- | --- |
| CSRF | the same random value in a cookie and in a hidden field, and only a page of this site can read one to fill the other |
| Captcha | whatever the environment declares, checked before anything is written |
| Validation | the same Pydantic schemas the API answers by, read back as a map the page marks a field with |

A write answers a redirect, so reloading never sends a form twice. What the next page should say travels in a signed flash cookie that is read once.

## SEO

Every page carries a `<title>`, a description, a canonical link and Open Graph tags. The home carries the organization as JSON-LD. `sitemap.xml` lists one entry per page — every page that answers the same to everybody — plus one per content, gallery and product. The canonical link names the address of the page and never the one the visitor arrived at, so a share carrying a tracking parameter does not become a page of its own. There is no `hreflang` and no address per language, because there is no address per language to point at.

## Assets

The `webapps/site` build produces exactly two files, under fixed names:

```
webapps/site/dist/styles.css
webapps/site/dist/scripts.js
```

They are served under `/static`, and the version of the application is what busts a cache. The classes come from the Jinja templates, which is why the Tailwind build reads `templates/` through an `@source` directive.

The JavaScript is progressive enhancement and nothing else: a menu that opens on a narrow screen, a notice that closes, the name of a chosen file in an upload field, a postal code that fills what is still empty, a number written in the shape its country writes it in, a form that leaves only once however many times it is pressed, and the reCAPTCHA token minted right before a form is sent. Every page works without it.

## Light and dark

The site draws with [DaisyUI](https://daisyui.com), which is Tailwind and no JavaScript at all. Two themes
are built: `light`, and `black` for a device that asked for a dark one.

A visitor chooses with the button in the header, which is a form and works without JavaScript. The choice
lives in the `fastkit_theme` cookie, so the server writes `data-theme` on the page and nothing ever draws
light and then turns. Like the language, it is a preference: it outlives the visit only where the visitor
allowed the `preferences` category.

Two things about the themes are adjusted through the plugin's own API, in `webapps/site/src/style.css`:
the black theme ships monochrome, where a primary button is a grey and a card is the same black as the
page, and the light theme tunes `error`, `success` and `warning` to be filled behind white text, which
leaves them under 3:1 where this site writes them as text.

The colour of the brand is stated once, in `config/base.py`, and both builds derive their palette from
it. Change `brand_hue` and the site and the panel follow.

## Overriding a template per tenant

A template is looked for in the tenant's folder first and in the shared one after:

```
templates/tenants/acme/site/pages/home.html   what this tenant draws
templates/global/site/pages/home.html         what everybody else draws
```

Nothing has to be duplicated to change one page of one brand.
