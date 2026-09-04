# The admin

The admin is a Vue single page app served at `/admin`. It has three screens — a grid, a detail and a form — and every resource is a declaration, not a screen somebody wrote.

## A resource

```js
export const products = {
    name: "products",              // the same name as the api path
    section: "commerce",               // which group of the menu it appears in
    icon: "tag",
    labelField: "name",
    ordering: ["id", "name", "price", "position", "createdAt"],
    defaultOrdering: "position",
    columns: [...],                // what the grid draws
    filters: [...],                // what the filter bar draws
    groups: [...],                 // the fieldsets of the form
    viewExtra: [...],              // what only the detail screen shows
};
```

Flags: `readOnly` for a table the engine writes, `managedByParent` for a resource a parent administers, `activatable` for the one that grows an activate button, and `canView` / `canCreate` / `canEdit` / `canDelete`.

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

A catalogue that other forms point at declares one more thing:

```python
class LanguageService(CrudService):
    lookup_roles = PANEL_ROLES
```

Managing a resource and resolving it as an option of somebody else's form are different permissions.
Content points at a language and a tenant that an editor does not manage, and without this the form
draws two fields that never answer. The suite fails when a form offers an option its reader cannot
resolve.

Nothing is ever drawn and then taken away: navigation completes only once the answer is in, and a boot
screen holds the place while it is on its way — once, on the first navigation, not on every click.

## Where the panel is served and what it calls

The panel is served at `admin_path` and calls the API at `api_path`, and it writes down neither. The
build reads both out of `config/base.py`: the first becomes the base of every asset URL, the second is
handed to the API client. A value the panel wrote down itself is one that breaks the day the server
moves, silently.

## Fields

One component per kind of data, never a loose `<input>`: `text`, `textarea`, `number`, `switch`, `select`, `lookup`, `datetime`, `date`, `json`, `html`, `image`, `file`, `password`, `timezone`.

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
