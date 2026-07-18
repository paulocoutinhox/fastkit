# Extend the admin client

Load a script via the `_extra_js.html` fill-in partial and use `window.FastKitAdmin` — no framework
edit, no build step.

```html
<!-- myproject/templates/admin/_extra_js.html -->
<script src="/static/showcase.js"></script>
```

```javascript
// showcase.js — plain jQuery, runs after fastkit:ready
(function () {
  // a custom cell renderer (return an HTML string or a live jQuery/DOM element)
  FastKitAdmin.registerCellRenderer("products", "status", function (row) {
    return row.is_active
      ? '<span class="badge bg-green">Active</span>'
      : '<span class="badge">Off</span>';
  });

  // a custom header renderer
  FastKitAdmin.registerHeaderRenderer("products", "price", function () { return "Price (USD)"; });

  // a row action that patches one row and refreshes it
  FastKitAdmin.registerRowAction("products", {
    label: "Toggle active", icon: "toggle-left",
    run: function (row) {
      FastKit.api("PATCH", "/resources/products/" + row.id, { is_active: !row.is_active })
        .then(function () { FastKitAdmin.refreshRow(row.id); });
    }
  });

  // react to events
  window.addEventListener("fastkit:cell-click", function (e) { /* e.detail */ });
})();
```

## What you can do

- `registerCellRenderer(resource, column, fn)` — interactive cells (a click-to-edit modal, a toggle).
- `registerHeaderRenderer(resource, column, fn)`.
- `registerRowAction(resource, action)`.
- listen to `fastkit:cell-click` / `fastkit:action` / `fastkit:ready`.
- `refreshGrid()` / `refreshRow(id)` — refresh keeping filters and page.
- `registerDashboard(fn)` — render the home screen.
- `FastKit.captcha.register(name, adapter)` — a login captcha client adapter.

Build all UI through `FastKit` (toast/modal/confirm/api/upload/formErrors) so you never depend on
Tabler/Bootstrap directly. See [Client (app.js)](../admin/client-js.md) and
[Override admin templates](override-templates.md).
