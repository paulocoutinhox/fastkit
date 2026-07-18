# Dashboard

The admin root (`{admin}`) renders a **dashboard**, not a resource grid. The sidebar's first link is
Dashboard.

## Default

By default the dashboard shows an empty state. Each project supplies its own.

## Registering a dashboard

From a client script loaded via `_extra_js.html`:

```html
<script>
FastKitAdmin.registerDashboard(function (element, ctx) {
  // element is the #dashboard mount; render whatever you want
  element.innerHTML = '<div class="row row-cards">…stat cards…</div>';
});
</script>
```

The demo renders overview stat cards this way.

## Notes

- The dashboard is the home screen, so its breadcrumb is hidden (you are already home) and its title
  ("Dashboard") shows in the header.
- Because the dashboard is a normal screen, it goes through the same server render + permission dispatch;
  the client hook only fills the `#dashboard` element.

See [Client (app.js)](client-js.md) and [Extend the admin client](../guides/extend-admin-client.md).
