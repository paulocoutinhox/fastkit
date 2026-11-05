# The admin

The admin is a Vue single page app served at `/admin`. It has three screens — a grid, a detail and a form — and every resource is a declaration, not a screen somebody wrote.

## Navigation and pending changes

A screen action belongs to the record or parent that started it. Switching resources closes an old
delete confirmation. Opening a different detail clears the previous record before loading, including
its edit, delete and activate actions if the new read fails.

Late delete and activate responses cannot redirect or reload a different screen. Child panels clear
their editor, confirmation and records when their parent changes. Old reads, saves, deletions and
reorders cannot replace the new parent's data. Closing a child editor invalidates its pending draft
response, so it cannot overwrite an editor opened afterwards.

These rules also apply when leaving the screen entirely. An operation already accepted by the server
can finish there. Its response does not take control of the screen now being used.

## A resource

```js
export const products = {
    name: "products",
    section: "commerce",
    icon: "tag",
    labelField: "name",
    ordering: ["id", "name", "slug", "price", "position", "createdAt"],
    defaultOrdering: "position",
    columns: [...],
    filters: [...],
    groups: [...],
    viewExtra: [...],
};
```

Flags: `readOnly` for a table the engine writes, `managedByParent` for a resource a parent administers, `activatable` for the one that grows an activate button, and `canView` / `canCreate` / `canEdit` / `canDelete`. A flag states what the API answers for that resource: the activate button posts to `/<resource>/<id>/activate`, and a resource kept out of the menu is one a parent lists among its subitems. The suite checks both.

A field nobody touched holds nothing unless it declares a `default`, and the form sends what every field holds, so a column the API refuses empty declares one. A record that did not load draws neither the form nor the save button, because the screen is reused from one record to the next and would otherwise save the previous one over it.

A resource form accepts one pending write, including submissions from the keyboard and its alternate
save action. Navigating to another resource invalidates the pending answer for that screen. A late
success cannot redirect the new form, and a late refusal cannot replace its current validation errors.

The panel is handed both paths it needs — where it is served and where the API answers — by the build,
and never writes either one itself: the webhook address an operator pastes into a gateway console is
built from what the server declared.

A subitem panel draws one page of children. Where a parent holds more than it drew it says so and stops
offering to reorder them, because an order written for part of a set renumbers what was drawn and leaves
the rest where it was.

The HTML editor answers every language the panel offers, read from a map rather than a choice between
two: the editor names its catalogues differently from us, and English is the only one it already carries.
The calendar reads the same kind of map for the day a week starts on — Sunday in English and Portuguese,
Monday in Spanish — and its header and its grid read the one value, so a column always names the day
beneath it.

Every field is declared through a builder in `resources/fields.js` and drawn by the component the registry
names for its type. The set is closed, so the type is indexed directly: one nobody wrote a component for
draws an empty field rather than quietly becoming a text box, and a guard checks that every type any
resource declares has both a component and a builder.

A read-only screen still chooses what it shows. The mail queue draws who a message went to, which template it used, what became of it and why it failed — and never the context it was rendered from, because a password reset carries its token in there.

## Who sees what

A resource says who reaches it in one line on its **service**, and the panel declares nothing:

```python
class ContentService(TaggedService):
    roles = (UserRole.ADMINISTRATOR, UserRole.EDITOR)
```

The panel asks `GET /api/meta/permissions` what **this account** reaches — never the whole map, which on
an open route would tell the shape of the system to somebody who never signed in — and draws the menu
from the answer. A section nobody reaches anything in is not a heading over an empty list, the router
refuses the address of a resource the account does not reach, and the dashboard counts only what it can
read.

The menu is read in alphabetical order by default: sections and the items of each by their names in the
language of the panel. A product that wants a menu of its own sets `MENU_ORDER` in `resources/index.js`
to `declared`, and the menu then keeps the order `SECTIONS` and `RESOURCES` are written in.

A catalogue that other forms point at declares one more thing:

```python
class TenantService(CrudService):
    lookup_roles = PANEL_ROLES
```

Managing a resource and resolving it as an option of somebody else's form are different permissions.
Content points at a tenant that an editor does not manage, and without this the form draws a field that
never answers. The suite fails when a form offers an option its reader cannot resolve.

A language is never a lookup. The languages the instance offers arrive with the boot, and the `language`
field draws them without asking for any permission — the `languages` resource belongs to no brand, and an
operator confined to one would be refused it on every form and every filter. For the same reason the
tenant filter of every grid is not drawn to a confined operator, and the suite fails when anything the
panel draws for one asks for a resource that belongs to no brand.

Nothing is ever drawn and then taken away: navigation completes only once the answer is in, and a boot
screen holds the place while it is on its way — once, on the first navigation, not on every click.

## The account of whoever operates the panel

What an operator edits about themselves is not a resource, so `/profile` is one of the four screens
written by hand — beside the sign in, the dashboard and the 404. It writes through the addresses the
account already answers for itself: `PUT /api/account/me` for the name, the nickname, the username, the
email, the document, the mobile phone, the gender, the language of its messages and the timezone, `POST` and `DELETE /api/account/avatar` for the picture, and
`POST /api/account/password` for the password.

Because it is not a resource, every role that works in the panel reaches it. An editor edits themselves
there without reaching `users`, which is the administrative resource and answers for everybody else.

Changing the password there mints a new token for this device and keeps what the account reaches: a new
password ends every other session the old one opened, and the store settles the new token instead of
starting over as it would for a different account signing in.

The fields of that screen are written by hand rather than read off a resource definition, so a guard
reads its builders against the two payloads an account sends about itself, in both directions.

## Optional sign-in methods

The login screen reads enabled methods from the server metadata. Email-code login and Google, Apple, Facebook, Instagram, GitHub, LinkedIn, Microsoft and Discord buttons appear only after their private configuration enables them for the admin. All start disabled. Password login remains available. See [authentication configuration](configuration.md#optional-authentication) and [provider registration](accounts.md#social-provider-setup).

An email code opens only an existing active operator account. Neither a code nor a provider approval grants a panel role. For social access, first sign in using an existing method, open the profile and connect the provider there. An email match alone does not attach a social identity to an operator.

The provider callback reaches the backend on the same host, then returns a short-lived, browser-bound ticket in the login URL fragment. The screen clears that fragment before redeeming it, and the server checks the account's current role, status and session epoch before issuing the normal bearer token. A stale request cannot overwrite a newer session. Unknown or expired tickets and cancelled consent show an error without opening a session.

The profile lists enabled providers and existing connections. Removing the final usable sign-in method is refused. An account without a password sees an explanation instead of a form asking for a nonexistent current password. If it has an email, password recovery can establish its first password. Instagram requires a professional Business or Creator account, and Apple requires HTTPS and secure cookies.

## Where the panel is served and what it calls

The panel is served at `admin_path` and calls the API at `api_path`, and it writes down neither. The
build reads both out of `config/settings.py`: the first becomes the base of every asset URL, the second is
handed to the API client. A value the panel wrote down itself is one that breaks the day the server
moves, silently.

## Fields

One component per kind of data, never a loose `<input>`: `text`, `textarea`, `number`, `switch`, `select`, `lookup`, `datetime`, `date`, `json`, `html`, `image`, `file`, `password`, `timezone`, `language`.

A foreign key always uses `lookup`, which searches the API as somebody types. A lookup may hang off another one:

```js
lookup("planId", "field.plan", "plans", { dependsOn: "integrationId" })
```

The dependent field waits until the one above it is chosen, asks the API narrowed by it, and empties every level below it when it moves.

## Subitems

A resource that only makes sense inside another declares it:

```js
subitems: [{ resource: "gallery-photos", foreignKey: "galleryId", orderBy: "position" }]
```

The edit screen of the parent grows a panel that lists, creates, edits, deletes and reorders the children, seeding the foreign key so the child never has to be told who its parent is. It appears only on edit, because a child needs a parent that already exists.

## What the guards keep honest

The suite refuses a definition that would draw a screen the API cannot answer:

| Guard | What it catches |
| --- | --- |
| every field a form writes | a name the write schema does not accept |
| every column a grid draws | a name the read schema never answers |
| every filter drawn | a filter the service does not apply |
| every sortable header | an ordering the service does not offer |
| every enum value | a value with no label in one of the catalogs |
| every resource | one with no title and singular in every catalog |
| every write screen | a resource the API answers 405 to |
