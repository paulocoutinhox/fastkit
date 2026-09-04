# Accounts

Who somebody is, what they reach, and how a session ends.

## Four identities, one field

An account is created with at least one of four: a username, an email, a document or a mobile phone.
Signing in takes any of them in the same field, and the API resolves which one was typed.

A username is written with letters, digits, a dot, a dash or an underscore, and nothing else. It is
written into the record of what an operator did, and a line of that record is read as one line — a
username carrying a line break inside it would write a second one.

An identity is unique **inside a tenant** and not across the system, so two brands may each have a
`contact@` of their own. What guarantees it is a functional unique index over `COALESCE(tenant_id, 0)`:
in a plain unique index no null equals another, and two accounts with no tenant and the same email would
both be accepted.

| Path | Resolves in | How it knows |
| --- | --- | --- |
| `POST /api/signin`, `/api/signup`, `/api/account/password-reset` | the tenant that called | the `X-Tenant-Code` header, required |
| the site | the tenant of the host | `Tenant.domain` |
| `POST /api/admin/signin` | the global scope | it has no tenant, and needs none |

Signing in to a tenant where the identity does not exist answers `error.invalid-credentials` — the same
as a wrong password, so the answer never says where somebody has an account.

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

A new password ends every session the old one opened and keeps the person who changed it signed in.
The `session_epoch` is a counter every token carries, and changing the password advances it. The account
`token` is untouched on purpose: it is the identifier a gateway knows, and drawing a new one would leave
a paid subscription pointing at nobody.

## Erasing an account

`DELETE /api/account/me` anonymises rather than deletes: removing the row would take subscriptions and
the ledger with it, and those are records of money and not personal data.

| What goes | What stays |
| --- | --- |
| username, email, document, phone, password and `token`, all overwritten with drawn values | subscriptions, the ledger, purchases and what the account owns |
| names, nickname, avatar, notes and metadata, emptied | |
| the events the apps reported, and the addresses | |

The drawn email uses the reserved `.invalid` TLD. The status becomes `erased`, and the guard refuses that
account before any route, so it never answers again.
