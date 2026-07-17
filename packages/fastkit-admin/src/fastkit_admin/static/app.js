(function ($) {
  "use strict";

  var CONFIG = window.__FASTKIT__ || {};
  var API = CONFIG.apiBaseUrl || "/api";
  var ADMIN = CONFIG.adminPath || "/admin";

  function t(key) {
    return (CONFIG.messages && CONFIG.messages[key]) || key;
  }

  function api(method, path, body) {
    return FastKit.api(method, path, body);
  }

  function navProgress() {
    var bar = document.getElementById("fk-nav-progress");
    if (!bar) {
      bar = document.createElement("div");
      bar.id = "fk-nav-progress";
      bar.setAttribute("data-testid", "nav-progress");
      document.body.appendChild(bar);
    }
    bar.className = "";
    void bar.offsetWidth;
    bar.className = "fk-progress-active";
  }

  function resetNavProgress() {
    var bar = document.getElementById("fk-nav-progress");
    if (bar) { bar.parentNode.removeChild(bar); }
  }

  function go(url) {
    navProgress();
    window.location.assign(url);
  }

  function flash(kind, message) {
    try { window.sessionStorage.setItem("fk-flash", JSON.stringify({ kind: kind, message: message })); } catch (error) { return; }
  }

  function showFlash() {
    var raw;
    try { raw = window.sessionStorage.getItem("fk-flash"); window.sessionStorage.removeItem("fk-flash"); } catch (error) { return; }
    if (!raw) { return; }
    var entry = JSON.parse(raw);
    FastKit.toast(entry.kind, entry.message);
  }

  // ---------- extension bridge ----------

  var registry = { cells: {}, rowActions: {}, dashboard: null };

  window.FastKitAdmin = {
    registerCellRenderer: function (resource, column, fn) {
      (registry.cells[resource] = registry.cells[resource] || {})[column] = fn;
    },
    registerRowAction: function (resource, action) {
      (registry.rowActions[resource] = registry.rowActions[resource] || []).push(action);
    },
    registerDashboard: function (fn) {
      registry.dashboard = fn;
    },
    refreshGrid: function () {},
    refreshRow: function () {}
  };

  function gridContext() {
    return { api: api, refreshGrid: window.FastKitAdmin.refreshGrid, refreshRow: window.FastKitAdmin.refreshRow };
  }

  function applyExtensions($grid, resource) {
    var cells = registry.cells[resource] || {};
    var actions = registry.rowActions[resource] || [];
    var ctx = gridContext();

    $grid.find("tr[data-row]").each(function () {
      var $tr = $(this);
      var row = $tr.data("row");

      Object.keys(cells).forEach(function (column) {
        var output = cells[column](row, ctx);
        if (output == null) { return; }
        var $cell = $tr.find('td[data-col="' + column + '"]').empty();
        if (typeof output === "string") { $cell.html(output); } else { $cell.append(output); }
      });

      var $menu = $tr.find(".dropdown-menu");
      actions.forEach(function (action) {
        var $item = $('<button type="button" class="dropdown-item"></button>').text(action.label).attr("data-testid", "ext-action-" + action.name + "-" + row.id);
        $item.on("click", function () { action.onClick(row, ctx); });
        $menu.append($item);
      });
    });
  }

  function formatCells($grid) {
    var tz = CONFIG.timezone || "UTC";
    var locale = CONFIG.locale || "en";
    $grid.find("tr[data-row]").each(function () {
      var row = $(this).data("row");
      $(this).find("td[data-type]").each(function () {
        if ($(this).children().length) { return; }
        var type = $(this).data("type");
        var value = row[$(this).data("col")];
        if (value == null || value === "") { return; }
        if (type === "datetime" || type === "date" || type === "time") {
          var parsed = new Date(value);
          if (isNaN(parsed.getTime())) { return; }
          var options = type === "date" ? { dateStyle: "medium" } : type === "time" ? { timeStyle: "short" } : { dateStyle: "medium", timeStyle: "short" };
          options.timeZone = tz;
          $(this).text(new Intl.DateTimeFormat(locale, options).format(parsed));
        } else if (type === "number" || type === "decimal") {
          var number = Number(value);
          if (!isNaN(number)) { $(this).text(new Intl.NumberFormat(locale).format(number)); }
        }
      });
    });
  }

  function optionsUrl(resource, field, params) {
    var query = $.param(params || {});
    return "/resources/" + resource + "/options/" + field + (query ? "?" + query : "");
  }

  function setLoading($control, on) {
    var $wrap = $control.closest(".fk-field,.fk-filter");
    var key = $control.data("field") || $control.data("filter") || $wrap.data("field") || $wrap.data("filter") || "";
    $control.prop("disabled", on);
    $wrap.find(".fk-load-spin").remove();
    if (on) {
      $wrap.append($('<span class="fk-load-spin spinner-border spinner-border-sm text-secondary" role="status" aria-hidden="true"></span>').attr("data-testid", "loading-" + key));
    }
  }

  function loadingMenu($menu) {
    $menu.html('<span class="dropdown-item disabled" data-testid="lookup-loading"><span class="spinner-border spinner-border-sm me-2"></span>' + FastKit.esc(t("form.loading")) + "</span>").addClass("show");
  }

  function setBusy($container, on) {
    $container.find(".fk-busy").remove();
    if (on) {
      $container.addClass("position-relative").append('<div class="fk-busy" data-testid="content-loading"><span class="spinner-border text-secondary" role="status" aria-hidden="true"></span></div>');
    }
  }

  function applyMask(value, mask) {
    var digits = String(value).replace(/\D/g, "");
    var result = "";
    var index = 0;
    for (var i = 0; i < mask.length; i += 1) {
      if (index >= digits.length) { break; }
      if (mask[i] === "#") { result += digits[index]; index += 1; } else { result += mask[i]; }
    }
    return result;
  }

  // ---------- reading field values ----------

  function readField($wrap) {
    var type = $wrap.data("type");
    if (type === "boolean") { return $wrap.find('input[type=checkbox]').prop("checked"); }
    if (type === "multiselect") { return $wrap.find('input[type=checkbox]:checked').map(function () { return $(this).val(); }).get(); }
    if (type === "color") { return $wrap.find('input[type=text]').val(); }
    if (type === "richtext") {
      var editor = window.tinymce && window.tinymce.get($wrap.find("textarea").attr("id"));
      return editor ? editor.getContent() : $wrap.find("textarea").val();
    }
    if (type === "json") {
      var jsonEditor = $wrap.find(".fk-json").data("jsonEditor");
      try { return jsonEditor ? jsonEditor.get() : null; } catch (error) { return null; }
    }
    if (type === "lookup") { return $wrap.find(".fk-lookup").data("value"); }
    if (type === "image" || type === "file") { return $wrap.find(".fk-upload").data("value"); }
    return $wrap.find("input,select,textarea").val();
  }

  var VIRTUAL = ["permission_matrix", "translations"];

  function collect($form) {
    var payload = {};
    $form.find(".fk-field").each(function () {
      var $wrap = $(this);
      if ($wrap.closest(".fk-inline").length) { return; }
      if (VIRTUAL.indexOf($wrap.data("type")) >= 0) { return; }
      payload[$wrap.data("field")] = readField($wrap);
    });
    $form.find(".fk-inline").each(function () {
      var name = $(this).data("inline");
      var rows = [];
      $(this).find(".fk-inline-rows").children(".fk-inline-row").each(function () {
        var row = {};
        var id = $(this).children(".fk-inline-id").val();
        if (id) { row.id = id; }
        $(this).find(".fk-field").each(function () {
          if (VIRTUAL.indexOf($(this).data("type")) < 0) { row[$(this).data("field")] = readField($(this)); }
        });
        rows.push(row);
      });
      payload[name] = rows;
    });
    return payload;
  }

  // ---------- field enhancers ----------

  function initMasks(root) {
    $(root).find(".fk-masked").each(function () {
      var mask = $(this).data("mask");
      $(this).on("input", function () { $(this).val(applyMask($(this).val(), mask)); });
    });
  }

  function initColor(root) {
    $(root).find(".fk-color").each(function () {
      var $picker = $(this).find('input[type=color]');
      var $text = $(this).find('input[type=text]');
      $picker.on("input", function () { $text.val($picker.val()); });
      $text.on("input", function () { if (/^#[0-9a-fA-F]{6}$/.test($text.val())) { $picker.val($text.val()); } });
    });
  }

  function initUploads(root) {
    $(root).find(".fk-upload").each(function () {
      var $container = $(this);
      var url = $container.data("upload-url");
      var kind = $container.data("kind");
      var $hidden = $container.find('input[type=hidden]');
      $container.data("value", $hidden.val() || "");
      var $label = $('<label class="btn mb-0"><span></span><input type="file" class="d-none"></label>');
      if (kind === "image") { $label.find("input").attr("accept", "image/*"); }
      var $remove = $('<button type="button" class="btn btn-ghost-danger ms-2"></button>').text(t("upload.remove"));
      function refresh() {
        var value = $container.data("value");
        $hidden.val(value);
        $label.find("span").text(value ? t("upload.replace") : kind === "image" ? t("upload.image") : t("upload.file"));
        $remove.toggle(!!value);
      }
      $label.find("input").on("change", function (event) {
        var file = event.target.files[0];
        if (!file) { return; }
        $label.find("span").text(t("upload.uploading"));
        FastKit.upload(url, file).then(function (res) { $container.data("value", res.data.url); refresh(); }).catch(function (err) { FastKit.toast("error", err.message); refresh(); });
        event.target.value = "";
      });
      $remove.on("click", function () { $container.data("value", ""); refresh(); });
      $container.append($label).append($remove);
      refresh();
    });
  }

  function initRichtexts(root) {
    if (!window.tinymce) { return; }
    $(root).find(".fk-richtext").each(function () {
      var element = this;
      var upload = $(this).data("upload-url");
      window.tinymce.init({
        target: element,
        license_key: "gpl",
        menubar: false,
        height: 320,
        branding: false,
        promotion: false,
        convert_urls: false,
        plugins: "lists link image table code autolink",
        toolbar: "undo redo | bold italic underline | bullist numlist | link image table | code",
        images_upload_handler: function (blobInfo) { return FastKit.upload(upload, blobInfo.blob()).then(function (res) { return res.data.url; }); }
      });
    });
  }

  function initJsons(root) {
    if (!window.JSONEditor) { return; }
    $(root).find(".fk-json").each(function () {
      var element = this;
      var raw = $(this).attr("data-value");
      var initial = null;
      if (raw && raw !== "null") { try { initial = JSON.parse(raw); } catch (error) { initial = raw; } }
      var editor = new window.JSONEditor(element, { modes: ["tree", "text"], mainMenuBar: true, statusBar: false }, initial);
      $(element).data("jsonEditor", editor);
    });
  }

  function resourceOf($el) {
    return $el.closest("[data-resource]").data("resource");
  }

  function readParent($form, name) {
    var $wrap = $form.find('.fk-field[data-field="' + name + '"]').first();
    if (!$wrap.length) { return null; }
    var $relation = $wrap.find(".fk-relation");
    if ($relation.length) { return $relation.val() || $relation.data("value") || ""; }
    var $lookup = $wrap.find(".fk-lookup");
    if ($lookup.length) { return $lookup.data("value") || ""; }
    return readField($wrap);
  }

  function relationParams($form, $node) {
    var params = {};
    String($node.data("depends-on") || "").split(",").filter(Boolean).forEach(function (parent) {
      var value = readParent($form, parent);
      if (value != null && value !== "") { params[parent] = value; }
    });
    return params;
  }

  function initRelations(root) {
    var $form = $(root).closest("form");
    $(root).find(".fk-relation").each(function () {
      var $select = $(this);
      loadOptions($select, resourceOf($select), $select.data("field"), relationParams($form, $select), $select.data("value"));
    });
    bindDependents($form, root);
  }

  function loadOptions($select, resource, field, params, current, blocking) {
    $select.data("pending", !!blocking);
    setLoading($select, true);
    return api("GET", optionsUrl(resource, field, params)).then(function (res) {
      $select.find("option:not(:first)").remove();
      res.data.forEach(function (option) { $select.append($("<option></option>").attr("value", option.value).text(option.label)); });
      if (current != null && current !== "") { $select.val(String(current)); }
      $select.data("pending", false);
      setLoading($select, false);
    }).catch(function () { $select.data("pending", false); setLoading($select, false); });
  }

  function resetDependent($form, $child) {
    if ($child.hasClass("fk-relation")) {
      $child.val("").data("value", "");
      loadOptions($child, resourceOf($child), $child.data("field"), relationParams($form, $child), null, true);
    } else {
      $child.data("value", "").find('input[type=hidden]').val("");
      $child.find('input[type=text]').val("");
    }
    $child.closest(".fk-field").trigger("change");
  }

  function bindDependents($form, root) {
    $(root).find(".fk-relation,.fk-lookup").each(function () {
      var $child = $(this);
      String($child.data("depends-on") || "").split(",").filter(Boolean).forEach(function (parent) {
        $form.find('.fk-field[data-field="' + parent + '"]').on("change", function () {
          resetDependent($form, $child);
        });
      });
    });
  }

  function initLookups(root) {
    var $form = $(root).closest("form");
    $(root).find(".fk-lookup").each(function () {
      var $container = $(this);
      var resource = resourceOf($container);
      var field = $container.data("field");
      var minChars = Number($container.data("min-chars") || 0);
      var initialLimit = Number($container.data("initial-limit") || 10);
      var searchLimit = Number($container.data("search-limit") || 20);
      var $hidden = $container.find('input[type=hidden]');
      $container.data("value", $hidden.val() || "");
      var $input = $('<input class="form-control" type="text" autocomplete="off">').attr("placeholder", t("lookup.search")).attr("data-testid", "field-" + field);
      var $menu = $('<div class="dropdown-menu fk-lookup-menu w-100"></div>');
      $container.addClass("dropdown").append($input).append($menu);
      var timer = null;
      var seq = 0;

      function params() {
        var result = {};
        String($container.data("depends-on") || "").split(",").filter(Boolean).forEach(function (parent) {
          var value = readParent($form, parent);
          if (value != null && value !== "") { result[parent] = value; }
        });
        return result;
      }
      function search() {
        var query = $input.val();
        var payload = params();
        if (query) { payload.q = query; }
        payload.limit = query ? searchLimit : initialLimit;
        var current = ++seq;
        loadingMenu($menu);
        api("GET", optionsUrl(resource, field, payload)).then(function (res) {
          if (current !== seq) { return; }
          $menu.empty();
          if (!res.data.length) { $menu.append('<span class="dropdown-item disabled">' + FastKit.esc(t("lookup.empty")) + "</span>"); }
          res.data.forEach(function (option) {
            var $item = $('<a class="dropdown-item" href="#"></a>').text(option.label).attr("data-testid", "lookup-option-" + option.value);
            $item.on("mousedown", function (event) { event.preventDefault(); $container.data("value", option.value); $hidden.val(option.value); $input.val(option.label); $menu.removeClass("show"); $container.trigger("change"); });
            $menu.append($item);
          });
          $menu.addClass("show");
        }).catch(function () { if (current === seq) { $menu.empty().removeClass("show"); } });
      }
      $input.on("focus", search);
      $input.on("input", function () {
        clearTimeout(timer);
        timer = setTimeout(function () { if ($input.val().length >= minChars) { search(); } else { $menu.removeClass("show"); } }, 200);
      });
      $input.on("blur", function () { setTimeout(function () { $menu.removeClass("show"); }, 150); });
    });
  }

  function matrixLayout($host, groups, selected, readonly) {
    $host.empty();
    groups.forEach(function (group) {
      var permissions = readonly ? group.permissions.filter(function (permission) { return selected[permission.id]; }) : group.permissions;
      if (readonly && !permissions.length) { return; }
      var $section = $('<div class="mb-4"></div>');
      $section.append($('<div class="subheader mb-3 pb-2 border-bottom"></div>').text(group.group));
      var $grid = $('<div class="row g-2"></div>');
      permissions.forEach(function (permission) {
        var $col = $('<div class="col-12 col-sm-6 col-lg-4"></div>');
        if (readonly) {
          $col.addClass("d-flex align-items-center gap-2").append('<i class="ti ti-check text-green"></i>').append($("<span></span>").attr("data-testid", "detail-permission-" + permission.code).text(permission.name));
        } else {
          var $label = $('<label class="form-check mb-0"><input type="checkbox" class="form-check-input"><span class="form-check-label"></span></label>');
          $label.find("input").attr("value", permission.id).prop("checked", !!selected[permission.id]).attr("data-testid", "permission-" + permission.code);
          $label.find(".form-check-label").text(permission.name);
          $col.append($label);
        }
        $grid.append($col);
      });
      $host.append($section.append($grid));
    });
  }

  function initMatrices(root) {
    $(root).find(".fk-matrix").each(function () {
      var $host = $(this);
      var readonly = !!$host.data("readonly");
      var recordId = $host.data("record-id");
      api("GET", $host.data("groups-url")).then(function (groupsRes) {
        var selected = {};
        function render() { matrixLayout($host, groupsRes.data, selected, readonly); }
        if (recordId !== "" && recordId != null) {
          api("GET", String($host.data("value-url")).replace("{id}", recordId)).then(function (valueRes) { valueRes.data.permission_ids.forEach(function (id) { selected[id] = true; }); render(); }).catch(function () { render(); });
        } else { render(); }
      }).catch(function () { FastKit.toast("error", t("error.unexpected")); });
    });
  }

  function saveMatrices($form, recordId) {
    var chain = Promise.resolve();
    $form.find('.fk-field[data-type="permission_matrix"] .fk-matrix').each(function () {
      var url = String($(this).data("save-url")).replace("{id}", recordId);
      var ids = $(this).find('input[type=checkbox]:checked').map(function () { return Number($(this).val()); }).get();
      chain = chain.then(function () { return api("PUT", url, { permission_ids: ids }); });
    });
    return chain;
  }

  function initTranslations(root) {
    $(root).find(".fk-translations").each(function () {
      var $host = $(this);
      var readonly = !!$host.data("readonly");
      var recordId = $host.data("record-id");
      api("GET", $host.data("languages-url")).then(function (langRes) {
        function render(values) {
          $host.empty();
          langRes.data.forEach(function (language) {
            var $group = $('<div class="mb-3"></div>');
            $group.append($('<label class="form-label"></label>').text(language.name));
            if (readonly) {
              $group.append($('<div class="text-secondary"></div>').text(values[language.code] || "—"));
            } else {
              $group.append($('<textarea class="form-control" rows="3"></textarea>').attr("data-testid", "translation-" + language.code).attr("data-language", language.code).val(values[language.code] || ""));
            }
            $host.append($group);
          });
        }
        if (recordId !== "" && recordId != null) {
          api("GET", String($host.data("value-url")).replace("{id}", recordId)).then(function (valueRes) {
            var values = {};
            valueRes.data.translations.forEach(function (translation) { values[translation.language] = translation.body; });
            render(values);
          }).catch(function () { render({}); });
        } else { render({}); }
      }).catch(function () { FastKit.toast("error", t("error.unexpected")); });
    });
  }

  function saveTranslations($form, recordId) {
    var chain = Promise.resolve();
    $form.find('.fk-field[data-type="translations"] .fk-translations').each(function () {
      var url = String($(this).data("save-url")).replace("{id}", recordId);
      var payload = { translations: $(this).find("textarea[data-language]").map(function () { return { language: $(this).data("language"), body: $(this).val() }; }).get() };
      chain = chain.then(function () { return api("PUT", url, payload); });
    });
    return chain;
  }

  function enhance(root) {
    initMasks(root);
    initColor(root);
    initUploads(root);
    initRichtexts(root);
    initJsons(root);
    initRelations(root);
    initLookups(root);
    initMatrices(root);
    initTranslations(root);
  }

  // ---------- filter enhancement ----------

  function filterFieldValue($panel, field) {
    var $filter = $panel.find('.fk-filter[data-filter="' + field + '"]');
    var $lookup = $filter.find(".fk-filter-lookup");
    if ($lookup.length) { return $lookup.data("value") || ""; }
    return $filter.find(".fk-filter-input").val() || "";
  }

  function filterParents($panel, $node) {
    var params = {};
    String($node.data("depends-on") || "").split(",").filter(Boolean).forEach(function (parent) {
      var value = filterFieldValue($panel, parent);
      if (value) { params[parent] = value; }
    });
    return params;
  }

  function loadFilterSelect($select, urlFn, params, current) {
    setLoading($select, true);
    return api("GET", urlFn($select.data("filter"), params)).then(function (res) {
      $select.find("option:not(:first)").remove();
      res.data.forEach(function (option) { $select.append($("<option></option>").attr("value", option.value).text(option.label)); });
      if (current != null && current !== "") { $select.val(String(current)); }
      setLoading($select, false);
    }).catch(function () { setLoading($select, false); });
  }

  function initFilterLookup($panel, $container, urlFn) {
    var field = $container.data("filter");
    $container.data("value", $container.data("value") || "");
    var $input = $('<input class="form-control" type="text" autocomplete="off">').attr("placeholder", t("lookup.search"));
    var $menu = $('<div class="dropdown-menu fk-lookup-menu w-100"></div>');
    $container.addClass("dropdown").prepend($menu).prepend($input);
    var timer = null;
    var seq = 0;

    function search() {
      var query = $input.val();
      var payload = filterParents($panel, $container);
      if (query) { payload.q = query; }
      var current = ++seq;
      loadingMenu($menu);
      api("GET", urlFn(field, payload)).then(function (res) {
        if (current !== seq) { return; }
        $menu.empty();
        res.data.forEach(function (option) {
          var $item = $('<a class="dropdown-item" href="#"></a>').text(option.label).attr("data-testid", "lookup-option-" + option.value);
          $item.on("mousedown", function (event) { event.preventDefault(); $container.data("value", option.value); $input.val(option.label); $menu.removeClass("show"); $container.trigger("change"); });
          $menu.append($item);
        });
        $menu.addClass("show");
      }).catch(function () { if (current === seq) { $menu.removeClass("show"); } });
    }
    $input.on("focus", search);
    $input.on("input", function () { clearTimeout(timer); timer = setTimeout(search, 200); });
    $input.on("blur", function () { setTimeout(function () { $menu.removeClass("show"); }, 150); });
  }

  function enhanceFilters($panel, urlFn) {
    if (!$panel.length) { return; }
    $panel.find(".fk-filter-select").each(function () { loadFilterSelect($(this), urlFn, filterParents($panel, $(this)), $(this).data("value")); });
    $panel.find(".fk-filter-lookup").each(function () { initFilterLookup($panel, $(this), urlFn); });
    $panel.find(".fk-filter-select,.fk-filter-lookup").each(function () {
      var $child = $(this);
      String($child.data("depends-on") || "").split(",").filter(Boolean).forEach(function (parent) {
        $panel.find('.fk-filter[data-filter="' + parent + '"]').on("change", function () {
          if ($child.hasClass("fk-filter-select")) {
            $child.val("");
            loadFilterSelect($child, urlFn, filterParents($panel, $child));
          } else {
            $child.data("value", "").find('input[type=text]').val("");
          }
          $child.closest(".fk-filter").trigger("change");
        });
      });
    });
  }

  // ---------- grid ----------

  function initGrid() {
    var $grid = $("#grid");
    if (!$grid.length) { return; }
    var base = $grid.data("base-url");
    var resource = $grid.data("resource");
    var state = { search: "", sort: "", page: 1, filters: {} };

    function query() {
      var parts = [];
      if (state.search) { parts.push("search=" + encodeURIComponent(state.search)); }
      if (state.sort) { parts.push("sort=" + encodeURIComponent(state.sort)); }
      if (state.page > 1) { parts.push("page=" + state.page); }
      Object.keys(state.filters).forEach(function (key) { parts.push(key + "=" + encodeURIComponent(state.filters[key])); });
      return parts.join("&");
    }

    function reload() {
      var url = base + "?" + query() + (query() ? "&" : "") + "_fragment=table";
      setBusy($grid, true);
      $.get(url).done(function (html) { $grid.html(html); formatCells($grid); applyExtensions($grid, resource); }).fail(function () { setBusy($grid, false); FastKit.toast("error", t("error.unexpected")); });
    }

    window.FastKitAdmin.refreshGrid = reload;
    window.FastKitAdmin.refreshRow = reload;
    formatCells($grid);
    applyExtensions($grid, resource);

    $(".fk-search-form").on("submit", function (event) { event.preventDefault(); state.search = $(this).find('[name=search]').val(); state.page = 1; reload(); });
    $(".fk-filter-toggle").on("click", function () { $(".fk-filter-panel").toggleClass("d-none"); });

    $(".fk-filters").on("submit", function (event) {
      event.preventDefault();
      state.filters = {};
      $(this).find(".fk-filter-input").each(function () {
        var name = $(this).attr("name");
        if (!name) { return; }
        if ($(this).is('[type=checkbox]') && !$(this).prop("checked")) { return; }
        var value = $(this).val();
        if (value !== "" && value != null) { state.filters[name] = value; }
      });
      $(this).find(".fk-filter-lookup").each(function () {
        var value = $(this).data("value");
        if (value) { state.filters["filter[" + $(this).data("filter") + "]"] = value; }
      });
      state.page = 1;
      reload();
    });
    $(".fk-filter-clear").on("click", function () { state.filters = {}; $(".fk-filters")[0].reset(); state.page = 1; reload(); });

    enhanceFilters($(".fk-filter-panel"), function (field, params) { return optionsUrl(resource, field, params); });

    $grid.on("click", ".fk-sort", function (event) { event.preventDefault(); state.sort = new URL(this.href, window.location.origin).searchParams.get("sort"); reload(); });
    $grid.on("click", ".fk-page", function (event) { event.preventDefault(); state.page = Number(new URL(this.href, window.location.origin).searchParams.get("page")); reload(); });

    $grid.on("click", ".fk-delete", function () {
      var id = $(this).data("id");
      FastKit.confirm(t("confirm.delete")).then(function (ok) {
        if (!ok) { return; }
        api("DELETE", "/resources/" + $grid.data("resource") + "/" + id).then(function () { FastKit.toast("success", t("form.deleted")); reload(); }).catch(function (err) { FastKit.toast("error", err.message); });
      });
    });

    var $bulk = $(".fk-bulk");
    $grid.on("change", ".fk-row-select,[data-testid=grid-select-all]", function () {
      if ($(this).is("[data-testid=grid-select-all]")) { $grid.find(".fk-row-select").prop("checked", $(this).prop("checked")); }
      var count = $grid.find(".fk-row-select:checked").length;
      $bulk.toggleClass("d-none", count === 0).find(".fk-bulk-count").text(count);
    });
    $bulk.find(".fk-bulk-delete").on("click", function () {
      var ids = $grid.find(".fk-row-select:checked").map(function () { return $(this).val(); }).get();
      if (!ids.length) { return; }
      FastKit.confirm(t("confirm.delete")).then(function (ok) {
        if (!ok) { return; }
        api("POST", "/resources/" + $grid.data("resource") + "/actions/bulk-delete", { ids: ids }).then(function () { FastKit.toast("success", t("form.deleted")); reload(); }).catch(function (err) { FastKit.toast("error", err.message); });
      });
    });

    function runAction(action, needsConfirm, ids) {
      function execute() {
        return api("POST", "/resources/" + resource + "/actions/" + action, { ids: ids }).then(function () { FastKit.toast("success", t("form.updated")); reload(); }).catch(function (err) { FastKit.toast("error", err.message); });
      }
      if (needsConfirm) { FastKit.confirm(t("confirm.delete")).then(function (ok) { if (ok) { execute(); } }); } else { execute(); }
    }

    $(".fk-collection-action").on("click", function () { runAction($(this).data("action"), $(this).data("confirm"), []); });
    $bulk.find(".fk-bulk-action").on("click", function () { runAction($(this).data("action"), $(this).data("confirm"), $grid.find(".fk-row-select:checked").map(function () { return $(this).val(); }).get()); });
  }

  // ---------- inlines ----------

  function reindexInline($inline) {
    $inline.find(".fk-inline-rows").children(".fk-inline-row").each(function (index) {
      $(this).attr("data-index", index);
      $(this).find(".fk-field").each(function () {
        var name = $(this).data("field");
        var id = "inline-" + $inline.data("inline") + "-" + index + "-" + name;
        $(this).find("label.form-label").attr("for", id);
        $(this).find("[id]").attr("id", id);
      });
    });
  }

  function initInlines($form) {
    $form.find(".fk-inline").each(function () {
      var $inline = $(this);
      reindexInline($inline);
      $inline.find(".fk-inline-add").on("click", function () {
        var max = $inline.data("max");
        var count = $inline.find(".fk-inline-rows").children(".fk-inline-row").length;
        if (max != null && count >= Number(max)) { return; }
        var html = $inline.find(".fk-inline-prototype").html();
        var $row = $(html);
        $inline.find(".fk-inline-rows").append($row);
        reindexInline($inline);
        enhance($row[0]);
      });
      $inline.on("click", ".fk-inline-remove", function () {
        var min = Number($inline.data("min") || 0);
        if ($inline.find(".fk-inline-rows").children(".fk-inline-row").length <= min) { return; }
        $(this).closest(".fk-inline-row").remove();
        reindexInline($inline);
      });
    });
  }

  // ---------- form ----------

  function initForm() {
    var $form = $("form[data-resource][data-mode]");
    if (!$form.length) { return; }
    var resource = $form.data("resource");
    var recordId = $form.data("record-id");
    enhance($form[0]);
    initInlines($form);

    $form.find(".fk-cancel").on("click", function () { go(ADMIN + "/" + resource); });
    $form.on("submit", function (event) {
      event.preventDefault();
      if ($form.find(".fk-relation").filter(function () { return $(this).data("pending"); }).length) {
        FastKit.toast("warning", t("form.still-loading"));
        return;
      }
      var $save = $form.find('[data-testid=form-save]');
      $save.prop("disabled", true).text(t("form.saving"));
      var payload = collect($form);
      var request = recordId ? api("PATCH", "/resources/" + resource + "/" + recordId, payload) : api("POST", "/resources/" + resource, payload);
      request.then(function (res) {
        var identifier = recordId || res.data.id;
        return saveMatrices($form, identifier).then(function () { return saveTranslations($form, identifier); }).then(function () {
          flash("success", recordId ? t("form.updated") : t("form.created"));
          go(ADMIN + "/" + resource);
        });
      }).catch(function (err) {
        $save.prop("disabled", false).text(t("form.save"));
        FastKit.formErrors($form, err);
      });
    });
  }

  // ---------- detail ----------

  function initDetail() {
    if ($("[data-testid=screen-title]").length && $(".fk-matrix").length) { initMatrices(document); }
  }

  // ---------- report ----------

  function initReport() {
    var $report = $("#report");
    if (!$report.length) { return; }
    var name = $report.data("report");
    var apiPath = $report.data("api-path");
    var params = {};

    function flatten() {
      params = {};
      $(".fk-filters").find(".fk-filter-input").each(function () {
        var raw = $(this).attr("name") || "";
        var match = raw.match(/^filter\[([^\]]+)\](?:\[([^\]]+)\])?$/);
        if (!match) { return; }
        var value = $(this).val();
        if (value === "" || value == null) { return; }
        params[match[2] ? match[1] + "_" + match[2] : match[1]] = value;
      });
      $(".fk-filters").find(".fk-filter-lookup").each(function () {
        var value = $(this).data("value");
        if (value) { params[$(this).data("filter")] = value; }
      });
    }
    function query() { return $.param(params); }
    function reload() {
      var url = $report.data("base-url") + "?" + query() + (query() ? "&" : "") + "_fragment=table";
      setBusy($report, true);
      $.get(url).done(function (html) {
        $report.html(html);
        $report.find(".fk-report-export").each(function () { this.href = apiPath + "/reports/" + name + "/export." + $(this).data("fmt") + (query() ? "?" + query() : ""); });
      }).fail(function () { setBusy($report, false); FastKit.toast("error", t("error.unexpected")); });
    }
    $(".fk-filter-toggle").on("click", function () { $(".fk-filter-panel").toggleClass("d-none"); });
    $(".fk-filters").on("submit", function (event) { event.preventDefault(); flatten(); reload(); });
    $(".fk-filter-clear").on("click", function () { $(".fk-filters")[0].reset(); params = {}; reload(); });

    enhanceFilters($(".fk-filter-panel"), function (field, payload) { var query = $.param(payload || {}); return "/reports/" + name + "/options/" + field + (query ? "?" + query : ""); });
  }

  // ---------- profile ----------

  function initProfile() {
    var $profile = $('[data-testid=profile]');
    if (!$profile.length) { return; }

    $profile.find(".fk-avatar-input").on("change", function (event) {
      var file = event.target.files[0];
      if (!file) { return; }
      FastKit.upload(API + "/profile/avatar", file).then(function (res) {
        $profile.find(".fk-profile-avatar").css("background-image", "url(" + res.data.url + ")").text("");
        $('[data-testid=user-avatar]').css("background-image", "url(" + res.data.url + ")").text("");
        FastKit.toast("success", t("form.updated"));
      }).catch(function (err) { FastKit.toast("error", err.message); });
      event.target.value = "";
    });

    $profile.find(".fk-profile-details").on("submit", function (event) {
      event.preventDefault();
      var $card = $(this);
      $card.find("[data-error]").text("");
      api("PUT", "/profile", { display_name: $card.find('[data-testid=profile-display-name]').val(), first_name: $card.find('[data-testid=profile-first-name]').val(), last_name: $card.find('[data-testid=profile-last-name]').val() }).then(function () { FastKit.toast("success", t("form.updated")); $('[data-testid=user-name]').text($card.find('[data-testid=profile-display-name]').val()); }).catch(function (err) { FastKit.formErrors($card, err); });
    });

    $profile.find(".fk-profile-password").on("submit", function (event) {
      event.preventDefault();
      var $card = $(this);
      $card.find("[data-error]").text("");
      api("POST", "/profile/password", { current_password: $card.find('[data-testid=profile-current-password]').val(), new_password: $card.find('[data-testid=profile-new-password]').val() }).then(function () { FastKit.toast("success", t("profile.password-changed")); $card.find("input").val(""); }).catch(function (err) { FastKit.formErrors($card, err, { aliases: { password: "new_password" } }); });
    });

    $profile.find(".fk-identifier-add").on("click", function () {
      var $card = $(this).closest(".fk-profile-methods");
      api("POST", "/profile/identifiers", { type: $card.find('[data-testid=identifier-type]').val(), value: $card.find('[data-testid=identifier-value]').val() }).then(function () { flash("success", t("form.created")); window.location.reload(); }).catch(function (err) { FastKit.formErrors($card, err); });
    });
    $profile.on("click", ".fk-identifier-delete", function () {
      var id = $(this).data("id");
      FastKit.confirm(t("confirm.delete")).then(function (ok) {
        if (!ok) { return; }
        api("DELETE", "/profile/identifiers/" + id).then(function () { flash("success", t("form.deleted")); window.location.reload(); }).catch(function (err) { FastKit.toast("error", err.message); });
      });
    });
  }

  // ---------- dashboard ----------

  function initDashboard() {
    var element = document.getElementById("dashboard");
    if (element && registry.dashboard) { registry.dashboard(element, { api: api, config: CONFIG }); }
  }

  // ---------- login ----------

  function initLogin() {
    var $form = $("#login-form-el");
    if (!$form.length) { return; }
    var $error = $("#login-error");
    var $errorText = $error.find(".fk-login-error-text");

    function submit(token) {
      api("POST", "/auth/login", { identifier: $("#login-email").val(), password: $("#login-password").val(), recaptcha_token: token }).then(function () { go(ADMIN); }).catch(function (err) { $errorText.text(err.message); $error.removeClass("d-none"); });
    }

    $form.on("submit", function (event) {
      event.preventDefault();
      $error.addClass("d-none");
      $errorText.text("");
      var recaptcha = CONFIG.recaptcha;
      if (recaptcha && recaptcha.enabled && window.grecaptcha) {
        window.grecaptcha.ready(function () { window.grecaptcha.execute(recaptcha.siteKey, { action: recaptcha.action }).then(function (token) { submit(token); }); });
      } else {
        submit(null);
      }
    });
  }

  // ---------- chrome (theme + logout) ----------

  function initChrome() {
    $(document).on("show.bs.dropdown", function (event) {
      $(event.target).closest(".dropdown").find(".dropdown-menu").attr("data-bs-theme", document.documentElement.getAttribute("data-bs-theme"));
    });
    $(document).on("shown.bs.dropdown", function (event) {
      var $dropdown = $(event.target).closest(".fk-menu-fixed");
      if (!$dropdown.length) { return; }
      var $toggle = $dropdown.find("[data-bs-toggle=dropdown]");
      var $menu = $dropdown.find(".dropdown-menu");
      var rect = $toggle[0].getBoundingClientRect();
      var height = $menu.outerHeight();
      var openUp = window.innerHeight - rect.bottom < height && rect.top > height;
      $menu.css({ position: "fixed", inset: "auto", transform: "none", margin: 0, "z-index": 1055, top: (openUp ? rect.top - height : rect.bottom) + "px", left: Math.max(8, rect.right - $menu.outerWidth()) + "px" });
    });
    $('[data-testid=theme-dark]').on("click", function (event) { event.preventDefault(); setTheme("dark"); });
    $('[data-testid=theme-light]').on("click", function (event) { event.preventDefault(); setTheme("light"); });
    $("#logout").on("click", function (event) {
      event.preventDefault();
      api("POST", "/auth/logout").then(function () { go(ADMIN + "/login"); }).catch(function () { go(ADMIN + "/login"); });
    });
  }

  function setTheme(theme) {
    document.documentElement.setAttribute("data-bs-theme", theme);
    try { window.localStorage.setItem("fk-theme", theme); } catch (error) { return; }
  }

  // ---------- full-page navigation progress ----------

  function initNavProgress() {
    resetNavProgress();
    $(document).on("click", "a[href]", function (event) {
      if (event.isDefaultPrevented() || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) { return; }
      if ((this.target && this.target !== "_self") || this.hasAttribute("download") || $(this).hasClass("fk-report-export")) { return; }
      var href = this.getAttribute("href");
      if (!href || href.charAt(0) === "#" || /^(javascript|mailto|tel):/i.test(href)) { return; }
      if (this.origin !== window.location.origin) { return; }
      navProgress();
    });
    window.addEventListener("pageshow", function (event) { if (event.persisted) { resetNavProgress(); } });
  }

  $(function () {
    if (FastKit.localize) { FastKit.localize(document); }
    showFlash();
    window.dispatchEvent(new Event("fastkit:ready"));
    initNavProgress();
    initChrome();
    initLogin();
    initGrid();
    initForm();
    initDetail();
    initReport();
    initProfile();
    initDashboard();
  });
})(jQuery);
