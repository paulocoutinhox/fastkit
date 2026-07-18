(function ($) {
  "use strict";

  var CONFIG = window.__FASTKIT__ || {};
  var API = CONFIG.apiBaseUrl || "/api";

  var LOCALE = CONFIG.locale || "en";
  var MESSAGES = CONFIG.messages || {};

  function registerMessages(locale, dict) {
    if (locale.split("-")[0] === LOCALE.split("-")[0]) { $.extend(MESSAGES, dict); }
  }

  function t(key) {
    return MESSAGES[key] || key;
  }

  function esc(value) {
    return $("<div>").text(value == null ? "" : value).html();
  }

  function localize(root) {
    var $root = root ? $(root) : $(document);
    $root.find("[data-i18n]").each(function () { $(this).text(t($(this).attr("data-i18n"))); });
    $root.find("[data-i18n-placeholder]").each(function () { $(this).attr("placeholder", t($(this).attr("data-i18n-placeholder"))); });
  }

  function toast(kind, message) {
    var color = kind === "error" ? "danger" : kind === "warning" ? "warning" : kind === "info" ? "info" : "success";
    var $el = $('<div class="toast show align-items-center border-0 mb-2" role="alert" aria-live="polite"><div class="d-flex"><div class="toast-body"></div><button type="button" class="btn-close me-2 m-auto" aria-label="Close"></button></div></div>');
    $el.addClass("text-bg-" + color).attr("data-testid", "toast-" + kind);
    $el.find(".btn-close").on("click", function () { $el.remove(); });
    $el.find(".toast-body").text(message);
    root("#fk-toast-root", "position-fixed bottom-0 end-0 p-3").append($el);
    setTimeout(function () { $el.remove(); }, 4000);
  }

  function root(id, cls) {
    var $el = $(id);
    if (!$el.length) {
      $el = $('<div></div>').attr("id", id.slice(1)).addClass(cls).css("z-index", 1090);
      $("body").append($el);
    }
    return $el;
  }

  function modal(options) {
    var opts = options || {};
    var size = opts.size ? "modal-" + opts.size : "";
    var $modal = $('<div class="modal modal-blur fade show d-block" tabindex="-1" style="background: rgba(0,0,0,.4)"><div class="modal-dialog modal-dialog-centered ' + size + '"><div class="modal-content"></div></div></div>');
    if (opts.testid) { $modal.attr("data-testid", opts.testid); }
    var $content = $modal.find(".modal-content");

    if (opts.title) {
      $content.append($('<div class="modal-header"><h3 class="modal-title"></h3><button class="btn-close" data-fk-close></button></div>').find(".modal-title").text(opts.title).end());
    }
    var $body = $('<div class="modal-body"></div>');
    if (typeof opts.body === "string") { $body.html(opts.body); } else if (opts.body) { $body.append(opts.body); }
    $content.append($body);

    function close() {
      if (opts.onClose) { opts.onClose(); }
      $modal.remove();
    }

    if (opts.buttons && opts.buttons.length) {
      var $footer = $('<div class="modal-footer"></div>');
      opts.buttons.forEach(function (button) {
        var $b = $('<button class="btn"></button>').text(button.label);
        if (button.variant) { $b.addClass("btn-" + button.variant); }
        if (button.testid) { $b.attr("data-testid", button.testid); }
        $b.on("click", function () {
          var keepOpen = button.onClick && button.onClick(close) === false;
          if (!keepOpen && button.close !== false) { close(); }
        });
        $footer.append($b);
      });
      $content.append($footer);
    }

    $modal.on("click", "[data-fk-close]", close);
    $("body").append($modal);
    return { close: close, element: $modal };
  }

  function confirmDialog(options) {
    var opts = typeof options === "string" ? { message: options } : (options || {});
    return new Promise(function (resolve) {
      var controller = modal({
        testid: "confirm-dialog",
        size: "sm",
        body: '<div class="text-center py-3"><h3 class="mb-2">' + esc(opts.title || t("confirm.title")) + '</h3><div class="text-secondary"></div></div>',
        buttons: [
          { label: opts.cancelLabel || t("form.cancel"), testid: "confirm-cancel", onClick: function () { resolve(false); } },
          { label: opts.confirmLabel || t("confirm.accept"), variant: opts.danger === false ? "primary" : "danger", testid: "confirm-accept", onClick: function () { resolve(true); } }
        ]
      });
      controller.element.find(".text-secondary").text(opts.message || "");
    });
  }

  function alertDialog(message, title) {
    return new Promise(function (resolve) {
      modal({
        testid: "alert-dialog",
        size: "sm",
        body: '<div class="text-center py-3"><h3 class="mb-2">' + esc(title || "") + '</h3><div class="text-secondary"></div></div>',
        buttons: [{ label: t("confirm.ok"), variant: "primary", testid: "alert-ok", onClick: function () { resolve(); } }]
      }).element.find(".text-secondary").text(message || "");
    });
  }

  function lightbox(src) {
    modal({ testid: "lightbox", size: "lg", body: $('<img class="img-fluid rounded" data-testid="lightbox-image">').attr("src", src) });
  }

  function api(method, path, body) {
    return new Promise(function (resolve, reject) {
      $.ajax({
        method: method,
        url: API + path,
        data: body !== undefined ? JSON.stringify(body) : undefined,
        contentType: "application/json",
        headers: { "Accept-Language": LOCALE, Accept: "application/json" }
      }).done(resolve).fail(function (xhr) {
        var envelope = xhr.responseJSON;
        reject({
          status: xhr.status,
          message: (envelope && envelope.message && envelope.message.text) || t("error.unexpected"),
          fieldErrors: (envelope && envelope.errors) || []
        });
      });
    });
  }

  function upload(url, file) {
    var form = new FormData();
    form.append("file", file);
    return new Promise(function (resolve, reject) {
      $.ajax({ method: "POST", url: url, data: form, processData: false, contentType: false, headers: { "Accept-Language": LOCALE } })
        .done(resolve)
        .fail(function (xhr) {
          var envelope = xhr.responseJSON;
          reject({ message: (envelope && envelope.message && envelope.message.text) || t("error.unexpected") });
        });
    });
  }

  function errorSlot($scope, fieldError, aliases) {
    var path = fieldError.path && fieldError.path.length ? fieldError.path : [fieldError.field];
    if (path.length === 3) {
      return $scope.find('.fk-inline[data-inline="' + path[0] + '"] .fk-inline-rows > .fk-inline-row').eq(path[1]).find('[data-error="' + path[2] + '"]');
    }
    return $scope.find('[data-error="' + (aliases[fieldError.field] || fieldError.field) + '"]');
  }

  function formErrors($scope, error, options) {
    var opts = options || {};
    var aliases = opts.aliases || {};
    $scope.find("[data-error]").text("");
    var $first = null;
    (error.fieldErrors || []).forEach(function (fieldError) {
      var $slot = errorSlot($scope, fieldError, aliases).first();
      if ($slot.length) {
        $slot.text(fieldError.message);
        if ($first === null) { $first = $slot; }
      }
    });
    if ($first === null) {
      toast("error", error.message);
      return false;
    }
    var $field = $first.closest(".mb-3, .col-12, .col").find("input, select, textarea").filter(":visible").first();
    if ($field.length) {
      $field[0].scrollIntoView({ behavior: "smooth", block: "center" });
      $field.trigger("focus");
    }
    return true;
  }

  window.FastKit = {
    locale: LOCALE,
    config: CONFIG,
    t: t,
    esc: esc,
    localize: localize,
    registerMessages: registerMessages,
    toast: toast,
    modal: modal,
    confirm: confirmDialog,
    alert: alertDialog,
    lightbox: lightbox,
    api: api,
    upload: upload,
    formErrors: formErrors
  };

  $(function () { localize(); });
})(jQuery);
