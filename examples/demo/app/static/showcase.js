(function ($) {
  "use strict";

  var STATUS_COLORS = { draft: "yellow", published: "green", archived: "secondary" };

  function patch(id, payload, ctx) {
    return FastKit.api("PATCH", "/resources/showcase/" + id, payload).then(function () {
      FastKit.toast("success", FastKit.t("form.updated"));
      ctx.refreshRow(id);
    }).catch(function (error) { FastKit.toast("error", error.message); });
  }

  window.addEventListener("fastkit:ready", function () {
    FastKitAdmin.registerDashboard(function (element, ctx) {
      var $el = $(element).html('<h2 class="mb-3">Overview</h2><div class="row row-cards" data-testid="demo-dashboard"></div>');
      var $row = $el.find(".row-cards");
      [
        { label: "Products", resource: "products", icon: "package" },
        { label: "Categories", resource: "categories", icon: "folder" },
        { label: "Task runs", resource: "task-runs", icon: "list-check" }
      ].forEach(function (card) {
        var $col = $('<div class="col-sm-6 col-lg-4"><div class="card"><div class="card-body"><div class="subheader">' + card.label + '</div><div class="h1 m-0" data-testid="dash-' + card.resource + '">…</div></div></div></div>');
        $row.append($col);
        ctx.api("GET", "/resources/" + card.resource).then(function (res) { $col.find("[data-testid]").text(res.meta.pagination.total_items); });
      });
    });

    FastKitAdmin.registerCellRenderer("showcase", "status", function (row) {
      if (!row.status) { return null; }
      var color = STATUS_COLORS[row.status] || "secondary";
      return '<span class="badge bg-' + color + '-lt" data-testid="status-badge-' + row.id + '">' + FastKit.esc(row.status) + "</span>";
    });

    FastKitAdmin.registerCellRenderer("showcase", "quantity", function (row, ctx) {
      var $link = $('<a href="#" class="text-primary fw-medium"></a>').text(row.quantity).attr("data-testid", "quantity-edit-" + row.id);
      $link.on("click", function (event) {
        event.preventDefault();
        var $input = $('<input type="number" class="form-control" data-testid="quantity-input">').val(row.quantity);
        FastKit.modal({
          title: "Update quantity",
          body: $input,
          buttons: [
            { label: FastKit.t("form.cancel") },
            { label: FastKit.t("form.save"), variant: "primary", testid: "quantity-save", onClick: function () { patch(row.id, { quantity: Number($input.val()) }, ctx); } }
          ]
        });
      });
      return $link;
    });

    FastKitAdmin.registerCellRenderer("showcase", "is_featured", function (row, ctx) {
      var $toggle = $('<a href="#" class="text-decoration-none"></a>').attr("data-testid", "feature-toggle-" + row.id).html(row.is_featured ? "★" : "☆").addClass(row.is_featured ? "text-warning" : "text-secondary");
      $toggle.on("click", function (event) { event.preventDefault(); patch(row.id, { is_featured: !row.is_featured }, ctx); });
      return $toggle;
    });

    FastKitAdmin.registerCellRenderer("showcase", "title", function (row) {
      return $('<div></div>').append($('<div class="fw-medium"></div>').text(row.title)).append($('<div class="text-secondary small"></div>').text("#" + row.id));
    });

    FastKitAdmin.registerRowAction("showcase", {
      name: "publish",
      label: "Publish",
      onClick: function (row, ctx) { patch(row.id, { status: "published" }, ctx); }
    });

    FastKitAdmin.registerRowAction("showcase", {
      name: "reload",
      label: "Reload",
      onClick: function (row, ctx) { ctx.refreshGrid(); }
    });
  });
})(jQuery);
