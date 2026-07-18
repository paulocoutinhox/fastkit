# Inlines

An inline is a **parent form with infinite repeatable child sub-items** — use it for a genuine
composition where the children are **owned by the parent** and not managed as a separate resource.

```python
from fastkit_admin.inlines import InlineResource
from fastkit_admin.fields import TextField

class SurveyAdmin(AdminResource[Survey]):
    form_fields = [TextField("name", required=True)]
    inlines = [
        InlineResource(
            "questions",
            [TextField("name", label="Question", required=True)],
            model=SurveyQuestion,
            fk_field="survey_id",
            label="Questions",
            min_items=0, max_items=None, pk_field="id",
        )
    ]
```

Each inline renders as a card of repeatable rows below the parent fieldsets, pre-filled on edit.

> When is an inline the right choice? When the children are a **composition** (a survey owns its
> questions). Two independently-managed resources (e.g. Categories and Subcategories, each with its own
> menu and CRUD) should **not** be an inline — they are separate resources.

## Validate-then-persist, in one transaction

`InlineResource.validate` runs **before any DB write** (the parent is never flushed for an invalid
child) and collects **every** row's field errors at once, tagging each `FieldError` with
`path = [inline_name, row_index, field_name]`. Persistence is an **id-diff formset**: a row's id
travels under the `id` key (mapped to the child model's `pk_field`), rows with a persisted id are
updated, new rows inserted, and rows no longer present deleted — never delete-then-insert, so a child
referenced elsewhere keeps its id across an edit.

## Robust against bad payloads

A partial `PATCH` that omits an inline key leaves those children untouched. A malformed inline payload
(`"x"`, `123`, `{}`, `[1,2]`) leaves the existing rows intact — it never 500s or wipes children.

## Per-row errors on the client

The one client helper `FastKit.formErrors($scope, err, {aliases})` routes each error by its `path`: a
3-element inline path fills the `index`-th `.fk-inline-row`'s `[data-error=<field>]`, so an error on one
row **never lights up the same-named field on other rows**.

Inlines also work inside the [related-object modal](related-widget.md), and editing a related record's
inline children refreshes the parent's [dependent selects](dependent-selects.md).
