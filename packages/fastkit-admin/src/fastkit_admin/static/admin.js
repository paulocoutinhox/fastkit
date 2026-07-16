(function ($) {
  "use strict";

  var CONFIG = window.__FASTKIT__ || {};
  var ADMIN = CONFIG.adminPath || "/admin";
  var API = CONFIG.apiBaseUrl || "/api";
  var renderSeq = 0;
  function beginRender() { renderSeq += 1; return renderSeq; }
  function isCurrent(token) { return token === renderSeq; }

  if (!window.bootstrap && window.tabler && window.tabler.bootstrap) { window.bootstrap = window.tabler.bootstrap; }

  function placeFixedMenu(toggle, menu) {
    var $menu = $(menu);
    if (!$menu.hasClass("show")) {
      $menu.css({ position: "", top: "", left: "", margin: "", transform: "", inset: "", "z-index": "" }).removeAttr("data-bs-theme");
      return;
    }
    $menu.attr("data-bs-theme", document.documentElement.getAttribute("data-bs-theme") || document.body.getAttribute("data-bs-theme") || "light");
    var rect = toggle.getBoundingClientRect();
    $menu.css({ position: "fixed", margin: 0, inset: "auto", transform: "none", "z-index": 1056 });
    var width = $menu.outerWidth();
    var height = $menu.outerHeight();
    var top = rect.bottom + 2;
    if (top + height > window.innerHeight - 8) { top = Math.max(8, rect.top - height - 2); }
    var left = rect.right - width;
    if (left < 8) { left = rect.left; }
    if (left + width > window.innerWidth - 8) { left = window.innerWidth - 8 - width; }
    $menu.css({ top: Math.round(top) + "px", left: Math.round(left) + "px" });
  }

  function eachOpenFixedMenu(handler) {
    $(".fk-menu-fixed").each(function () {
      var toggle = $(this).children('[data-bs-toggle="dropdown"]')[0];
      var menu = $(this).children(".dropdown-menu")[0];
      if (toggle && menu) { handler(toggle, menu); }
    });
  }

  $(document).on("click", '.fk-menu-fixed [data-bs-toggle="dropdown"]', function () {
    var toggle = this;
    var menu = $(this).closest(".fk-menu-fixed").children(".dropdown-menu")[0];
    window.requestAnimationFrame(function () { placeFixedMenu(toggle, menu); });
  });
  window.addEventListener("scroll", function () { eachOpenFixedMenu(placeFixedMenu); }, true);
  window.addEventListener("resize", function () { eachOpenFixedMenu(placeFixedMenu); });
  var t = FastKit.t;
  var esc = FastKit.esc;
  var api = FastKit.api;

  var registry = { cellRenderers: {}, headerRenderers: {}, rowActions: {}, listeners: {} };

  var FastKitAdmin = {
    registerCellRenderer: function (resource, column, render) { registry.cellRenderers[resource + "." + column] = render; },
    cellRenderer: function (resource, column) { return registry.cellRenderers[resource + "." + column] || null; },
    registerHeaderRenderer: function (resource, column, render) { registry.headerRenderers[resource + "." + column] = render; },
    headerRenderer: function (resource, column) { return registry.headerRenderers[resource + "." + column] || null; },
    registerRowAction: function (resource, action) { (registry.rowActions[resource] = registry.rowActions[resource] || []).push(action); },
    rowActions: function (resource) { return registry.rowActions[resource] || []; },
    registerDashboard: function (render) { registry.dashboard = render; },
    on: function (event, fn) { (registry.listeners[event] = registry.listeners[event] || []).push(fn); },
    emit: function (event, payload) {
      (registry.listeners[event] || []).forEach(function (fn) { fn(payload); });
      window.dispatchEvent(new CustomEvent("fastkit:" + event, { detail: payload }));
    },
    refreshGrid: function () {},
    refreshRow: function () {}
  };
  window.FastKitAdmin = FastKitAdmin;

  function applyMask(value, mask) {
    var digits = String(value).replace(/\D/g, ""), result = "", index = 0;
    for (var i = 0; i < mask.length; i += 1) {
      if (index >= digits.length) { break; }
      if (mask[i] === "#") { result += digits[index]; index += 1; } else { result += mask[i]; }
    }
    return result;
  }

  function optionsUrl(resource, field, params) {
    var query = $.param(params || {});
    return "/resources/" + resource + "/options/" + field + (query ? "?" + query : "");
  }

  var CHECK_SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M5 12l5 5l10 -10" /></svg>';
  var CROSS_SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M18 6l-12 12" /><path d="M6 6l12 12" /></svg>';

  function boolIcon(on) {
    return $('<span></span>').addClass(on ? "text-green" : "text-red").attr("data-testid", on ? "bool-true" : "bool-false").html(on ? CHECK_SVG : CROSS_SVG);
  }

  function formatCell(value, fieldType) {
    if (fieldType === "boolean") {
      return boolIcon(value === true || value === "true");
    }
    if (value == null || value === "") {
      return document.createTextNode("—");
    }
    if (fieldType === "date") {
      return document.createTextNode(new Date(value).toLocaleDateString(FastKit.locale, { timeZone: CONFIG.timezone || "UTC" }));
    }
    if (fieldType === "datetime") {
      return document.createTextNode(new Date(value).toLocaleString(FastKit.locale, { timeZone: CONFIG.timezone || "UTC" }));
    }
    if (fieldType === "time") {
      return document.createTextNode(new Date("1970-01-01T" + value).toLocaleTimeString(FastKit.locale, { hour: "2-digit", minute: "2-digit" }));
    }
    if (fieldType === "number" || fieldType === "decimal") {
      return document.createTextNode(Number(value).toLocaleString(FastKit.locale));
    }
    return document.createTextNode(String(value));
  }

  var jsonEditors = [];

  function windowedPages(page, total) {
    var pages = [];
    for (var i = 1; i <= total; i += 1) {
      if (i === 1 || i === total || (i >= page - 1 && i <= page + 1)) { pages.push(i); }
      else if (pages[pages.length - 1] !== "gap") { pages.push("gap"); }
    }
    return pages;
  }

  function fieldInputId(field) { return "fk-field-" + field.name; }

  function renderField(resource, field, value, form) {
    var $wrap = $('<div class="mb-3"></div>');
    if (field.type !== "boolean" && !field.hide_label) {
      $wrap.append('<label class="form-label">' + esc(t(field.label)) + "</label>");
    }
    var testid = "field-" + field.name;
    var $control;

    if (field.type === "textarea") {
      $control = $('<textarea class="form-control" rows="4"></textarea>').val(value == null ? "" : value);
    } else if (field.type === "json") {
      $control = buildJson(field, value, form);
    } else if (field.type === "richtext") {
      $control = buildRichText(field, value, form);
    } else if (field.type === "select") {
      $control = $('<select class="form-select"></select>').append('<option value="">—</option>');
      (field.choices || []).forEach(function (choice) { $control.append($('<option></option>').attr("value", choice.value).text(choice.label)); });
      $control.val(value == null ? "" : value);
    } else if (field.type === "multiselect") {
      $control = $('<div class="d-flex flex-wrap gap-2"></div>');
      (field.choices || []).forEach(function (choice) {
        var $c = $('<label class="form-selectgroup-item"><input type="checkbox" class="form-check-input me-1"><span></span></label>');
        $c.find("input").prop("checked", (value || []).indexOf(choice.value) >= 0).attr("value", choice.value);
        $c.find("span").text(choice.label);
        $control.append($c);
      });
    } else if (field.type === "relation") {
      $control = $('<select class="form-select"></select>').append('<option value="">—</option>');
      form.relationSelects.push({ field: field, $el: $control, value: value });
    } else if (field.type === "lookup") {
      $control = buildLookup(resource, field, value, form);
    } else if (field.type === "permission_matrix") {
      $control = $('<div class="fk-matrix"></div>');
      form.matrices.push({ field: field, $el: $control });
    } else if (field.type === "translations") {
      $control = $('<div class="fk-translations"></div>');
      form.translations.push({ field: field, $el: $control, inputs: {} });
    } else if (field.type === "boolean") {
      $control = $('<label class="form-check form-switch"><input class="form-check-input" type="checkbox"><span class="form-check-label"></span></label>');
      $control.find("input").prop("checked", !!value);
      $control.find(".form-check-label").text(t(field.help_text || field.label));
    } else if (field.type === "color") {
      $control = $('<div class="d-flex align-items-center gap-2"><input type="color" class="form-control form-control-color"><input type="text" class="form-control font-monospace" style="max-width:9rem" placeholder="#4f46e5"></div>');
      $control.find('input[type=color]').val(value || "#000000");
      $control.find('input[type=text]').val(value || "").attr("data-testid", testid);
      $control.find('input[type=color]').on("input", function () { $control.find('input[type=text]').val($(this).val()); });
      $control.find('input[type=text]').on("input", function () { $control.find('input[type=color]').val($(this).val()); });
    } else if (field.type === "image" || field.type === "file") {
      $control = buildUpload(field, value, testid);
    } else if (field.type === "date" || field.type === "time" || field.type === "datetime") {
      var inputType = field.type === "datetime" ? "datetime-local" : field.type;
      $control = $('<input class="form-control">').attr("type", inputType).val(value == null ? "" : value);
    } else if (field.type === "number") {
      $control = $('<input class="form-control" type="number">').val(value == null ? "" : value);
    } else if (field.type === "masked") {
      $control = $('<input class="form-control" type="text">').val(value == null ? "" : value).attr("placeholder", field.mask);
      $control.on("input", function () { $(this).val(applyMask($(this).val(), field.mask)); });
    } else {
      var htmlType = field.type === "email" ? "email" : field.type === "url" ? "url" : field.type === "password" ? "password" : "text";
      $control = $('<input class="form-control">').attr("type", htmlType).val(value == null ? "" : value);
      if (htmlType === "password") { $control.attr("autocomplete", "new-password"); }
      if (field.placeholder) { $control.attr("placeholder", field.placeholder); }
    }

    $control.attr("id", fieldInputId(field));
    if ($control.is("input,select,textarea")) {
      if (!$control.attr("data-testid")) { $control.attr("data-testid", testid); }
    } else if (!$control.attr("data-testid") && !$control.find("[data-testid]").length) {
      $control.attr("data-testid", testid);
    }
    $wrap.append($control);

    if (field.help_text && field.type !== "boolean") {
      $wrap.append('<div class="form-hint">' + esc(field.help_text) + "</div>");
    }
    $wrap.append($('<div class="text-danger small mt-1"></div>').attr("data-error", field.name).attr("data-testid", "error-" + field.name));
    return $wrap;
  }

  function buildRichText(field, value, form) {
    var $textarea = $('<textarea class="form-control" data-testid="richtext-area"></textarea>').val(value || "");
    form.richtexts.push({ field: field });
    return $textarea;
  }

  function initRichtexts(form) {
    form.richtexts.forEach(function (entry) {
      window.tinymce.init({
        target: document.getElementById(fieldInputId(entry.field)),
        license_key: "gpl",
        menubar: false,
        height: 320,
        branding: false,
        promotion: false,
        convert_urls: false,
        plugins: "lists link image table code autolink",
        toolbar: "undo redo | bold italic underline | bullist numlist | link image table | code",
        images_upload_handler: function (blobInfo) {
          return FastKit.upload(entry.field.upload_url, blobInfo.blob()).then(function (res) { return res.data.url; });
        }
      });
    });
  }

  function buildJson(field, value, form) {
    var $wrap = $('<div class="fk-json"></div>').attr("data-testid", "json-" + field.name);
    form.jsons.push({ field: field, initial: value });
    return $wrap;
  }

  function initJsons(form) {
    form.jsons.forEach(function (entry) {
      var element = document.getElementById(fieldInputId(entry.field));
      var initial = null;
      if (entry.initial != null && entry.initial !== "") { try { initial = JSON.parse(entry.initial); } catch (e) { initial = entry.initial; } }
      var editor = new window.JSONEditor(element, { modes: ["tree", "text"], mainMenuBar: true, statusBar: false }, initial);
      $(element).data("jsonEditor", editor);
      jsonEditors.push(editor);
    });
  }

  function buildUpload(field, value, testid) {
    var $c = $('<div class="d-flex align-items-center gap-3"></div>');
    var $preview = $('<div class="fk-upload-preview border rounded"></div>');
    function renderPreview() {
      $preview.empty();
      if (field.type === "image" && $c.data("value")) {
        var $img = $('<img alt="preview" data-testid="upload-preview" style="cursor:zoom-in">').attr("src", $c.data("value"));
        $img.on("click", function () { FastKit.lightbox($c.data("value")); });
        $preview.append($img);
      } else {
        $preview.html('<span class="text-secondary">—</span>');
      }
    }
    var $label = $('<label class="btn"><span></span><input type="file" class="d-none"></label>');
    $label.find("input").attr("data-testid", testid);
    if (field.type === "image") { $label.find("input").attr("accept", "image/*"); }
    var $remove = $('<button type="button" class="btn btn-ghost-danger ms-2" data-testid="upload-remove"></button>').text(t("upload.remove"));
    var $link = $('<a target="_blank" class="d-block small text-truncate mt-1"></a>');
    function refresh() {
      var v = $c.data("value");
      $label.find("span").text(v ? t("upload.replace") : field.type === "image" ? t("upload.image") : t("upload.file"));
      $remove.toggle(!!v);
      $link.text(v || "").attr("href", v || "#").toggle(!!v);
      renderPreview();
    }
    $c.data("value", value || "");
    $label.find("input").on("change", function (event) {
      var file = event.target.files[0];
      if (!file) { return; }
      $label.find("span").text(t("upload.uploading"));
      FastKit.upload(field.upload_url, file).then(function (res) { $c.data("value", res.data.url); refresh(); }).catch(function (err) { FastKit.toast("error", err.message); refresh(); });
      event.target.value = "";
    });
    $remove.on("click", function () { $c.data("value", ""); refresh(); });
    $c.append($preview).append($('<div class="flex-fill"></div>').append($label).append($remove).append($link));
    refresh();
    return $c;
  }

  function buildLookup(resource, field, value, form) {
    var buildUrl = form.optionsUrl || function (name, params) { return optionsUrl(resource, name, params); };
    var $c = $('<div class="fk-lookup dropdown"></div>');
    var $input = $('<input class="form-control" type="text" autocomplete="off">').attr("placeholder", t("lookup.search")).attr("data-testid", "field-" + field.name);
    var $menu = $('<div class="dropdown-menu fk-lookup-menu w-100"></div>');
    $c.data("value", value == null ? "" : value);
    $c.append($input).append($menu);
    var timer = null;

    function params() {
      var p = {};
      (field.depends_on || []).forEach(function (parent) {
        var pv = form.readParent(parent);
        if (pv !== "" && pv != null) { p[parent] = pv; }
      });
      return p;
    }
    function open() { $menu.addClass("show"); }
    function close() { $menu.removeClass("show"); }
    var searchSeq = 0;
    function search() {
      var p = params();
      var query = $input.val();
      if (query) { p.q = query; }
      p.limit = query ? (field.search_limit || 20) : (field.initial_limit || 10);
      var seq = ++searchSeq;
      api("GET", buildUrl(field.name, p)).then(function (res) {
        if (seq !== searchSeq) { return; }
        $menu.empty();
        if (!res.data.length) { $menu.append('<span class="dropdown-item disabled">' + esc(t("lookup.empty")) + "</span>"); }
        res.data.forEach(function (opt) {
          var $item = $('<a class="dropdown-item" href="#"></a>').text(opt.label).attr("data-testid", "lookup-option-" + opt.value);
          $item.on("mousedown", function (e) { e.preventDefault(); $c.data("value", opt.value); $input.val(opt.label); close(); $input.trigger("change"); });
          $menu.append($item);
        });
        open();
      }).catch(function () {
        if (seq !== searchSeq) { return; }
        $menu.empty().append('<span class="dropdown-item disabled">' + esc(t("lookup.empty")) + "</span>");
        open();
      });
    }
    $input.on("focus", search);
    $input.on("input", function () {
      clearTimeout(timer);
      timer = setTimeout(function () {
        if ($input.val().length >= (field.min_chars || 0)) { search(); } else { close(); }
      }, 200);
    });
    $input.on("blur", function () { setTimeout(close, 150); });
    if ($c.data("value") !== "") {
      api("GET", buildUrl(field.name, { value: $c.data("value") })).then(function (res) { if (res.data.length) { $input.val(res.data[0].label); } }).catch(function () {});
    }
    return $c;
  }

  function buildFilterPanel(config) {
    var filters = config.filters || [];
    var $panel = $('<div class="card mb-3 d-none" data-testid="filters-panel"><div class="card-header"><h3 class="card-title"></h3></div><div class="card-body"></div></div>');
    $panel.find(".card-title").text(t("grid.filters"));
    var $body = $panel.find(".card-body");
    var reads = {};
    var refreshers = {};
    var cells = {};

    function ctxRead(name) { return reads[name] ? reads[name]() : ""; }

    function optionSelect(filter) {
      var $sel = $('<select class="form-select"><option value="">—</option></select>');
      function fill(params) {
        api("GET", config.optionsUrl(filter.options, params || {})).then(function (res) {
          var current = $sel.val();
          $sel.find("option:not(:first)").remove();
          res.data.forEach(function (opt) { $sel.append($('<option></option>').attr("value", opt.value).text(opt.label)); });
          $sel.val(current);
        }).catch(function () { FastKit.toast("error", t("error.unexpected")); });
      }
      fill({ limit: filter.initial_limit || 50 });
      refreshers[filter.field] = function () {
        var params = { limit: filter.initial_limit || 50 };
        (filter.depends_on || []).forEach(function (parent) { var value = ctxRead(parent); if (value) { params[parent] = value; } });
        fill(params);
      };
      return { el: $sel, read: function () { return $sel.val(); }, reset: function () { $sel.val(""); } };
    }

    function widget(filter) {
      if (filter.type === "boolean") {
        var $bool = $('<select class="form-select"><option value="">—</option><option value="true"></option><option value="false"></option></select>');
        $bool.find("option").eq(1).text(t("bool.yes"));
        $bool.find("option").eq(2).text(t("bool.no"));
        return { el: $bool, read: function () { return $bool.val(); }, reset: function () { $bool.val(""); } };
      }
      if (filter.type === "lookup") {
        var pseudo = { readParent: ctxRead, relationSelects: [], optionsUrl: config.optionsUrl };
        var lookupField = { name: filter.options, depends_on: filter.depends_on || [], min_chars: filter.min_chars || 0, initial_limit: filter.initial_limit || 10, search_limit: filter.search_limit || 20 };
        var $lookup = buildLookup("", lookupField, "", pseudo);
        return { el: $lookup, read: function () { return $lookup.data("value") || ""; }, reset: function () { $lookup.data("value", ""); $lookup.find("input").val(""); } };
      }
      if (filter.type === "select" && !(filter.choices || []).length) { return optionSelect(filter); }
      if (filter.type === "select" || filter.type === "choice" || filter.type === "enum" || filter.type === "exact") {
        var $choice = $('<select class="form-select"><option value="">—</option></select>');
        (filter.choices || []).forEach(function (choice) { $choice.append($('<option></option>').attr("value", choice.value).text(choice.label)); });
        return { el: $choice, read: function () { return $choice.val(); }, reset: function () { $choice.val(""); } };
      }
      if (filter.type === "date_range") {
        var $from = $('<input type="date" class="form-control" data-testid="filter-' + filter.field + '-from">');
        var $to = $('<input type="date" class="form-control" data-testid="filter-' + filter.field + '-to">');
        var $range = $('<div class="d-flex gap-2"></div>').append($from).append($to);
        return { el: $range, read: function () { return { from: $from.val(), to: $to.val() }; }, reset: function () { $from.val(""); $to.val(""); } };
      }
      if (filter.type === "date" || filter.type === "time" || filter.type === "datetime") {
        var inputType = filter.type === "datetime" ? "datetime-local" : filter.type;
        var $date = $('<input class="form-control">').attr("type", inputType);
        return { el: $date, read: function () { return $date.val(); }, reset: function () { $date.val(""); } };
      }
      if (filter.type === "number") {
        var $number = $('<input type="number" class="form-control">');
        return { el: $number, read: function () { return $number.val(); }, reset: function () { $number.val(""); } };
      }
      var $text = $('<input type="text" class="form-control">');
      return { el: $text, read: function () { return $text.val(); }, reset: function () { $text.val(""); } };
    }

    var byField = {};
    filters.forEach(function (filter) { byField[filter.field] = filter; });
    var groups = (config.fieldsets && config.fieldsets.length) ? config.fieldsets : [{ title: null, fields: filters.map(function (filter) { return filter.field; }) }];

    groups.forEach(function (group) {
      var $group = $('<div class="mb-2"></div>');
      if (group.title) { $group.append($('<div class="fw-bold mb-2"></div>').text(t(group.title))); }
      var $row = $('<div class="row g-2"></div>');
      group.fields.forEach(function (name) {
        var filter = byField[name];
        if (!filter) { return; }
        var built = widget(filter);
        reads[filter.field] = built.read;
        cells[filter.field] = built;
        var $col = $('<div class="col-md-4" data-testid="filter-' + filter.field + '"></div>');
        $col.append($('<label class="form-label small"></label>').text(t(filter.label)));
        $col.append(built.el);
        $row.append($col);
      });
      $group.append($row);
      $body.append($group);
    });

    function resetFilterDependents(changed) {
      filters.forEach(function (filter) {
        if ((filter.depends_on || []).indexOf(changed) < 0) { return; }
        if (cells[filter.field]) { cells[filter.field].reset(); }
        if (refreshers[filter.field]) { refreshers[filter.field](); }
        resetFilterDependents(filter.field);
      });
    }

    var filterParents = {};
    filters.forEach(function (filter) { (filter.depends_on || []).forEach(function (parent) { filterParents[parent] = true; }); });
    Object.keys(filterParents).forEach(function (parent) {
      if (cells[parent]) { cells[parent].el.on("change", function () { resetFilterDependents(parent); }); }
    });

    var $footer = $('<div class="d-flex gap-2 mt-3"></div>');
    var $apply = $('<button class="btn btn-primary" data-testid="filters-apply"></button>').text(t("grid.apply"));
    var $clear = $('<button class="btn" data-testid="filters-clear"></button>').text(t("grid.clear"));
    $apply.on("click", function () {
      var values = {};
      Object.keys(reads).forEach(function (field) {
        var value = reads[field]();
        if (value && typeof value === "object") { if (value.from || value.to) { values[field] = value; } }
        else if (value !== "" && value != null) { values[field] = value; }
      });
      config.onApply(values);
    });
    $clear.on("click", function () {
      Object.keys(cells).forEach(function (field) { cells[field].reset(); });
      config.onClear();
    });
    $footer.append($apply).append($clear);
    $body.append($footer);
    $body.on("keydown", "input", function (event) { if (event.key === "Enter") { event.preventDefault(); $apply.click(); } });
    return $panel;
  }

  function readField(field, $wrap) {
    if (field.type === "boolean") { return $wrap.find('input[type=checkbox]').prop("checked"); }
    if (field.type === "multiselect") { return $wrap.find('input[type=checkbox]:checked').map(function () { return $(this).attr("value"); }).get(); }
    if (field.type === "color") { return $wrap.find('input[type=text]').val(); }
    if (field.type === "richtext") {
      var editor = window.tinymce && window.tinymce.get(fieldInputId(field));
      return editor ? editor.getContent() : $wrap.find("#" + fieldInputId(field)).val();
    }
    if (field.type === "image" || field.type === "file") { return $wrap.find(".d-flex").first().data("value") || ""; }
    if (field.type === "lookup") { return $wrap.find(".fk-lookup").data("value"); }
    if (field.type === "json") {
      var jsonEditor = $wrap.find("#" + fieldInputId(field)).data("jsonEditor");
      try { return jsonEditor.get(); } catch (e) { return null; }
    }
    return $wrap.find("#" + fieldInputId(field)).val();
  }

  function renderGrid(resource) {
    var token = renderSeq;
    var state = { page: 1, sort: "id", search: "", selected: {}, grid: null, rows: [], filterValues: {} };
    var $content = $("#content").empty();

    api("GET", "/resources/" + resource + "/schema").then(function (res) {
      if (!isCurrent(token)) { return; }
      state.grid = res.data.grid;
      state.sort = (state.grid.default_sort && state.grid.default_sort[0]) || "id";
      state.hasSelection = state.grid.flags.can_delete || (state.grid.actions || []).some(function (a) { return a.scope === "bulk"; });
      $("#page-title").text(t(state.grid.label));
      buildShell();
      load();
    }).catch(showError);

    FastKitAdmin.refreshGrid = load;
    FastKitAdmin.refreshRow = function (id) {
      return api("GET", "/resources/" + resource + "/" + id + "/row").then(function (res) {
        if (!isCurrent(token)) { return; }
        var index = state.rows.findIndex(function (r) { return r.id === res.data.id; });
        if (index >= 0) { state.rows[index] = res.data; renderRows(); }
      });
    };

    function buildShell() {
      var $toolbar = $('<div class="card mb-3"><div class="card-body py-2 px-2"><div class="row g-2 align-items-center" data-testid="grid-toolbar"></div></div></div>');
      var $row = $toolbar.find('[data-testid="grid-toolbar"]');

      if ((state.grid.search_fields || []).length) {
        var $search = $('<input class="form-control" data-testid="grid-search">').attr("placeholder", t("grid.search"));
        $search.on("input", debounce(function () { state.search = $search.val(); state.page = 1; load(); }, 300));
        $row.append($('<div class="col-12 col-md"></div>').append($search));
      }

      var $actions = $('<div class="btn-list justify-content-end"></div>');
      $row.append($('<div class="col-12 col-md-auto ms-md-auto"></div>').append($actions));

      var $filterPanel = buildFilters();
      if ($filterPanel) {
        var $filterToggle = $('<button class="btn" data-testid="grid-filters"><i class="ti ti-filter me-1"></i></button>').append(document.createTextNode(t("grid.filters")));
        $filterToggle.on("click", function () { $filterPanel.toggleClass("d-none"); });
        $actions.append($filterToggle);
      }

      var bulkActions = (state.grid.actions || []).filter(function (a) { return a.scope === "bulk"; });
      if (state.hasSelection) {
        var $bulkWrap = $('<div class="dropdown fk-menu-fixed"></div>');
        var $bulkToggle = $('<button class="btn dropdown-toggle" data-bs-toggle="dropdown" data-testid="bulk-menu"></button>').text(t("grid.actions"));
        var $bulkMenu = $('<div class="dropdown-menu"></div>');
        bulkActions.forEach(function (action) {
          $bulkMenu.append($('<a class="dropdown-item" href="#"></a>').text(t(action.label)).attr("data-testid", "bulk-" + action.name).on("click", function (e) { e.preventDefault(); runAction(action, Object.keys(state.selected)); }));
        });
        if (state.grid.flags.can_delete) {
          $bulkMenu.append($('<a class="dropdown-item text-danger" href="#"><i class="ti ti-trash me-2"></i></a>').append(document.createTextNode(t("grid.delete-selected"))).attr("data-testid", "bulk-delete").on("click", function (e) { e.preventDefault(); deleteSelected(); }));
        }
        $bulkWrap.append($bulkToggle).append($bulkMenu);
        $actions.append($bulkWrap);
      }

      (state.grid.actions || []).filter(function (a) { return a.scope === "collection"; }).forEach(function (action) {
        var $b = $('<button class="btn"></button>').attr("data-testid", "collection-" + action.name).addClass(action.variant === "primary" ? "btn-primary" : "");
        if (action.icon) { $b.append($('<i class="ti me-1"></i>').addClass(action.icon)); }
        $b.append(document.createTextNode(t(action.label)));
        $b.on("click", function () { runAction(action, []); });
        $actions.append($b);
      });

      if (state.grid.flags.can_create) {
        var $new = $('<button class="btn btn-primary" data-testid="grid-new"><i class="ti ti-plus me-1"></i></button>').append(document.createTextNode(t("grid.new")));
        $new.on("click", function () { navigate(ADMIN + "/" + resource + "/new"); });
        $actions.append($new);
      }

      var $card = $(
        '<div class="card">' +
        '<div class="table-responsive"><table class="table table-selectable card-table table-vcenter text-nowrap datatable" data-testid="grid-table"><thead></thead><tbody></tbody></table></div>' +
        '<div class="card-footer d-flex align-items-center flex-wrap gap-2"><p class="m-0 text-secondary" data-testid="grid-total"></p>' +
        '<ul class="pagination m-0 ms-auto" data-testid="grid-pagination"></ul></div>' +
        '</div>'
      );

      $content.append($toolbar);
      if ($filterPanel) { $content.append($filterPanel); }
      $content.append($card);
    }

    function renderPagination() {
      var page = state.pagination.page;
      var pages = state.pagination.total_pages;
      var $ul = $content.find('[data-testid="grid-pagination"]').empty();

      function pageItem(label, target, opts) {
        opts = opts || {};
        var $li = $('<li class="page-item"></li>').toggleClass("disabled", !!opts.disabled).toggleClass("active", !!opts.active);
        var $a = $('<a class="page-link" href="#"></a>').html(label).attr("data-testid", opts.testid || ("grid-page-" + target));
        $a.on("click", function (e) { e.preventDefault(); if (opts.disabled || opts.active) { return; } state.page = target; load(); });
        return $li.append($a);
      }

      $ul.append(pageItem('<i class="ti ti-chevron-left"></i>', page - 1, { disabled: page <= 1, testid: "grid-prev" }));
      windowedPages(page, pages).forEach(function (target) {
        if (target === "gap") { $ul.append('<li class="page-item disabled"><span class="page-link">…</span></li>'); }
        else { $ul.append(pageItem(String(target), target, { active: target === page })); }
      });
      $ul.append(pageItem('<i class="ti ti-chevron-right"></i>', page + 1, { disabled: page >= pages, testid: "grid-next" }));
    }

    function buildFilters() {
      if (!(state.grid.filters || []).length) { return null; }
      return buildFilterPanel({
        filters: state.grid.filters,
        fieldsets: state.grid.filter_fieldsets,
        optionsUrl: function (field, params) { return optionsUrl(resource, field, params); },
        onApply: function (values) { state.filterValues = values; state.page = 1; load(); },
        onClear: function () { state.filterValues = {}; state.page = 1; load(); }
      });
    }

    function load() {
      state.selected = {};
      var params = { page: state.page, sort: state.sort };
      if (state.search) { params.search = state.search; }
      Object.keys(state.filterValues).forEach(function (field) {
        var value = state.filterValues[field];
        if (value && typeof value === "object") {
          if (value.from) { params["filter[" + field + "][from]"] = value.from; }
          if (value.to) { params["filter[" + field + "][to]"] = value.to; }
        } else {
          params["filter[" + field + "]"] = value;
        }
      });
      api("GET", "/resources/" + resource + "?" + $.param(params)).then(function (res) {
        if (!isCurrent(token)) { return; }
        state.rows = res.data;
        state.pagination = res.meta.pagination;
        if (state.page > state.pagination.total_pages && state.pagination.total_pages >= 1) {
          state.page = state.pagination.total_pages;
          load();
          return;
        }
        renderHead();
        renderRows();
        var pg = state.pagination;
        var from = pg.total_items ? (pg.page - 1) * pg.page_size + 1 : 0;
        var to = Math.min(pg.page * pg.page_size, pg.total_items);
        $content.find('[data-testid="grid-total"]').text(t("grid.showing").replace("{from}", from).replace("{to}", to).replace("{total}", pg.total_items));
        renderPagination();
      }).catch(showError);
    }

    function columnAlign(col) {
      return col.align || (col.field_type === "boolean" ? "center" : "left");
    }

    function renderHead() {
      var $tr = $("<tr></tr>");
      if (state.hasSelection) {
        var $th = $('<th class="w-1"></th>');
        if (state.grid.select_all) {
          $th.html('<input type="checkbox" class="form-check-input m-0" data-testid="grid-select-all">');
          $th.find("input").on("change", function () {
            var checked = $(this).prop("checked");
            state.selected = {};
            if (checked) { state.rows.forEach(function (r) { state.selected[r.id] = true; }); }
            renderRows();
          });
        }
        $tr.append($th);
      }
      (state.grid.columns || []).forEach(function (col) {
        var align = columnAlign(col);
        var $th = $("<th></th>").css("text-align", align).attr("data-testid", "header-" + col.name);
        var headerRenderer = FastKitAdmin.headerRenderer(resource, col.name);
        if (headerRenderer) { $th.html(headerRenderer(col)); return $tr.append($th); }
        if (col.sortable) {
          var direction = state.sort === col.name ? "asc" : state.sort === "-" + col.name ? "desc" : "";
          var justify = align === "center" ? "justify-content-center" : align === "right" ? "justify-content-end" : "";
          var $sort = $('<span class="d-inline-flex align-items-center gap-1"></span>').addClass(justify).css("cursor", "pointer").attr("data-testid", "sort-" + col.name);
          $sort.append(document.createTextNode(t(col.label)));
          $sort.append($('<i class="ti"></i>').addClass(direction === "asc" ? "ti-chevron-up" : direction === "desc" ? "ti-chevron-down" : "ti-selector text-secondary"));
          $sort.on("click", function () { state.sort = state.sort === col.name ? "-" + col.name : col.name; load(); });
          $th.append($sort);
        } else {
          $th.text(t(col.label));
        }
        $tr.append($th);
      });
      $tr.append('<th class="w-1 text-end">' + esc(t("grid.actions")) + "</th>");
      $content.find("thead").empty().append($tr);
    }

    function actionItem(testid, icon, label, cls, handler) {
      var $a = $('<a class="dropdown-item" href="#"></a>').attr("data-testid", testid);
      if (cls) { $a.addClass(cls); }
      $a.append($('<i class="ti me-2"></i>').addClass(icon)).append(document.createTextNode(label));
      $a.on("click", function (e) { e.preventDefault(); handler(); });
      return $a;
    }

    function renderRows() {
      var $tbody = $content.find("tbody").empty();
      if (!state.rows.length) {
        var span = (state.grid.columns || []).length + 1 + (state.hasSelection ? 1 : 0);
        $tbody.append('<tr><td colspan="' + span + '" class="text-center text-secondary py-4" data-testid="grid-empty">' + esc(t("grid.empty")) + "</td></tr>");
        return;
      }
      var canOpen = state.grid.flags.can_update || state.grid.flags.can_detail;
      state.rows.forEach(function (row) {
        var $tr = $('<tr data-testid="grid-row"></tr>');
        if (state.hasSelection) {
          var $cb = $('<td><input type="checkbox" class="form-check-input m-0 align-middle table-selectable-check"></td>');
          $cb.find("input").attr("data-testid", "select-" + row.id).prop("checked", !!state.selected[row.id]).on("change", function () {
            if ($(this).prop("checked")) { state.selected[row.id] = true; } else { delete state.selected[row.id]; }
          });
          $tr.append($cb);
        }
        (state.grid.columns || []).forEach(function (col) {
          var $td = $("<td></td>").css("text-align", columnAlign(col)).attr("data-testid", "cell-" + col.name + "-" + row.id);
          var renderer = FastKitAdmin.cellRenderer(resource, col.name);
          if (renderer) {
            var rendered = renderer(row, { resource: resource, column: col, refreshRow: FastKitAdmin.refreshRow, refreshGrid: load });
            if (rendered instanceof $ || rendered instanceof Element) { $td.empty().append(rendered); } else { $td.html(rendered == null ? "—" : rendered); }
          } else if (col.html) {
            var value = row[col.name];
            if (value == null || value === "") { $td.append(document.createTextNode("—")); } else { $td.html(value); }
          } else {
            $td.append(formatCell(row[col.name], col.field_type));
          }
          if (col.clickable && canOpen) {
            $td.addClass("text-primary fw-medium").css("cursor", "pointer").on("click", function () {
              FastKitAdmin.emit("cell-click", { resource: resource, row: row, column: col.name });
              navigate(ADMIN + "/" + resource + (state.grid.flags.can_update ? "/" + row.id + "/edit" : "/" + row.id));
            });
          }
          $tr.append($td);
        });
        var $menu = $('<div class="dropdown-menu dropdown-menu-end"></div>');
        if (state.grid.flags.can_detail) {
          $menu.append(actionItem("view-" + row.id, "ti-eye", t("grid.view"), "", function () { navigate(ADMIN + "/" + resource + "/" + row.id); }));
        }
        if (state.grid.flags.can_update) {
          $menu.append(actionItem("edit-" + row.id, "ti-edit", t("grid.edit"), "", function () { navigate(ADMIN + "/" + resource + "/" + row.id + "/edit"); }));
        }
        (state.grid.actions || []).filter(function (a) { return a.scope === "row"; }).forEach(function (action) {
          $menu.append(actionItem("action-" + action.name + "-" + row.id, "ti-bolt", t(action.label), "", function () { runAction(action, [row.id]); }));
        });
        FastKitAdmin.rowActions(resource).forEach(function (action) {
          $menu.append(actionItem("ext-action-" + action.name + "-" + row.id, action.icon || "ti-bolt", t(action.label), "", function () {
            FastKitAdmin.emit("action", { resource: resource, action: action.name, row: row });
            if (action.onClick) { action.onClick(row, { refreshRow: FastKitAdmin.refreshRow, refreshGrid: load }); }
          }));
        });
        if (state.grid.flags.can_delete) {
          $menu.append(actionItem("delete-" + row.id, "ti-trash", t("grid.delete"), "text-danger", function () {
            FastKit.confirm(t("confirm.delete")).then(function (ok) {
              if (ok) { api("DELETE", "/resources/" + resource + "/" + row.id).then(function () { FastKit.toast("success", t("form.deleted")); load(); }).catch(function (e) { FastKit.toast("error", e.message); }); }
            });
          }));
        }
        var $actions = $('<td class="text-end"></td>');
        if ($menu.children().length) {
          var $dropdown = $('<div class="dropdown fk-menu-fixed"></div>');
          $dropdown.append($('<button type="button" class="btn btn-action" data-bs-toggle="dropdown" aria-label="row actions"><i class="ti ti-dots-vertical"></i></button>').attr("data-testid", "row-menu-" + row.id));
          $dropdown.append($menu);
          $actions.append($dropdown);
        }
        $tr.append($actions);
        $tbody.append($tr);
      });
    }

    function deleteSelected() {
      var ids = Object.keys(state.selected);
      if (!ids.length) { return; }
      FastKit.confirm(t("confirm.delete-many")).then(function (ok) {
        if (!ok) { return; }
        Promise.all(ids.map(function (id) { return api("DELETE", "/resources/" + resource + "/" + id); })).then(function () { FastKit.toast("success", t("form.deleted")); load(); }).catch(function (e) { FastKit.toast("error", e.message); load(); });
      });
    }

    function runAction(action, ids) {
      function perform() {
        var request = action.scope === "row"
          ? api("POST", "/resources/" + resource + "/" + ids[0] + "/actions/" + action.name)
          : api("POST", "/resources/" + resource + "/actions/" + action.name, { ids: ids });
        request.then(function (r) { FastKit.toast("success", r.message.text); load(); }).catch(function (e) { FastKit.toast("error", e.message); });
      }
      if (action.confirm) { FastKit.confirm(action.confirm_message || t("confirm.delete")).then(function (ok) { if (ok) { perform(); } }); } else { perform(); }
    }
  }

  function renderForm(resource, recordId) {
    var token = renderSeq;
    var $content = $("#content").empty();
    var mode = recordId ? "edit" : "create";
    var form = { relationSelects: [], matrices: [], translations: [], richtexts: [], jsons: [], fieldWraps: {}, fields: [] };

    form.readParent = function (name) {
      var wrap = form.fieldWraps[name];
      if (!wrap) { return ""; }
      return readField(form.fields.filter(function (x) { return x.name === name; })[0], wrap);
    };

    Promise.all([
      api("GET", "/resources/" + resource + "/schema?mode=" + mode),
      recordId ? api("GET", "/resources/" + resource + "/" + recordId) : Promise.resolve(null)
    ]).then(function (results) {
      if (!isCurrent(token)) { return; }
      var flags = results[0].data.grid.flags;
      if ((recordId && !flags.can_update) || (!recordId && !flags.can_create)) {
        showError({ message: t("error.forbidden") });
        return;
      }
      var fieldsets = results[0].data.form.fieldsets;
      var data = results[1] ? results[1].data : {};
      $("#page-title").text((recordId ? t("form.edit") : t("grid.new")) + " " + t(results[0].data.grid.label));

      var $form = $('<form data-testid="form" autocomplete="off"></form>');
      form.scope = $form;
      fieldsets.forEach(function (fieldset, index) {
        var $card = $('<div class="card mb-3" data-testid="fieldset-' + index + '"></div>');
        if (fieldset.title) {
          var $head = $('<div class="card-header flex-column align-items-start py-2"></div>');
          $head.append($('<h3 class="card-title mb-0"></h3>').text(t(fieldset.title)));
          if (fieldset.description) { $head.append($('<div class="text-secondary small"></div>').text(t(fieldset.description))); }
          $card.append($head);
        }
        var $body = $('<div class="card-body"><div class="row"></div></div>');
        var $grid = $body.find(".row");
        fieldset.fields.forEach(function (field) {
          form.fields.push(field);
          var $wrap = renderField(resource, field, data[field.name], form);
          form.fieldWraps[field.name] = $wrap;
          $grid.append($('<div class="col-12"></div>').append($wrap));
        });
        $card.append($body);
        $form.append($card);
      });

      var $footer = $('<div class="d-flex gap-2"></div>');
      var $save = $('<button type="submit" class="btn btn-primary" data-testid="form-save">' + esc(t("form.save")) + "</button>");
      var $cancel = $('<button type="button" class="btn" data-testid="form-cancel">' + esc(t("form.cancel")) + "</button>");
      $cancel.on("click", function () { navigate(ADMIN + "/" + resource); });
      $form.append($footer.append($save).append($cancel));
      $content.append($form);

      form.relationSelects.forEach(function (entry) { if (!(entry.field.depends_on || []).length) { loadRelationOptions(resource, form, entry); } });
      populateMatrices(form, recordId, token);
      populateTranslations(form, recordId, token);
      initRichtexts(form);
      initJsons(form);
      wireCascades(resource, form);

      $form.on("submit", function (e) { e.preventDefault(); submitForm(resource, recordId, form, $save); });
    }).catch(showError);
  }

  function loadRelationOptions(resource, form, entry) {
    var params = {}, ready = true;
    (entry.field.depends_on || []).forEach(function (parent) {
      var pv = form.readParent(parent);
      if (pv === "" || pv == null) { ready = false; } else { params[parent] = pv; }
    });
    if (!ready) {
      entry.$el.empty().append('<option value="">—</option>').prop("disabled", false);
      loadDependents(resource, form, entry.field.name);
      return;
    }
    entry.loading = true;
    entry.$el.prop("disabled", true).empty().append('<option value="">' + esc(t("form.loading")) + "</option>");
    entry.seq = (entry.seq || 0) + 1;
    var seq = entry.seq;
    api("GET", optionsUrl(resource, entry.field.name, params)).then(function (res) {
      if (seq !== entry.seq) { return; }
      entry.$el.empty().append('<option value="">—</option>');
      res.data.forEach(function (opt) { entry.$el.append($('<option></option>').attr("value", opt.value).text(opt.label)); });
      if (entry.value != null) { entry.$el.val(entry.value); }
      entry.$el.prop("disabled", false);
      entry.loading = false;
      loadDependents(resource, form, entry.field.name);
    }).catch(function (err) {
      if (seq !== entry.seq) { return; }
      entry.$el.prop("disabled", false).empty().append('<option value="">—</option>');
      entry.loading = false;
      FastKit.toast("error", err.message);
    });
  }

  function loadDependents(resource, form, parentName) {
    form.relationSelects.forEach(function (entry) {
      if ((entry.field.depends_on || []).indexOf(parentName) >= 0) { loadRelationOptions(resource, form, entry); }
    });
  }

  function populateMatrices(form, recordId, token) {
    form.matrices.forEach(function (entry) {
      api("GET", entry.field.groups_url).then(function (groupsRes) {
        if (!isCurrent(token)) { return; }
        var selected = {};
        function render() {
          entry.$el.empty();
          groupsRes.data.forEach(function (group) {
            var $section = $('<div class="mb-4"></div>');
            $section.append($('<div class="subheader mb-3 pb-2 border-bottom"></div>').text(group.group));
            var $grid = $('<div class="row g-2"></div>');
            group.permissions.forEach(function (permission) {
              var $col = $('<div class="col-12 col-sm-6 col-lg-4"></div>');
              var $label = $('<label class="form-check mb-0"><input type="checkbox" class="form-check-input"><span class="form-check-label"></span></label>');
              $label.find("input").attr("value", permission.id).prop("checked", !!selected[permission.id]).attr("data-testid", "permission-" + permission.code);
              $label.find(".form-check-label").text(permission.name);
              $col.append($label);
              $grid.append($col);
            });
            $section.append($grid);
            entry.$el.append($section);
          });
        }
        if (recordId) {
          api("GET", entry.field.value_url.replace("{id}", recordId)).then(function (valueRes) { if (!isCurrent(token)) { return; } valueRes.data.permission_ids.forEach(function (id) { selected[id] = true; }); render(); }).catch(function () { FastKit.toast("error", t("error.unexpected")); });
        } else { render(); }
      }).catch(function () { if (isCurrent(token)) { FastKit.toast("error", t("error.unexpected")); } });
    });
  }

  function populateTranslations(form, recordId, token) {
    form.translations.forEach(function (entry) {
      api("GET", entry.field.languages_url).then(function (langRes) {
        if (!isCurrent(token)) { return; }
        function render(values) {
          entry.$el.empty();
          entry.inputs = {};
          langRes.data.forEach(function (language) {
            var $group = $('<div class="mb-3"></div>');
            $group.append($('<label class="form-label"></label>').text(language.name));
            var $textarea = $('<textarea class="form-control" rows="3"></textarea>').attr("data-testid", "translation-" + language.code).val(values[language.code] || "");
            entry.inputs[language.code] = $textarea;
            entry.$el.append($group.append($textarea));
          });
        }
        if (recordId) {
          api("GET", entry.field.value_url.replace("{id}", recordId)).then(function (valueRes) {
            if (!isCurrent(token)) { return; }
            var values = {};
            valueRes.data.translations.forEach(function (translation) { values[translation.language] = translation.body; });
            render(values);
          }).catch(function () { FastKit.toast("error", t("error.unexpected")); });
        } else { render({}); }
      }).catch(function () { if (isCurrent(token)) { FastKit.toast("error", t("error.unexpected")); } });
    });
  }

  function saveTranslations(form, recordId) {
    var chain = Promise.resolve();
    form.translations.forEach(function (entry) {
      var payload = { translations: Object.keys(entry.inputs).map(function (code) { return { language: code, body: entry.inputs[code].val() }; }) };
      chain = chain.then(function () { return api("PUT", entry.field.save_url.replace("{id}", recordId), payload); });
    });
    return chain;
  }

  function wireCascades(resource, form) {
    form.fields.forEach(function (field) {
      var wrap = form.fieldWraps[field.name];
      wrap.find("#" + fieldInputId(field)).on("change", function () { resetDependents(resource, form, field.name); });
      if (field.type === "lookup") { wrap.find(".fk-lookup input").on("change", function () { resetDependents(resource, form, field.name); }); }
    });
  }

  function resetDependents(resource, form, changedName) {
    form.fields.forEach(function (field) {
      if ((field.depends_on || []).indexOf(changedName) < 0) { return; }
      var wrap = form.fieldWraps[field.name];
      if (field.type === "relation") {
        var entry = form.relationSelects.filter(function (e) { return e.field.name === field.name; })[0];
        entry.value = null;
        loadRelationOptions(resource, form, entry);
      } else if (field.type === "lookup") {
        wrap.find(".fk-lookup").data("value", "").find("input").val("");
        resetDependents(resource, form, field.name);
      }
    });
  }

  function submitForm(resource, recordId, form, $save) {
    if (form.relationSelects.some(function (entry) { return entry.loading; })) {
      FastKit.toast("warning", t("form.still-loading"));
      return;
    }
    $save.prop("disabled", true).text(t("form.saving"));
    var payload = {};
    form.fields.forEach(function (field) { if (!field.virtual) { payload[field.name] = readField(field, form.fieldWraps[field.name]); } });
    var request = recordId ? api("PUT", "/resources/" + resource + "/" + recordId, payload) : api("POST", "/resources/" + resource, payload);
    request.then(function (res) {
      var identifier = recordId || res.data.id;
      return saveMatrices(form, identifier).then(function () { return saveTranslations(form, identifier); }).then(function () {
        FastKit.toast("success", recordId ? t("form.updated") : t("form.created"));
        navigate(ADMIN + "/" + resource);
      });
    }).catch(function (err) {
      $save.prop("disabled", false).text(t("form.save"));
      FastKit.formErrors(form.scope, err);
    });
  }

  function saveMatrices(form, recordId) {
    var chain = Promise.resolve();
    form.fields.forEach(function (field) {
      if (field.type !== "permission_matrix") { return; }
      var ids = form.fieldWraps[field.name].find('input[type=checkbox]:checked').map(function () { return Number($(this).attr("value")); }).get();
      chain = chain.then(function () { return api("PUT", field.save_url.replace("{id}", recordId), { permission_ids: ids }); });
    });
    return chain;
  }

  function renderDetail(resource, recordId) {
    var token = renderSeq;
    var $content = $("#content").empty();
    Promise.all([api("GET", "/resources/" + resource + "/schema?mode=edit"), api("GET", "/resources/" + resource + "/" + recordId)]).then(function (results) {
      if (!isCurrent(token)) { return; }
      var fieldsets = results[0].data.form.fieldsets;
      var data = results[1].data;
      var flags = results[0].data.grid.flags;
      $("#page-title").text(data._display || t("view.title"));

      var $head = $('<div class="d-flex gap-2 mb-3"></div>');
      if (flags.can_update) {
        var $edit = $('<button class="btn btn-primary" data-testid="detail-edit">' + esc(t("form.edit")) + "</button>");
        $edit.on("click", function () { navigate(ADMIN + "/" + resource + "/" + recordId + "/edit"); });
        $head.append($edit);
      }
      var $close = $('<button class="btn" data-testid="detail-close">' + esc(t("form.close")) + "</button>");
      $close.on("click", function () { navigate(ADMIN + "/" + resource); });
      $content.append($head.append($close));

      fieldsets.forEach(function (fieldset) {
        var $card = $('<div class="card mb-3"></div>');
        if (fieldset.title) { $card.append($('<div class="card-header"><h3 class="card-title"></h3></div>').find(".card-title").text(t(fieldset.title)).end()); }
        var $list = $('<div class="card-body"><div class="row"></div></div>');
        var $grid = $list.find(".row");
        fieldset.fields.filter(function (f) { return f.type !== "permission_matrix" && f.type !== "translations"; }).forEach(function (field) {
          var $row = $('<div class="mb-2" data-testid="detail-' + field.name + '"></div>');
          $row.append($('<div class="text-secondary small"></div>').text(t(field.label)));
          var value = data[field.name];
          var $val = $('<div></div>');
          var custom = data._html && data._html[field.name];
          if (custom != null) { $val.html(custom === "" ? "—" : custom); }
          else if (field.type === "image" && value) { $val.append($('<img class="rounded border" style="max-height:96px;cursor:zoom-in">').attr("src", value).on("click", function () { FastKit.lightbox(value); })); }
          else if (field.type === "file" && value) { $val.append($('<a target="_blank"></a>').attr("href", value).text(value)); }
          else if (field.type === "richtext" && value) { $val.html(value); }
          else if (field.type === "json" && value) { $val.append($('<pre class="mb-0 p-2 bg-secondary-lt rounded"></pre>').text(value)); }
          else if (field.type === "boolean") { $val.append(boolIcon(value === true || value === "true")); }
          else if (field.type === "color" && value) { $val.html('<span style="display:inline-block;width:1rem;height:1rem;border-radius:50%;background:' + esc(value) + '"></span> <span class="font-monospace">' + esc(value) + "</span>"); }
          else { $val.text(value == null || value === "" ? "—" : value); }
          $grid.append($('<div class="col-12"></div>').append($row.append($val)));
        });
        fieldset.fields.filter(function (f) { return f.type === "permission_matrix"; }).forEach(function (field) {
          var $holder = $('<div class="col-12" data-testid="detail-' + field.name + '"></div>');
          $grid.append($holder);
          renderReadonlyMatrix($holder, field, recordId, token);
        });
        $content.append($card.append($list));
      });
    }).catch(showError);
  }

  function renderReadonlyMatrix($holder, field, recordId, token) {
    Promise.all([api("GET", field.groups_url), api("GET", field.value_url.replace("{id}", recordId))]).then(function (results) {
      if (!isCurrent(token)) { return; }
      var selected = {};
      results[1].data.permission_ids.forEach(function (id) { selected[id] = true; });
      var any = false;
      results[0].data.forEach(function (group) {
        var granted = group.permissions.filter(function (permission) { return selected[permission.id]; });
        if (!granted.length) { return; }
        any = true;
        var $section = $('<div class="mb-4"></div>');
        $section.append($('<div class="subheader mb-3 pb-2 border-bottom"></div>').text(group.group));
        var $grid = $('<div class="row g-2"></div>');
        granted.forEach(function (permission) {
          var $col = $('<div class="col-12 col-sm-6 col-lg-4 d-flex align-items-center gap-2"></div>');
          $col.append($('<span class="text-green"></span>').html(CHECK_SVG));
          $col.append($('<span></span>').attr("data-testid", "detail-permission-" + permission.code).text(permission.name));
          $grid.append($col);
        });
        $holder.append($section.append($grid));
      });
      if (!any) { $holder.append($('<div class="text-secondary"></div>').text("—")); }
    }).catch(function () { if (isCurrent(token)) { $holder.append($('<div class="text-secondary"></div>').text("—")); } });
  }

  function profileCard(title) {
    var $card = $('<div class="card mb-3"></div>');
    $card.append($('<div class="card-header"><h3 class="card-title"></h3></div>').find(".card-title").text(title).end());
    var $body = $('<div class="card-body"></div>');
    $card.append($body);
    return { card: $card, body: $body };
  }

  function fieldRow(label, testid, value, type, errorKey) {
    var $row = $('<div class="mb-3"></div>');
    $row.append($('<label class="form-label"></label>').text(label));
    var $input = $('<input class="form-control">').attr("type", type || "text").attr("data-testid", testid).val(value == null ? "" : value);
    if (type === "password") { $input.attr("autocomplete", "new-password"); }
    $row.append($input);
    if (errorKey) { $row.append($('<div class="text-danger small mt-1"></div>').attr("data-error", errorKey)); }
    return $row;
  }

  function updateHeaderIdentity(profile) {
    $('[data-testid="user-name"]').text(profile.display_name || "");
    var $avatar = $('[data-testid="user-avatar"]');
    if (profile.avatar_url) { $avatar.css("background-image", "url(" + profile.avatar_url + ")").text(""); }
    else { $avatar.css("background-image", "").text((profile.display_name || profile.email || "?").slice(0, 2).toUpperCase()); }
  }

  function flattenReportParams(values) {
    var out = {};
    Object.keys(values).forEach(function (field) {
      var value = values[field];
      if (value && typeof value === "object") {
        if (value.from) { out[field + "_from"] = value.from; }
        if (value.to) { out[field + "_to"] = value.to; }
      } else {
        out[field] = value;
      }
    });
    return out;
  }

  function renderReport(name) {
    var token = renderSeq;
    var $content = $("#content").empty();
    var params = {};
    var $host = null;

    function refresh() {
      var query = $.param(params);
      api("GET", "/reports/" + name + "/run" + (query ? "?" + query : "")).then(function (res) {
        if (!isCurrent(token)) { return; }
        var report = res.data;
        $("#page-title").text(t(report.title));

        if (!$host) {
          if (report.filters && report.filters.length) {
            var $panel = buildFilterPanel({
              filters: report.filters,
              optionsUrl: function (field, p) { var q = $.param(p || {}); return "/reports/" + name + "/options/" + field + (q ? "?" + q : ""); },
              onApply: function (values) { params = flattenReportParams(values); refresh(); },
              onClear: function () { params = {}; refresh(); }
            });
            $content.append($panel.removeClass("d-none"));
          }
          $host = $('<div></div>');
          $content.append($host);
        }

        var $card = $('<div class="card"><div class="card-header d-flex flex-wrap align-items-center gap-2"><h3 class="card-title"></h3></div><div class="table-responsive" data-testid="report-table"></div></div>');
        $card.find(".card-title").text(t(report.title));
        var $exports = $('<div class="ms-auto btn-list"></div>');
        report.formats.forEach(function (fmt) {
          $exports.append($('<a class="btn" target="_blank"></a>').attr("data-testid", "report-export-" + fmt).attr("href", API + "/reports/" + name + "/export." + fmt + (query ? "?" + query : "")).attr("download", "").append($('<i class="ti ti-download me-1"></i>')).append(document.createTextNode(fmt.toUpperCase())));
        });
        $card.find(".card-header").append($exports);

        var $table = $('<table class="table table-vcenter card-table"><thead><tr></tr></thead><tbody></tbody></table>');
        report.columns.forEach(function (column) { $table.find("thead tr").append($("<th></th>").css("text-align", column.align).text(t(column.label))); });
        report.rows.forEach(function (row) {
          var $tr = $('<tr data-testid="report-row"></tr>');
          report.columns.forEach(function (column) { $tr.append($("<td></td>").css("text-align", column.align).text(row[column.key] == null ? "—" : row[column.key])); });
          $table.find("tbody").append($tr);
        });
        $card.find('[data-testid="report-table"]').append($table);
        $host.empty().append($card);
      }).catch(showError);
    }

    refresh();
  }

  function renderProfile() {
    var token = renderSeq;
    var $content = $("#content").empty();
    $("#page-title").text(t("profile.title"));
    api("GET", "/profile").then(function (res) {
      if (!isCurrent(token)) { return; }
      var profile = res.data;
      var $wrap = $('<div data-testid="profile"></div>');

      var avatar = profileCard(t("profile.avatar"));
      var $avatarRow = $('<div class="d-flex align-items-center gap-3"></div>');
      var initials = (profile.display_name || profile.email || "?").slice(0, 2).toUpperCase();
      var $avatar = $('<span class="avatar avatar-xl"></span>').attr("data-testid", "profile-avatar");
      if (profile.avatar_url) { $avatar.css("background-image", "url(" + profile.avatar_url + ")"); } else { $avatar.text(initials); }
      var $avatarUpload = $('<label class="btn"><span data-i18n="profile.change-photo">Change photo</span><input type="file" accept="image/*" class="d-none" data-testid="profile-avatar-input"></label>');
      $avatarUpload.find("input").on("change", function (event) {
        var file = event.target.files[0];
        if (!file) { return; }
        FastKit.upload(API + "/profile/avatar", file).then(function (r) {
          $avatar.css("background-image", "url(" + r.data.url + ")").text("");
          updateHeaderIdentity({ display_name: profile.display_name, avatar_url: r.data.url });
          FastKit.toast("success", t("form.updated"));
        }).catch(function (e) { FastKit.toast("error", e.message); });
        event.target.value = "";
      });
      avatar.body.append($avatarRow.append($avatar).append($avatarUpload));
      $wrap.append(avatar.card);

      var details = profileCard(t("profile.details"));
      details.body.append($('<div class="mb-3"><label class="form-label">Email</label><input class="form-control" disabled></div>').find("input").val(profile.email || "").end());
      details.body.append(fieldRow(t("profile.display-name"), "profile-display-name", profile.display_name, "text", "display_name"));
      details.body.append(fieldRow(t("profile.first-name"), "profile-first-name", profile.first_name, "text", "first_name"));
      details.body.append(fieldRow(t("profile.last-name"), "profile-last-name", profile.last_name, "text", "last_name"));
      var $saveDetails = $('<button class="btn btn-primary" data-testid="profile-save"></button>').text(t("form.save"));
      $saveDetails.on("click", function () {
        details.body.find("[data-error]").text("");
        api("PUT", "/profile", {
          display_name: details.body.find('[data-testid="profile-display-name"]').val(),
          first_name: details.body.find('[data-testid="profile-first-name"]').val(),
          last_name: details.body.find('[data-testid="profile-last-name"]').val()
        }).then(function (res) { FastKit.toast("success", t("form.updated")); updateHeaderIdentity(res.data); }).catch(function (e) { FastKit.formErrors(details.body, e); });
      });
      details.body.append($saveDetails);
      $wrap.append(details.card);

      var password = profileCard(t("profile.password"));
      password.body.append(fieldRow(t("profile.current-password"), "profile-current-password", "", "password", "current_password"));
      password.body.append(fieldRow(t("profile.new-password"), "profile-new-password", "", "password", "new_password"));
      var $savePassword = $('<button class="btn btn-primary" data-testid="profile-password-save"></button>').text(t("profile.change-password"));
      $savePassword.on("click", function () {
        password.body.find("[data-error]").text("");
        api("POST", "/profile/password", {
          current_password: password.body.find('[data-testid="profile-current-password"]').val(),
          new_password: password.body.find('[data-testid="profile-new-password"]').val()
        }).then(function () { FastKit.toast("success", t("profile.password-changed")); password.body.find("input").val(""); }).catch(function (e) { FastKit.formErrors(password.body, e, { aliases: { password: "new_password" } }); });
      });
      password.body.append($savePassword);
      $wrap.append(password.card);

      var methods = profileCard(t("profile.login-methods"));
      var $list = $('<ul class="list-group list-group-flush mb-3" data-testid="identifiers"></ul>');
      (profile.identifiers || []).forEach(function (identifier) {
        var $li = $('<li class="list-group-item d-flex align-items-center px-0"></li>');
        $li.append($('<span></span>').text(identifier.type + ": " + identifier.value));
        var $del = $('<button class="btn btn-ghost-danger btn-sm ms-auto" data-testid="identifier-delete-' + identifier.type + '"></button>').text(t("upload.remove"));
        $del.on("click", function () {
          FastKit.confirm(t("confirm.delete")).then(function (ok) {
            if (!ok) { return; }
            api("DELETE", "/profile/identifiers/" + identifier.id).then(function () { FastKit.toast("success", t("form.deleted")); renderProfile(); }).catch(function (e) { FastKit.toast("error", e.message); });
          });
        });
        $list.append($li.append($del));
      });
      methods.body.append($list);
      var $addRow = $('<div class="row g-2 align-items-end"></div>');
      var $typeCol = $('<div class="col-12 col-sm-4"></div>');
      $typeCol.append($('<label class="form-label small"></label>').text(t("profile.method-type")));
      var $type = $('<select class="form-select" data-testid="identifier-type"></select>');
      (profile.identifier_types || []).forEach(function (type) { $type.append($('<option></option>').attr("value", type).text(type)); });
      $typeCol.append($type);
      var $valueCol = $('<div class="col-12 col-sm-5"></div>');
      $valueCol.append($('<label class="form-label small"></label>').text(t("profile.method-value")));
      var $value = $('<input class="form-control" data-testid="identifier-value">').attr("placeholder", t("profile.method-value"));
      $valueCol.append($value);
      var $addCol = $('<div class="col-12 col-sm-3"></div>');
      var $add = $('<button class="btn btn-outline-primary w-100" data-testid="identifier-add"></button>').text(t("profile.add-method"));
      $addCol.append($add);
      $addRow.append($typeCol).append($valueCol).append($addCol);
      methods.body.append($addRow);
      methods.body.append($('<div class="text-danger small mt-1" data-error="value"></div>'));
      $add.on("click", function () {
        api("POST", "/profile/identifiers", { type: $type.val(), value: $value.val() }).then(function () { FastKit.toast("success", t("form.created")); renderProfile(); }).catch(function (e) { FastKit.formErrors(methods.body, e); });
      });
      $wrap.append(methods.card);

      $content.append($wrap);
    }).catch(showError);
  }

  function showError(err) { $("#content").html('<div class="alert alert-danger" data-testid="content-error">' + esc(err.message) + "</div>"); }

  function renderDashboard() {
    var $content = $("#content").empty();
    $("#page-title").text(t("dashboard.title"));
    if (typeof registry.dashboard === "function") {
      registry.dashboard($content[0], { api: api, t: t, navigate: navigate });
      return;
    }
    var $empty = $('<div class="empty" data-testid="dashboard"><div class="empty-icon"><i class="ti ti-layout-dashboard" style="font-size:3rem"></i></div><p class="empty-title"></p><p class="empty-subtitle text-secondary"></p></div>');
    $empty.find(".empty-title").text(t("dashboard.title"));
    $empty.find(".empty-subtitle").text(t("dashboard.empty"));
    $content.append($empty);
  }

  function teardownEditors() {
    if (window.tinymce) { window.tinymce.remove(); }
    jsonEditors.forEach(function (editor) { editor.destroy(); });
    jsonEditors = [];
  }

  function route() {
    beginRender();
    teardownEditors();
    FastKitAdmin.refreshGrid = function () {};
    FastKitAdmin.refreshRow = function () {};
    var rel = location.pathname.slice(ADMIN.length).replace(/^\//, "");
    var segments = rel ? rel.split("/") : [];
    $("[data-nav]").removeClass("active");
    if (!segments.length) {
      $('[data-resource="dashboard"]').addClass("active");
      renderDashboard();
      return;
    }
    if (segments[0] === "profile") { renderProfile(); return; }
    if (segments[0] === "reports") { $('[data-resource="' + segments[1] + '"]').addClass("active"); renderReport(segments[1]); return; }
    $('[data-resource="' + segments[0] + '"]').addClass("active");
    if (segments.length === 1) { renderGrid(segments[0]); }
    else if (segments[1] === "new") { renderForm(segments[0], null); }
    else if (segments.length === 3 && segments[2] === "edit") { renderForm(segments[0], segments[1]); }
    else { renderDetail(segments[0], segments[1]); }
  }

  function closeSidebarDrawer() {
    var menu = document.getElementById("sidebar-menu");
    if (!menu || !menu.classList.contains("show")) { return; }
    if (window.bootstrap && window.bootstrap.Collapse) {
      window.bootstrap.Collapse.getOrCreateInstance(menu).hide();
      return;
    }
    menu.classList.remove("show");
    $(".navbar-toggler").addClass("collapsed").attr("aria-expanded", "false");
  }

  function navigate(url) { history.pushState({}, "", url); route(); }

  function debounce(fn, wait) {
    var timer;
    return function () { clearTimeout(timer); timer = setTimeout(fn, wait); };
  }

  function wireLogin() {
    $("#login-form-el").on("submit", function (e) {
      e.preventDefault();
      var email = $("#login-email").val(), password = $("#login-password").val();
      $("#login-error").addClass("d-none").text("");
      function doLogin(token) {
        api("POST", "/auth/login", { identifier: email, password: password, recaptcha_token: token }).then(function () { window.location.href = ADMIN; })
          .catch(function (err) { $("#login-error").removeClass("d-none").text(err.message); });
      }
      if (CONFIG.recaptcha && CONFIG.recaptcha.enabled && window.grecaptcha) {
        window.grecaptcha.ready(function () { window.grecaptcha.execute(CONFIG.recaptcha.siteKey, { action: CONFIG.recaptcha.action }).then(doLogin); });
      } else { doLogin(null); }
    });
  }

  function setTheme(theme) {
    document.documentElement.setAttribute("data-bs-theme", theme);
    document.body.setAttribute("data-bs-theme", theme);
    localStorage.setItem("fk-theme", theme);
  }

  function wireTheme() {
    setTheme(localStorage.getItem("fk-theme") || "light");
    $(document).on("click", '[data-testid="theme-dark"]', function (e) { e.preventDefault(); setTheme("dark"); });
    $(document).on("click", '[data-testid="theme-light"]', function (e) { e.preventDefault(); setTheme("light"); });
  }

  $(function () {
    wireTheme();
    if ($("#login-form-el").length) { wireLogin(); return; }
    if (!$("#content").length) { return; }

    $(document).ajaxError(function (event, xhr) {
      if (xhr.status === 401) { window.location.href = ADMIN + "/login"; }
    });

    $(document).on("click", "[data-nav]", function (e) {
      e.preventDefault();
      closeSidebarDrawer();
      navigate($(this).attr("href"));
    });
    $(document).on("click", "#logout", function (e) { e.preventDefault(); api("POST", "/auth/logout").then(function () { window.location.href = ADMIN + "/login"; }); });
    window.addEventListener("popstate", route);
    window.dispatchEvent(new CustomEvent("fastkit:ready", { detail: FastKitAdmin }));
    route();
  });
})(jQuery);
