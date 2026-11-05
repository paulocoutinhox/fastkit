# Accounts

Who somebody is, what they reach, and how a session ends.

## Four identities, one field

An account is created with at least one of four: a username, an email, a document or a mobile phone.
Signing in takes any of them in the same field, and the API resolves which one was typed: a login carrying
a letter is a username or an email, and one made of digits and punctuation is a document or a phone. An
identity is taken when, typed as a login, it would answer for another account of the same brand — so an
eleven-digit phone equal to somebody's document is refused, like a repeated email.

A username is written with letters, digits, a dot, a dash or an underscore, carries at least one letter,
and nothing else. It is
written into the record of what an operator did, and a line of that record is read as one line — a
username carrying a line break inside it would write a second one.

An identity is unique **inside a tenant** and not across the system, so two brands may each have a
`contact@` of their own. What guarantees it is a functional unique index over `COALESCE(tenant_id, 0)`:
in a plain unique index no null equals another, and two accounts with no tenant and the same email would
both be accepted.

| Path | Resolves in | How it knows |
| --- | --- | --- |
| `POST /api/signin`, `/api/signup`, `/api/account/password-reset`, `/api/account/password-reset/confirm`, `/api/account/confirmation/{token}` | the tenant that called | the `X-Tenant-Code` header, required where the instance serves many brands and refused where it serves one |
| the site | the tenant of the host | `Tenant.domain`, where it serves many brands |
| `POST /api/admin/signin` | the brand of the host the panel was opened on, plus the global scope | `Tenant.domain`, like the site: an operator of a brand signs in on that brand's domain, and one of no brand on any |

Signing in to a tenant where the identity does not exist answers `error.invalid-credentials` — the same
as a wrong password, so the answer never says where somebody has an account. A link that arrives by mail is
looked up inside the brand it is followed on too, and a session of the site answers only on the site of the
account's own brand. The API holds to the same rule: a checkout named in a brand the account does not
belong to is refused with 403 and `error.account-of-another-brand`, and the catalogue and the event batch
read that account as nobody.

An erased account takes no write that was still on its way: a picture, a profile edit or an address that
lands after the erasure is refused with 409 and `error.account-erased`, and the picture that was already
stored leaves the bucket.

## Roles

A role is a value of `UserRole`, and `normal` is the one an account of a reader carries. `PANEL_ROLES`
names the ones that work in the panel one by one, and a role added to the enum reaches nothing until
somebody writes that it does. A set read as *every role but one* would hand the panel to whatever is
written next, on the day it is written, and a permission may never grant itself.

What a role reaches is one line on a service:

```python
class ContentService(TaggedService):
    roles = (UserRole.ADMINISTRATOR, UserRole.EDITOR)
```

The CRUD factory guards every route it builds with that declaration, and a route written by hand states
it in its own signature. Nothing else in the project decides who reaches what — see
[Admin](admin.md) for how the panel is handed the answer instead of declaring one of its own.

A catalogue that other forms point at declares one more thing, `lookup_roles`: managing a resource and
resolving it as an option of somebody else's form are different permissions.

Giving a resource to a role gives what that resource can do. The body of a content is rendered as markup
on purpose — it is what somebody writes in the editor — so **whoever reaches `contents` puts HTML, and
therefore script, on every public page of the site.** That is not a hole, it is what handing the pages
to somebody costs, and whoever hands them out has to know it.

## Groups and access rules

A role says what an account is, and a **group** says what it belongs to. Groups are a resource of the
panel, under Access: an operator writes a group, gives it a code, and adds accounts to it. A group of one
brand holds the accounts of that brand, and a group of no brand holds any account of the instance.

Whatever a surface lets in is an **access rule**, declared once and asked before the surface answers:

| Rule | Who it lets in |
| --- | --- |
| `Everyone()` | anybody, signed in or not |
| `SignedIn()` | any signed in account |
| `HasRole(UserRole.ADMINISTRATOR, ...)` | an account holding one of the roles, read from the account and never from its token |
| `InGroup("finance", ...)` | a member of one of the active groups named by code |
| `AnyOf(rule, ...)` | whoever any one of the rules lets in |
| `AllOf(rule, ...)` | whoever every one of the rules lets in |

```python
access = AnyOf(HasRole(UserRole.ADMINISTRATOR), InGroup("finance"))
```

A rule of your own is one subclass of `AccessRule` that answers `permits(user, groups)`. A rule naming
no group never costs a query, and a combination of every rule of nothing is refused where it is written,
because it would let everybody in.

A report declares its rule in code — see [Admin](admin.md#reports). A page of the site is given one in
the panel — see [Site](site.md#who-reads-a-page).

## The address answers before the account does

The `confirm_sign_up` setting decides, and it is one line of configuration. With it on — the default — an account
created by signing up is born `pending`, a message goes to the address it named, and it becomes `active`
only once that address answers. With it off, the account is active immediately and the session starts there.

| Surface | Confirmation on | Confirmation off |
| --- | --- | --- |
| `POST /api/signup` | `201` with a **null** `token`, and the account `pending` | `201` with the token |
| `POST /api/account/confirmation/{token}` | opens the account and answers a token | there is no such token, so it answers `422` |
| `POST /api/account/confirmation` | writes to the address again | nothing is waiting, and the answer is the same |

Signing up answers one shape either way: `token` is nullable, and a token of nothing is the account
saying its address has to speak first. Nothing new guards the account — the session guard already
refused `pending` before any route, with `error.account-pending`.

Where somebody was going before they had an account travels inside the letter. The wait for an address to
answer is the one stretch of the journey the browser does not cross — it may end hours later on another
device — so the link carries the destination, and the route that opens it confines the value exactly as
the sign in does. Asking for the letter again carries none, because that journey started on the
confirmation page rather than on a page that asked for a session.

An account created with a username or a phone and no address is born `active` even with confirmation on.
There is nowhere to write to, and holding it would lock it for good.

Changing the address of an account is the same question asked again. With confirmation on, the new address
waits in `pendingEmail`, receives a letter of its own, and replaces the old one only once it answers — until
then the account keeps signing in and receiving mail at the address it had. An operator writing the address
from the panel is not asked, and clears whatever was waiting.

Replacing the email invalidates recovery links sent to the previous mailbox. A replacement written by
an operator also invalidates its outstanding confirmation link. A pending replacement leaves the current
mailbox valid until the new address is confirmed.

Sending back the address the account already has, or the one already waiting, changes nothing and writes
no letter, so saving any other field of a form never cancels the change. Writing a different address
voids the letter that went out for the one before, so a letter only ever proves the address it was
written for. And answering it writes the address without starting a session: the letter proves the
mailbox and not the account, and `POST /api/account/confirmation/{token}` answers a `token` of `null` for
an address change, where it answers one for a sign up.

Asking for the message again is an open route, so it answers `204` for every login: one nobody has, one
already confirmed, and one still waiting. It also takes a window — sixty seconds by
`confirm_sign_up_interval` — and draws a new token as it takes it, so only the last message sent to an
address still opens the account it names.

**On a developer machine the letter is printed rather than sent.** Development declares the `console`
mailer, and nothing is dialled inside a request anyway: the message is written to the queue and the
`send_pending_emails` job picks it up every two minutes. So signing up locally means waiting for that
pass and then reading the link out of the server log — the feature is working, it just has nowhere to
post to. Switching `confirm_sign_up` off is the other way to develop against it.

## Optional email-code sign-in

Email-code sign-in is disabled by default. Enable `authentication.email.enabled` in the private environment configuration, then choose `site` and `admin` independently. The [configuration guide](configuration.md#optional-authentication) lists every setting and its bounds. Existing password sign-in remains available.

The site offers **Sign in with an email code** on its login page. The reader enters an address, passes the configured captcha and receives a six-digit code through the existing localized mail queue. Requesting a code creates a challenge and a queued message, never a user. Only a correct, unexpired code creates an account if the address does not already belong to one in that brand. The account is active, has the normal role, has no password, and keeps the model defaults and empty profile fields. The email itself supplies the identity.

An existing active account keeps its password and profile. A pending sign-up becomes active after the mailbox is proved, and any password supplied before that proof is cleared. Existing sessions are revoked in that activation. Blocked and erased accounts cannot sign in. A code names one tenant and one surface, so a site code never opens the admin.

The admin requires an **existing active account with a panel role**. Email confirmation never creates or promotes an operator. Create the operator with `uv run manage.py create-administrator --password …`, or assign the appropriate role through an authorized account, before using email-code sign-in there.

| API request | Purpose |
| --- | --- |
| `GET /api/auth/methods?surface=site` | Return enabled method labels without credentials. Use `surface=admin` for the panel. |
| `POST /api/auth/email/request` | Send `{ "email": "reader@example.com", "surface": "site", "captchaToken": "…", "captchaAnswer": "…" }`. Captcha fields follow the configured provider. |
| `POST /api/auth/email/confirm` | Send `{ "challenge": "…", "code": "123456", "surface": "site" }` and receive the normal token/account response. |

The request response contains `challenge`, `expiresAt` and `resendAt`. It never contains the code or whether an account exists. Site API requests use `X-Tenant-Code` under the same rules as password sign-in. Admin requests resolve the tenant from the host, including the global operator scope, and do not take a tenant selector from the body.

Codes expire after ten minutes, permit five wrong attempts and have a sixty-second resend cooldown by default. A repeated request inside the cooldown reuses the live challenge without sending another message. A resend after the cooldown replaces the token and code, invalidating the previous message. A spent or exhausted challenge cannot reopen inside its cooldown. Successful confirmation consumes the challenge atomically, so replay cannot mint another session. The database stores a keyed digest of the code, not the code itself. The private mail queue necessarily retains the message context until its normal retention removes it, and never exposes that context through the admin API.

The browser forms are `/account/email-login` and `/account/email-login/confirm`. Their writes require CSRF, and requesting a message also requires captcha. The code is submitted in the body. Keep the mail worker running and size delivery capacity for the configured code lifetime. The development console mailer prints the message locally. A suppressed address receives no message, so inspect the queue and suppression status when diagnosing delivery.

## Social sign-in

Google, Apple, Facebook, Instagram, GitHub, LinkedIn, Microsoft and Discord are available through explicit provider adapters. Every provider starts disabled, and each enabled provider can serve the site, the admin or both. Configure only the providers the product uses. The [configuration guide](configuration.md#social-provider-settings) contains the credential fields and startup validation rules.

An authorization begins at `/account/social/{provider}/start`, using `surface=site` or `surface=admin`. The server generates the provider redirect and stores the state, nonce, encrypted PKCE verifier and return path. A short-lived HttpOnly cookie binds that attempt to the browser that began it. The callback at `/account/social/{provider}/callback` consumes the attempt once, verifies the provider response and resolves the immutable subject inside the tenant. OpenID Connect providers require a valid signature, issuer, audience, expiry and nonce. The implementation uses S256 PKCE where the provider supports that flow.

The provider account identifier is the identity. An address or display name is never the social key. A new site user receives a verified email only when the provider supplies a trusted verified claim. Other profile fields keep their defaults. Without a verified address, the account receives a generated username such as `instagram-<random identifier>` and an empty email. Facebook and Instagram do not supply a verified email in these adapters. Microsoft email claims are mutable and are not accepted as proof of a mailbox. GitHub uses only its primary verified email. Apple private relay addresses are supported as verified addresses.

**Matching email addresses never silently link accounts.** If a new social identity presents an email already used in the tenant, sign-in is refused with instructions to sign in using the existing method and connect the provider from the profile. This also applies to the first social sign-in of an operator. Admin social sign-in requires a connection already attached to an existing permitted operator, and never creates an administrator.

The site receives its normal HttpOnly session cookie. The admin callback returns a short-lived ticket in the URL fragment, removes the fragment before exchanging it, and redeems the ticket through `POST /api/admin/social/redeem`. The ticket is valid for sixty seconds by default, is bound to its browser and tenant, can be claimed once, and rechecks the account's role, status and session epoch. Permanent application tokens, provider tokens and credentials are never placed in callback URLs or public metadata. Provider tokens are used for the identity exchange and are not stored as renewable integrations.

### Connecting and removing providers

The site profile links to `/account/connections`, and the admin profile shows its enabled providers. Sign in with an existing method first, then choose **Connect** and approve that provider. An account can connect one identity per provider. A provider identity can belong to only one account in a tenant, and changing the connected identity requires removing the old one first.

| Authenticated API request | Purpose |
| --- | --- |
| `GET /api/account/social-connections?surface=site` | List enabled providers and existing connections. Use `surface=admin` for panel availability. |
| `POST /api/account/social-connections/{provider}/start` | Send `{ "surface": "site" }` and navigate to `authorizationUrl`. The response also sets the temporary browser cookie. |
| `DELETE /api/account/social-connections/{provider}?surface=site` | Remove this account's connection. The final usable method is protected. |

These API requests use the normal bearer token. Connection callbacks recheck the session epoch, tenant and status before attaching an identity. Removing a connection requires another enabled social connection, a password or an email usable by enabled email-code sign-in on that surface. A disabled provider remains visible when connected so its owner can remove it safely. Removing an identity prevents future sign-ins with it and does not end sessions already opened. Password changes and account blocking retain their normal session revocation behavior.

A passwordless account's password page explains that it has no password. An account with an email can use password recovery to set one. Erasing an account removes its social mappings, in-flight social attempts, admin tickets and email challenges along with the existing personal data cleanup. Expired operational records are collected by the existing retention job.

## Social provider setup

Register a separate application with each provider you enable and keep its credentials in the private environment file. Register the **exact** HTTPS callback for every participating brand, for example `https://brand.example/account/social/google/callback`. The same callback handles site sign-in, admin sign-in and profile connections. The installation holds one credential set per provider, so every participating domain must be allowed by that provider application. Provider policy may require verification, product approval, a published privacy policy or review before accounts outside the development team can sign in.

| Provider key | Application setup and permissions |
| --- | --- |
| `google` | Create a Web application OAuth client in Google Cloud, configure the consent screen, and register the callback. The adapter requests `openid email`, reads the immutable `sub` and accepts only verified email. Google documents both current issuer spellings. See [OpenID Connect](https://developers.google.com/identity/openid-connect/openid-connect). |
| `apple` | Enable Sign in with Apple for the primary App ID, configure a Services ID for the website, register its domains and return URL, and create a Sign in with Apple key. Set the Services ID as `client_id`, plus `team_id`, `key_id` and the private P-256 `.p8` key. The server signs its client secret. Apple returns by `form_post`, so HTTPS and secure cookies are required, including in local end-to-end testing. Configure relay email delivery if the product sends to private relay addresses. See [Sign in with Apple REST API](https://developer.apple.com/documentation/signinwithapplerestapi). |
| `facebook` | Configure Facebook Login for a Meta app, add its valid OAuth redirect URI and enable the appropriate live access. The adapter requests `public_profile`, uses the app-scoped `id`, and supplies `appsecret_proof` when reading the profile. It does not treat a Facebook email as verified. The configured Graph API version defaults to `v26.0`. See [Facebook Login](https://developers.facebook.com/docs/facebook-login/) and the [Graph API changelog](https://developers.facebook.com/docs/graph-api/changelog/). |
| `instagram` | Configure Instagram API with Instagram Login, register the redirect URI and request `instagram_business_basic`. Use the Instagram app credentials. This API supports **professional Business and Creator accounts**, not personal consumer accounts. The adapter reads `user_id` and does not invent an email address. See [Meta's Instagram API collection](https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api) and [Business Login](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/business-login). |
| `github` | Register an OAuth App or a GitHub App configured for the web authorization flow. Register the callback, create a client secret and allow `user:email`. S256 PKCE protects the exchange. The adapter reads the numeric user `id` and the primary verified address from the emails endpoint. An OAuth App has one callback URL, while a GitHub App permits up to ten, so choose an application type that fits the brand domains. See [web authorization](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps), [email permissions](https://docs.github.com/en/rest/users/emails) and [GitHub App registration](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/registering-a-github-app). |
| `linkedin` | Create a LinkedIn application and enable the **Sign In with LinkedIn using OpenID Connect** product. Register the callback and request `openid profile email`. The adapter validates `sub` and accepts email only with `email_verified=true`. Email fields may be absent. See [LinkedIn's integration guide](https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/sign-in-with-linkedin-v2). |
| `microsoft` | Register a Web application in Microsoft Entra, register its redirect URI and create a client secret. The default `microsoft_tenant="consumers"` accepts personal Microsoft accounts. Set an explicit organization tenant UUID for an organization application. The adapter requests `openid email profile` and validates that tenant's issuer. Its mutable email claim is not a verified mailbox identity, so connect existing accounts explicitly. See [ID token claims](https://learn.microsoft.com/en-us/entra/identity-platform/id-token-claims-reference). |
| `discord` | Create an application in the Discord Developer Portal, add its OAuth2 redirect URI and obtain the client ID and secret. The adapter requests `openid identify email`, validates the ID token through Discord's published signing keys and accepts email only when verified. See [OAuth2 documentation](https://docs.discord.com/developers/topics/oauth2) and [OpenID discovery](https://discord.com/.well-known/openid-configuration). |

### Diagnosing sign-in failures

A missing button means the method is disabled for that surface, or the admin metadata needs a reload after configuration changed. Invalid enabled credentials or an Apple configuration without HTTPS fail configuration validation before serving traffic. A provider redirect mismatch requires correcting the registered callback, including scheme, domain and path. An app in provider development mode usually admits only its owners and configured testers.

A cancelled provider prompt opens no session. An expired state, a callback in another browser, a reused callback or a lost temporary cookie requires starting again. Apple callbacks need the secure `SameSite=None` cookie to survive the cross-site POST, so an HTTP development origin cannot exercise that flow. A matching-email refusal requires signing in to the existing account and connecting the provider there. A panel-access refusal requires an existing panel role and connection, never a new social sign-up.

Uvicorn and the supplied Nginx access log omit query strings because provider callbacks carry authorization codes. Keep the same redaction when replacing the reverse proxy or adding request logging. Do not log callback bodies, tokens, cookies or mail contexts. Local tests stub every provider and exercise real signature validation. Completing each provider's registration and testing with its approved application remains part of enabling it for a deployment.

## Wrong passwords are counted on the account

The account is what is being guessed at, so that is where the count lives. The rate limiter counts
addresses, and it counts them in the memory of one process — with four workers on ten copies, one
address gets forty times the budget.

| What happens | What the account answers |
| --- | --- |
| a wrong password | counts one more, and answers `error.invalid-credentials` |
| the count of `sign_in_attempts` closes | earns a wait that **doubles** with every further miss, up to `sign_in_cooldown_max` |
| the right password inside the wait | `error.too-many-attempts`, because only somebody who already knows it is told to wait |
| a wrong password inside the wait | `error.invalid-credentials`, exactly what it always said |
| the right password after the wait | signs in, and the count goes back to zero |

The count is raised by the database in an `UPDATE` rather than read and written back by this side.
Attempts arriving together would otherwise all read the same old value, and what is lost that way is
attempts an attacker gets for free.

Whoever is guessing never sees the wait. That is what stops the throttle from becoming a way to find out
which accounts exist, and a login naming nobody answers the same and counts nothing.

## Deleting an account from the panel

Nobody deletes the row they are signed in as. The trail of the deletion would point at somebody who is
no longer there, and what came back instead was a conflict complaining about a duplicate — the foreign
key refusing, not a duplicate at all.

Erasing your own account is a different door, on the site, and it anonymises rather than deletes.

## The session

Signing in mints a JWT. The API carries it in `Authorization: Bearer`, and the site keeps the same token
in an `httponly` cookie the page never reads.

**The token does not expire.** What ends access is the status of the account, not the clock — a blocked
or erased account is refused before any route. And `sub` is the `token` of the account, never the id,
because that identifier travels to gateways and the numeric one never crosses the network.

A new password ends every session the old one opened and keeps the person who changed it signed in. An
operator setting the password of an account from the panel ends every session of that account too.
The `session_epoch` is a counter every token carries, and changing the password advances it. The account
`token` is untouched on purpose: it is the identifier a gateway knows, and drawing a new one would leave
a paid subscription pointing at nobody.

A password change checks the hash and session epoch again in the database after verification and
hashing. If another password change, reset or erasure wins that interval, the older request is refused
with `error.invalid-credentials`. It cannot overwrite newer credentials or issue a replacement session.

## Recovering a password

The letter carries a link, and the page it opens asks first whether the link still opens an account. One
that was used, replaced by a newer request or left to expire sends the person back to ask for another,
instead of drawing a form that can never succeed. Setting the password from the letter proves the
address, so it also opens an account still waiting for its confirmation, and it clears the wait that
wrong guesses put on the account. Where the person was going travels through the whole
recovery — on the link to it, inside the letter, and back to the sign-in once the password is set.

## Erasing an account

`DELETE /api/account/me` anonymises rather than deletes: removing the row would take subscriptions and
the ledger with it, and those are records of money and not personal data.

| What goes | What stays |
| --- | --- |
| username, email, document, phone, password and `token`, all overwritten with drawn values | subscriptions, the ledger, purchases and what the account owns |
| names, nickname, avatar, notes and metadata, emptied | |
| the events the apps reported, and the addresses | |

The drawn email uses the reserved `.invalid` TLD. The status becomes `erased`, and the guard refuses that
account before any route, so it never answers again. The panel never writes that status by hand: erasing
is what the account does to itself, and a status that only looks erased would keep every personal field.
