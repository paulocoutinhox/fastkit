import { test, expect } from "@playwright/test";

async function login(page, email = "root@fastkit.local", password = "root-password-123") {
  await page.goto("/admin/login");
  await page.getByTestId("login-email").fill(email);
  await page.getByTestId("login-password").fill(password);
  await page.getByTestId("login-submit").click();
  await expect(page.getByTestId("sidebar")).toBeVisible();
}

async function rowAction(page, prefix) {
  await page.locator('[data-testid^="row-menu-"]').first().click();
  await page.locator('[data-testid^="' + prefix + '"]:visible').first().click();
}

test("login page uses a non-prefilling password field", async ({ page }) => {
  await page.goto("/admin/login");
  await expect(page.getByTestId("login-form")).toBeVisible();
  await expect(page.getByTestId("login-password")).toHaveAttribute("autocomplete", "new-password");
});

test("rejects invalid credentials without showing null", async ({ page }) => {
  await page.goto("/admin/login");
  await page.getByTestId("login-email").fill("root@fastkit.local");
  await page.getByTestId("login-password").fill("wrong-password");
  await page.getByTestId("login-submit").click();

  const error = page.getByTestId("login-error");
  await expect(error).toBeVisible();
  await expect(error).not.toHaveText("null");
  await expect(error).not.toBeEmpty();
  await expect(error.locator(".alert-icon")).toBeVisible();
});

test("signs in and shows the grouped navigation", async ({ page }) => {
  await login(page);
  await expect(page.getByTestId("group-catalog")).toBeVisible();
  await expect(page.getByTestId("nav-products")).toBeVisible();
  await expect(page.getByTestId("brand-name")).toHaveText("FastKit");
});

test("opens on the dashboard, not a specific resource", async ({ page }) => {
  await login(page);
  await expect(page.getByTestId("demo-dashboard")).toBeVisible();
  await expect(page.getByTestId("dash-products")).not.toHaveText("…");

  await page.getByTestId("nav-products").click();
  await expect(page.getByTestId("grid-table")).toBeVisible();
  await page.getByTestId("nav-dashboard").click();
  await expect(page.getByTestId("demo-dashboard")).toBeVisible();
});

test("pressing Enter in a filter applies it", async ({ page }) => {
  await login(page);
  await page.getByTestId("nav-products").click();
  await page.getByTestId("grid-new").click();
  await page.getByTestId("field-name").fill("Enter Probe");
  await page.getByTestId("field-sku").fill("SKU-ENTER");
  await page.getByTestId("field-price").fill("1.00");
  await page.getByTestId("form-save").click();
  await expect(page.getByTestId("toast-success")).toBeVisible();

  await page.getByTestId("grid-filters").click();
  await page.locator('[data-testid="filter-name"] input').fill("Enter Probe");
  await page.locator('[data-testid="filter-name"] input').press("Enter");
  await expect(page.getByText("Enter Probe")).toBeVisible();
  await expect(page.locator('[data-testid^="grid-row"]')).toHaveCount(1);
});

test("lists products and creates one", async ({ page }) => {
  await login(page);
  await page.getByTestId("nav-products").click();
  await expect(page.getByTestId("grid-table")).toBeVisible();

  await page.getByTestId("grid-new").click();
  await page.getByTestId("field-name").fill("Tabler Product");
  await page.getByTestId("field-sku").fill("SKU-TAB");
  await page.getByTestId("field-price").fill("12.34");
  await page.getByTestId("form-save").click();
  await expect(page.getByTestId("toast-success")).toBeVisible();
});

test("shows a field validation error inline", async ({ page }) => {
  await login(page);
  await page.getByTestId("nav-products").click();
  await page.getByTestId("grid-new").click();
  await page.getByTestId("field-name").fill("Broken");
  await page.getByTestId("field-sku").fill("SKU-Z");
  await page.getByTestId("field-price").fill("not-a-number");
  await page.getByTestId("form-save").click();
  await expect(page.getByTestId("error-price")).not.toBeEmpty();
});

test("sorts by header, selects all, and opens a clickable cell", async ({ page }) => {
  await login(page);
  await page.getByTestId("nav-products").click();

  await page.getByTestId("sort-name").click();
  await expect(page.locator('[data-testid="header-name"] .ti-chevron-up')).toBeVisible();

  await page.getByTestId("grid-select-all").check();
  const boxes = page.locator('[data-testid^="select-"]');
  await expect(boxes.first()).toBeChecked();

  await page.locator('[data-testid^="cell-name-"]').first().click();
  await expect(page.getByTestId("form")).toBeVisible();
});

test("click-through cells and sortable headers stay visually neutral", async ({ page }) => {
  await login(page);
  await page.getByTestId("nav-products").click();
  await expect(page.getByTestId("grid-table")).toBeVisible();

  const cell = page.locator('[data-testid^="cell-name-"] a.fk-cell-link').first();
  await expect(cell).toHaveCSS("text-decoration-line", "none");
  await expect(cell).toHaveCSS("font-weight", "400");
  await cell.hover();
  await expect(cell).toHaveCSS("text-decoration-line", "none");

  const header = page.getByTestId("sort-name");
  await header.hover();
  await expect(header).toHaveCSS("text-decoration-line", "none");
});

test("every column opens the edit form by default (not just the first)", async ({ page }) => {
  await login(page);
  await page.getByTestId("nav-products").click();
  await expect(page.getByTestId("grid-table")).toBeVisible();

  // a non-name column cell (sku) is clickable too, by default
  await page.locator('[data-testid^="cell-sku-"] a').first().click();
  await expect(page.getByTestId("form")).toBeVisible();
});

test("clickable_columns restricts which cells are click-through", async ({ page }) => {
  await login(page);
  await page.getByTestId("nav-categories").click();
  await expect(page.getByTestId("grid-table")).toBeVisible();

  // Categories declares clickable_columns = ["name"]: only name is a link
  await expect(page.locator('[data-testid^="cell-name-"] a').first()).toHaveAttribute("href", /\/edit$/);
  await expect(page.locator('[data-testid^="cell-is_active-"] a')).toHaveCount(0);
});

test("row action menu is not clipped by the table on the last row", async ({ page }) => {
  await login(page);
  await page.getByTestId("nav-categories").click();
  const menus = page.locator('[data-testid^="row-menu-"]');
  await menus.last().click();
  const del = page.locator('[data-testid^="delete-"]:visible').last();
  await expect(del).toBeVisible();
  await expect(del).toBeInViewport();
});

async function openCategory(page, label) {
  await page.getByTestId("grid-search").fill(label);
  await page.getByTestId("grid-search").press("Enter");
  await page.locator('[data-testid^="row-menu-"]').first().click();
  await page.locator('[data-testid^="edit-"]:visible').first().click();
  await expect(page.getByTestId("inline-subcategories")).toBeVisible();
}

test("creates and edits repeatable subcategory inline rows on the category form", async ({ page }) => {
  await login(page);
  await page.getByTestId("nav-categories").click();
  await page.getByTestId("grid-new").click();

  const label = "Inline " + Date.now();
  await page.getByTestId("field-name").fill(label);

  const inline = page.getByTestId("inline-subcategories");
  await page.getByTestId("inline-add-subcategories").click();
  await page.getByTestId("inline-add-subcategories").click();
  await inline.getByTestId("field-name").nth(0).fill("Alpha");
  await inline.getByTestId("field-name").nth(1).fill("Beta");
  await page.getByTestId("form-save").click();
  await expect(page.getByTestId("toast-success")).toBeVisible();

  await openCategory(page, label);
  const editInline = page.getByTestId("inline-subcategories");
  await expect(editInline.getByTestId("field-name")).toHaveCount(2);
  await expect(editInline.getByTestId("field-name").nth(0)).toHaveValue("Alpha");

  await editInline.getByTestId("field-name").nth(0).fill("Alpha2");
  await editInline.getByTestId("inline-row-subcategories").nth(1).locator(".fk-inline-remove").click();
  await page.getByTestId("inline-add-subcategories").click();
  await editInline.getByTestId("field-name").nth(1).fill("Gamma");
  await page.getByTestId("form-save").click();
  await expect(page.getByTestId("toast-success")).toBeVisible();

  await openCategory(page, label);
  const finalInline = page.getByTestId("inline-subcategories");
  await expect(finalInline.getByTestId("field-name")).toHaveCount(2);
  const values = await finalInline.getByTestId("field-name").evaluateAll((els) => els.map((el) => el.value).sort());
  expect(values).toEqual(["Alpha2", "Gamma"]);

  await page.getByTestId("nav-categories").click();
  await page.getByTestId("grid-search").fill(label);
  await page.getByTestId("grid-search").press("Enter");
  await page.locator('[data-testid^="row-menu-"]').first().click();
  await page.locator('[data-testid^="delete-"]:visible').first().click();
  await page.getByTestId("confirm-accept").click();
  await expect(page.getByTestId("toast-success")).toBeVisible();
});

test("deletes a row only after confirmation", async ({ page }) => {
  await login(page);
  await page.getByTestId("nav-products").click();

  await rowAction(page, "delete-");
  await expect(page.getByTestId("confirm-dialog")).toBeVisible();
  await page.getByTestId("confirm-cancel").click();
  await expect(page.getByTestId("confirm-dialog")).toHaveCount(0);

  await rowAction(page, "delete-");
  await page.getByTestId("confirm-accept").click();
  await expect(page.getByTestId("toast-success")).toBeVisible();
});

test("runs a bulk action behind a confirmation", async ({ page }) => {
  await login(page);
  await page.getByTestId("nav-products").click();
  await page.locator('[data-testid^="select-"]').first().check();
  await page.getByTestId("bulk-menu").click();
  await page.getByTestId("bulk-deactivate").click();
  await expect(page.getByTestId("confirm-dialog")).toBeVisible();
  await page.getByTestId("confirm-accept").click();
  await expect(page.getByTestId("toast-success")).toBeVisible();
});

test("edits every field type on the showcase form", async ({ page }) => {
  await login(page);
  await page.getByTestId("nav-showcase").click();
  await page.getByTestId("grid-new").click();

  // fieldsets render as separate cards
  await expect(page.getByTestId("fieldset-0")).toBeVisible();
  await expect(page.getByTestId("fieldset-1")).toBeVisible();

  await page.getByTestId("field-title").fill("Showcase via Tabler");
  await page.getByTestId("field-quantity").fill("9");
  await page.getByTestId("field-price").fill("10.00");
  await expect(page.locator(".tox-tinymce").first()).toBeVisible();

  // masked field
  await page.getByTestId("field-reference_code").fill("12345678");
  await expect(page.getByTestId("field-reference_code")).toHaveValue("12-3456-78");

  // url + email widgets
  await expect(page.getByTestId("field-website")).toHaveAttribute("type", "url");
  await expect(page.getByTestId("field-contact_email")).toHaveAttribute("type", "email");
  await expect(page.getByTestId("field-brand_color")).toBeVisible();

  await page.getByTestId("form-save").click();
  await expect(page.getByTestId("toast-success")).toBeVisible();
});

test("dependent relation select loads its options and keeps its value on edit", async ({ page }) => {
  await login(page);
  await page.getByTestId("nav-products").click();
  await page.locator('[data-testid^="cell-name-"]').filter({ hasText: "Pro Plan" }).click();

  await expect(page.getByTestId("field-category_id")).not.toHaveValue("");
  const sub = page.getByTestId("field-subcategory_id");
  await expect(sub).not.toHaveValue("");
  await expect(sub.locator("option").nth(1)).toBeAttached();
});

test("grid defaults to descending primary-key order", async ({ page }) => {
  await login(page);
  await page.getByTestId("nav-products").click();
  await expect(page.locator('[data-testid^="cell-id-"]').first()).toBeVisible();
  const ids = (await page.locator('[data-testid^="cell-id-"]').allTextContents()).map(Number);
  const descending = [...ids].sort((a, b) => b - a);
  expect(ids).toEqual(descending);
});

test("changing the parent relation reloads and clears the dependent select", async ({ page }) => {
  await login(page);
  await page.getByTestId("nav-products").click();
  await page.getByTestId("grid-new").click();

  await expect(page.getByTestId("field-subcategory_id")).toHaveValue("");
  await page.getByTestId("field-category_id").selectOption({ index: 1 });
  await expect(page.getByTestId("field-subcategory_id").locator("option").nth(1)).toBeAttached();
  await page.getByTestId("field-subcategory_id").selectOption({ index: 1 });
  await expect(page.getByTestId("field-subcategory_id")).not.toHaveValue("");
});

test("blocks saving while dependent options are still loading", async ({ page }) => {
  await page.route("**/resources/products/options/subcategory_id*", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 1500));
    await route.continue();
  });
  await login(page);
  await page.getByTestId("nav-products").click();
  await page.getByTestId("grid-new").click();
  await page.getByTestId("field-name").fill("Race Product");
  await page.getByTestId("field-sku").fill("SKU-RACE");
  await page.getByTestId("field-price").fill("5.00");
  await page.getByTestId("field-category_id").selectOption({ index: 1 });
  await page.getByTestId("form-save").click();
  await expect(page.getByTestId("toast-warning")).toBeVisible();
});

test("editing a record blocks save until its relation options finish the initial slow load", async ({ page }) => {
  await login(page);
  await page.getByTestId("nav-geo-samples").click();
  await expect(page.getByTestId("grid-table")).toBeVisible({ timeout: 15000 });

  // open the first record's edit form; its country select is still doing its slow initial load
  await page.locator('[data-testid^="cell-name-"] a').first().click();
  await expect(page.getByTestId("form")).toBeVisible();

  // saving now must be blocked (not silently wipe the FK with an empty select value)
  await page.getByTestId("form-save").click();
  await expect(page.getByTestId("toast-warning")).toBeVisible();
});

test("searches a lookup field and selects a match", async ({ page }) => {
  await login(page);
  await page.getByTestId("nav-showcase").click();
  await page.getByTestId("grid-new").click();

  await page.getByTestId("field-category_id").fill("Prem");
  await page.getByTestId("lookup-option-2").click();
  await expect(page.getByTestId("field-category_id")).toHaveValue("Premium");
});

test("lookup lists initial options on focus before typing", async ({ page }) => {
  await login(page);
  await page.getByTestId("nav-showcase").click();
  await page.getByTestId("grid-new").click();

  await page.getByTestId("field-category_id").focus();
  await expect(page.locator('[data-testid^="lookup-option-"]').first()).toBeVisible();
});

test("product view shows the full record including metadata", async ({ page }) => {
  await login(page);
  await page.getByTestId("nav-products").click();
  await rowAction(page, "view-");
  await expect(page.getByTestId("detail-name")).toBeVisible();
  await expect(page.getByTestId("detail-created_at")).toBeVisible();
  await expect(page.getByTestId("detail-updated_at")).toBeVisible();
});

test("boolean columns and headers are centered by default", async ({ page }) => {
  await login(page);
  await page.getByTestId("nav-products").click();
  await expect(page.getByTestId("header-is_active")).toHaveCSS("text-align", "center");
  await expect(page.locator('[data-testid^="cell-is_active-"]').first()).toHaveCSS("text-align", "center");
});

test("product filters include dependent category and subcategory lookups", async ({ page }) => {
  await login(page);
  await page.getByTestId("nav-products").click();
  await page.getByTestId("grid-filters").click();
  await expect(page.getByTestId("filters-panel").locator(".card-title")).toHaveText("Filters");
  await expect(page.locator('[data-testid="filter-category_id"] .fk-lookup')).toBeVisible();
  await expect(page.locator('[data-testid="filter-subcategory_id"] .fk-lookup')).toBeVisible();
  await page.locator('[data-testid="filter-category_id"] input').focus();
  await expect(page.locator('[data-testid^="lookup-option-"]').first()).toBeVisible();
});

test("changing a parent filter lookup resets the dependent child lookup", async ({ page }) => {
  await login(page);
  await page.getByTestId("nav-products").click();
  await page.getByTestId("grid-filters").click();
  const catCell = page.locator('[data-testid="filter-category_id"]');
  const subCell = page.locator('[data-testid="filter-subcategory_id"]');
  await catCell.locator("input").focus();
  await catCell.locator('[data-testid^="lookup-option-"]').first().click();
  await subCell.locator("input").focus();
  await subCell.locator('[data-testid^="lookup-option-"]').first().click();
  await expect(subCell.locator("input")).not.toHaveValue("");
  await catCell.locator("input").focus();
  await catCell.locator('[data-testid^="lookup-option-"]').last().click();
  await expect(subCell.locator("input")).toHaveValue("");
});

test("shows the read-only detail screen for a view-only user", async ({ page }) => {
  await login(page, "viewer@fastkit.local", "viewer-password-123");
  await page.getByTestId("nav-products").click();
  await rowAction(page, "view-");
  await expect(page.getByTestId("detail-name")).toBeVisible();
  await expect(page.getByTestId("detail-close")).toBeVisible();
});

test("viewer sees only view action and cannot reach create/edit screens", async ({ page }) => {
  await login(page, "viewer@fastkit.local", "viewer-password-123");
  await page.getByTestId("nav-products").click();
  await expect(page.getByTestId("grid-new")).toHaveCount(0);

  await page.locator('[data-testid^="row-menu-"]').first().click();
  await expect(page.locator('[data-testid^="view-"]:visible').first()).toBeVisible();
  await expect(page.locator('[data-testid^="edit-"]')).toHaveCount(0);
  await expect(page.locator('[data-testid^="delete-"]')).toHaveCount(0);

  await page.goto("/admin/products/new");
  await expect(page.getByTestId("content-error")).toBeVisible();
});

test("deletes a login method only after confirmation", async ({ page }) => {
  await login(page);
  await page.getByTestId("user-menu").click();
  await page.getByTestId("menu-profile").click();
  await expect(page.getByTestId("profile")).toBeVisible();

  await page.locator('[data-testid^="identifier-delete-"]').first().click();
  await expect(page.getByTestId("confirm-dialog")).toBeVisible();
  await page.getByTestId("confirm-cancel").click();
  await expect(page.getByTestId("identifiers")).toBeVisible();
});

test("updates the profile display name and reflects it in the header", async ({ page }) => {
  await login(page);
  await page.getByTestId("user-menu").click();
  await page.getByTestId("menu-profile").click();
  await page.getByTestId("profile-display-name").fill("Root Updated");
  await page.getByTestId("profile-save").click();
  await expect(page.getByTestId("toast-success")).toBeVisible();
  await expect(page.getByTestId("user-name")).toHaveText("Root Updated");
});

const PNG_1PX = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAIAAABLbSncAAAAFElEQVR4nGP0d3vKgA0wYRUdtBIAKt0Bij/iKGMAAAAASUVORK5CYII=", "base64");

test("profile: avatar upload, password validation, add and remove login method", async ({ page }) => {
  await login(page);
  await page.getByTestId("user-menu").click();
  await page.getByTestId("menu-profile").click();
  await expect(page.getByTestId("profile")).toBeVisible();

  await page.getByTestId("profile-avatar-input").setInputFiles({ name: "a.png", mimeType: "image/png", buffer: PNG_1PX });
  await expect(page.getByTestId("toast-success")).toBeVisible();
  await expect(page.getByTestId("profile-avatar")).toHaveCSS("background-image", /url\(/);

  // the navbar avatar updates live, without a reload
  await expect(page.getByTestId("user-avatar")).toHaveCSS("background-image", /url\(/);

  // a full reload shows the avatar in the server-rendered header, and the stored file is a square webp
  await page.reload();
  const headerAvatar = page.getByTestId("user-avatar");
  await expect(headerAvatar).toHaveCSS("background-image", /url\(.*\.webp/);

  // a too-short new password shows a field error under the new-password field, not a generic toast
  await page.getByTestId("profile-current-password").fill("root-password-123");
  await page.getByTestId("profile-new-password").fill("short");
  await page.getByTestId("profile-password-save").click();
  await expect(page.locator('[data-error="new_password"]')).toContainText(/at least/i);

  // a wrong current password shows a translated field error (not the raw validation code)
  await page.getByTestId("profile-current-password").fill("wrong-password");
  await page.getByTestId("profile-new-password").fill("valid-password-1234");
  await page.getByTestId("profile-password-save").click();
  await expect(page.locator('[data-error="current_password"]')).toContainText(/incorrect/i);
  await expect(page.locator('[data-error="current_password"]')).not.toContainText("validation.");

  // the uploaded avatar persists after navigating away and back
  await page.getByTestId("nav-products").click();
  await page.getByTestId("user-menu").click();
  await page.getByTestId("menu-profile").click();
  await expect(page.getByTestId("profile-avatar")).toHaveCSS("background-image", /url\(/);

  // an invalid login-method value shows the field error under the value input (not a generic toast)
  await page.getByTestId("identifier-type").selectOption("email");
  await page.getByTestId("identifier-value").fill("not-an-email");
  await page.getByTestId("identifier-add").click();
  await expect(page.locator('[data-error="value"]')).toContainText(/valid email/i);

  await page.getByTestId("identifier-type").selectOption("phone");
  await page.getByTestId("identifier-value").fill("+5511987654321");
  await page.getByTestId("identifier-add").click();
  await expect(page.getByTestId("identifier-delete-phone")).toBeVisible();
  await page.getByTestId("identifier-delete-phone").click();
  await page.getByTestId("confirm-accept").click();
  await expect(page.getByTestId("toast-success")).toBeVisible();
});

test("edits a role through the grouped permission matrix", async ({ page }) => {
  await login(page);
  await page.getByTestId("nav-roles").click();
  await rowAction(page, "edit-");
  await expect(page.getByTestId("permission-users.view")).toBeVisible();
  await page.getByTestId("permission-users.view").click();
  await page.getByTestId("form-save").click();
  await expect(page.getByTestId("toast-success")).toBeVisible();
});

test("the role detail view lists granted permissions grouped by module", async ({ page }) => {
  await login(page);
  await page.getByTestId("nav-roles").click();
  await rowAction(page, "view-");
  await expect(page.getByTestId("detail-permissions_matrix")).toBeVisible();
  await expect(page.getByTestId("detail-permission-products.view")).toBeVisible();
});

test("lets an external script add a row action through the extension bridge", async ({ page }) => {
  await page.addInitScript(() => {
    window.addEventListener("fastkit:ready", () => {
      window.__pinged = false;
      window.FastKitAdmin.registerRowAction("products", { name: "ping", label: "Ping", onClick: () => { window.__pinged = true; } });
    });
  });
  await login(page);
  await page.getByTestId("nav-products").click();
  await rowAction(page, "ext-action-ping-");
  await expect.poll(() => page.evaluate(() => window.__pinged)).toBe(true);
});

test.describe("with a Portuguese browser", () => {
  test.use({ locale: "pt-BR" });

  test("auto-detects the interface locale", async ({ page }) => {
    await login(page);
    await page.getByTestId("nav-products").click();
    await expect(page.getByTestId("grid-new")).toHaveText("Novo");
  });

  test("localizes the server-rendered login page", async ({ page }) => {
    await page.goto("/admin/login");
    await expect(page.getByTestId("login-submit")).toHaveText("Entrar");
  });

  test("translates fieldset titles, field labels, column headers and menu", async ({ page }) => {
    await login(page);
    await expect(page.getByTestId("group-catalog")).toContainText("Catálogo");
    await expect(page.getByTestId("nav-products")).toContainText("Produtos");
    await page.getByTestId("nav-products").click();
    await expect(page.getByTestId("header-price")).toContainText("Preço");
    await page.getByTestId("grid-new").click();
    await expect(page.getByTestId("fieldset-1")).toContainText("Classificação");
    await expect(page.getByTestId("fieldset-1").locator("label.form-label").first()).toHaveText("Categoria");
  });
});

test("navigating away before a response resolves does not corrupt the new view", async ({ page }) => {
  await login(page);
  await page.route("**/resources/products/schema*", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 700));
    await route.continue();
  });
  await page.getByTestId("nav-products").click();
  await page.getByTestId("nav-categories").click();
  await expect(page.getByTestId("screen-title")).toHaveText("Categories");
  await page.waitForTimeout(900);
  await expect(page.getByTestId("screen-title")).toHaveText("Categories");
  await expect(page.getByTestId("header-name")).toBeVisible();
});

test("shows the id column in the grid", async ({ page }) => {
  await login(page);
  await page.getByTestId("nav-products").click();
  await expect(page.getByTestId("header-id")).toBeVisible();
  await expect(page.locator('[data-testid^="cell-id-"]').first()).not.toBeEmpty();
});

test("filters a grid through the filter panel and narrows results", async ({ page }) => {
  await login(page);
  await page.getByTestId("nav-products").click();
  await page.getByTestId("grid-new").click();
  await page.getByTestId("field-name").fill("ZZ Filter Probe");
  await page.getByTestId("field-sku").fill("SKU-PROBE");
  await page.getByTestId("field-price").fill("1.00");
  await page.getByTestId("form-save").click();
  await expect(page.getByTestId("toast-success")).toBeVisible();

  await page.getByTestId("grid-filters").click();
  await expect(page.getByTestId("filters-panel")).toBeVisible();
  await page.locator('[data-testid="filter-name"] input').fill("ZZ Filter Probe");
  await page.getByTestId("filters-apply").click();
  await expect(page.getByText("ZZ Filter Probe")).toBeVisible();
  await expect(page.locator('[data-testid^="grid-row"]')).toHaveCount(1);
});

test("enum filter narrows the task runs grid", async ({ page }) => {
  await login(page);
  await page.getByTestId("nav-task-runs").click();
  await page.getByTestId("grid-filters").click();
  await page.locator('[data-testid="filter-status"] select').selectOption("running");
  await page.getByTestId("filters-apply").click();
  await expect(page.getByText("demo.sync")).toBeVisible();
  await expect(page.getByText("demo.cleanup")).toHaveCount(0);
});

test("activity log filters render grouped with a lookup", async ({ page }) => {
  await login(page);
  await page.getByTestId("nav-activity").click();
  await page.getByTestId("grid-filters").click();
  await expect(page.getByTestId("filters-panel")).toBeVisible();
  await expect(page.locator('[data-testid="filter-created_at-from"]')).toBeVisible();
  await expect(page.locator('[data-testid="filter-user_id"] .fk-lookup')).toBeVisible();
  await page.locator('[data-testid="filter-user_id"] input').focus();
  await expect(page.locator('[data-testid^="lookup-option-"]').first()).toBeVisible();
});

test("json fields use the JSONEditor widget", async ({ page }) => {
  await login(page);
  await page.getByTestId("nav-showcase").click();
  await page.getByTestId("grid-new").click();
  await expect(page.locator('[data-testid="json-attributes"] .jsoneditor')).toBeVisible();
  await expect(page.locator('[data-testid="json-attributes"] .jsoneditor-menu')).toBeVisible();
});

test("rich text editor keeps absolute media urls (convert_urls off)", async ({ page }) => {
  await login(page);
  await page.getByTestId("nav-showcase").click();
  await page.getByTestId("grid-new").click();
  await expect(page.locator(".tox-tinymce").first()).toBeVisible();

  const content = await page.evaluate(() => {
    const editor = window.tinymce.get("field-body_html");
    editor.setContent('<p><img src="/media/0/ab/pic.png"></p>');
    return editor.getContent();
  });
  expect(content).toContain('src="/media/0/ab/pic.png"');
});

test("rich text editor exposes an image upload button", async ({ page }) => {
  await login(page);
  await page.getByTestId("nav-showcase").click();
  await page.getByTestId("grid-new").click();
  await expect(page.locator('.tox-tinymce .tox-tbtn[aria-label*="image" i]').first()).toBeVisible();
});

test("server-rendered html cells render as markup, not escaped text", async ({ page }) => {
  await login(page);
  await page.getByTestId("nav-showcase").click();
  const swatch = page.locator('[data-testid^="cell-swatch-"] span[style*="border-radius"]').first();
  await expect(swatch).toBeVisible();
  await expect(page.locator('[data-testid^="cell-swatch-"]').first()).not.toContainText("<span");
});

test("boolean columns render an icon, not text", async ({ page }) => {
  await login(page);
  await page.getByTestId("nav-products").click();
  const cell = page.locator('[data-testid^="cell-is_active-"]').first();
  await expect(cell.locator("svg")).toHaveCount(1);
});

test("showcase grid renders custom badge and computed cells", async ({ page }) => {
  await login(page);
  await page.getByTestId("nav-showcase").click();
  await expect(page.locator('[data-testid^="status-badge-"]').first()).toBeVisible();
  await expect(page.locator('[data-testid^="feature-toggle-"]').first()).toBeVisible();
});

test("edits a cell value through an ajax modal and refreshes the row", async ({ page }) => {
  await login(page);
  await page.getByTestId("nav-showcase").click();

  const quantityCell = page.locator('[data-testid^="quantity-edit-"]').first();
  await quantityCell.click();
  await page.getByTestId("quantity-input").fill("77");
  await page.getByTestId("quantity-save").click();
  await expect(page.getByTestId("toast-success")).toBeVisible();
  await expect(page.locator('[data-testid^="quantity-edit-"]').first()).toHaveText("77");
});

test("toggles a boolean cell via an extension renderer", async ({ page }) => {
  await login(page);
  await page.getByTestId("nav-showcase").click();
  const toggle = page.locator('[data-testid^="feature-toggle-"]').first();
  const before = await toggle.textContent();
  await toggle.click();
  await expect(page.getByTestId("toast-success")).toBeVisible();
  await expect(page.locator('[data-testid^="feature-toggle-"]').first()).not.toHaveText(before);
});

test("manages per-language content translations", async ({ page }) => {
  await login(page);
  await page.getByTestId("nav-content").click();
  await page.getByTestId("grid-new").click();

  await page.getByTestId("field-key").fill("home.title");
  await page.getByTestId("field-type").selectOption("html");
  await page.getByTestId("translation-en").fill("<p>Welcome</p>");
  await page.getByTestId("translation-pt").fill("<p>Bem-vindo</p>");
  await page.getByTestId("form-save").click();
  await expect(page.getByTestId("toast-success")).toBeVisible();

  await rowAction(page, "edit-");
  await expect(page.getByTestId("translation-pt")).toHaveValue("<p>Bem-vindo</p>");
});

test("pagination is bounded on a single-page grid", async ({ page }) => {
  await login(page);
  await page.getByTestId("nav-categories").click();
  await expect(page.getByTestId("grid-table")).toBeVisible();
  await expect(page.getByTestId("grid-prev").locator("xpath=..")).toHaveClass(/disabled/);
  await expect(page.getByTestId("grid-next").locator("xpath=..")).toHaveClass(/disabled/);
  await expect(page.locator('[data-testid="grid-pagination"] .page-item.active')).toHaveText("1");
  await expect(page.getByTestId("grid-total")).toContainText("of 2");
});

test("multi-tenant, tasks and reports admin screens work", async ({ page }) => {
  await login(page);
  await page.getByTestId("nav-tenants").click();
  await expect(page.getByTestId("grid-table")).toBeVisible();
  await expect(page.getByText("Acme Inc.")).toBeVisible();

  await page.getByTestId("nav-task-runs").click();
  await expect(page.getByTestId("grid-table")).toBeVisible();
  await expect(page.locator('[data-testid^="cell-status-"] .badge').first()).toBeVisible();

  await page.getByTestId("nav-report-runs").click();
  await expect(page.getByTestId("grid-table")).toBeVisible();
  await expect(page.getByText("sales.summary")).toBeVisible();
});

test("toggles light and dark theme from the header and persists it", async ({ page }) => {
  await login(page);
  await expect(page.locator("html")).toHaveAttribute("data-bs-theme", "light");

  await page.getByTestId("theme-dark").click();
  await expect(page.locator("html")).toHaveAttribute("data-bs-theme", "dark");

  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-bs-theme", "dark");
  await expect(page.getByTestId("nav-products")).toBeVisible();

  await page.getByTestId("theme-light").click();
  await expect(page.locator("html")).toHaveAttribute("data-bs-theme", "light");
});

test("floating action menus follow the dark theme", async ({ page }) => {
  await login(page);
  await page.getByTestId("nav-products").click();
  await page.getByTestId("theme-dark").click();
  await page.locator('[data-testid^="row-menu-"]').first().click();
  const menu = page.locator('.fk-menu-fixed .dropdown-menu.show').first();
  await expect(menu).toHaveAttribute("data-bs-theme", "dark");
  const bg = await menu.evaluate((el) => getComputedStyle(el).backgroundColor);
  expect(bg).not.toBe("rgb(255, 255, 255)");
});

test("users grid shows which tenant each user belongs to", async ({ page }) => {
  await login(page);
  await page.getByTestId("nav-users").click();
  await expect(page.getByTestId("header-tenant")).toBeVisible();
  await expect(page.getByText("Acme Inc.")).toBeVisible();
  await expect(page.getByText("Global").first()).toBeVisible();
});

test("each report is its own screen with filters and export buttons", async ({ page }) => {
  await login(page);
  await page.getByTestId("nav-sales-by-category").click();
  await expect(page.getByTestId("filters-panel")).toBeVisible();
  const rows = page.locator('[data-testid="report-row"]');
  await expect(rows.filter({ hasText: "General" })).toHaveCount(1);
  await expect(rows.filter({ hasText: "Premium" })).toHaveCount(1);

  await expect(page.getByTestId("report-export-csv")).toBeVisible();
  await expect(page.getByTestId("report-export-pdf")).toBeVisible();
  await expect(page.getByTestId("report-export-html")).toBeVisible();

  const catCell = page.locator('[data-testid="filter-category_id"]');
  await catCell.locator("input").focus();
  await catCell.locator('[data-testid^="lookup-option-"]').filter({ hasText: "Premium" }).click();
  await page.getByTestId("filters-apply").click();
  await expect(rows.filter({ hasText: "Premium" })).toHaveCount(1);
  await expect(rows.filter({ hasText: "General" })).toHaveCount(0);
  await expect(page.getByTestId("report-export-csv")).toHaveAttribute("href", /category_id=\d+/);
});

test("report filters have full parity with grid filters, including lookup cascades", async ({ page }) => {
  await login(page);
  await page.getByTestId("nav-product-prices").click();
  await expect(page.getByTestId("filters-panel")).toBeVisible();
  await expect(page.locator('[data-testid="report-row"]').first()).toBeVisible();

  const catCell = page.locator('[data-testid="filter-category_id"]');
  await catCell.locator("input").focus();
  await catCell.locator('[data-testid^="lookup-option-"]').filter({ hasText: "Premium" }).click();

  const subCell = page.locator('[data-testid="filter-subcategory_id"]');
  await subCell.locator("input").focus();
  await expect(subCell.locator('[data-testid^="lookup-option-"]').first()).toBeVisible();
  await subCell.locator('[data-testid^="lookup-option-"]').first().click();
  await page.getByTestId("filters-apply").click();
  await expect(page.getByTestId("report-export-csv")).toHaveAttribute("href", /subcategory_id=\d+/);
});

test("enqueues a background task from the task runs toolbar", async ({ page }) => {
  await login(page);
  await page.getByTestId("nav-task-runs").click();
  await page.getByTestId("collection-enqueue_email").click();
  await expect(page.getByTestId("toast-success")).toBeVisible();
  await expect(page.getByText("demo.send_welcome_email")).toBeVisible();
});

test("datetimes render in the user's timezone", async ({ page }) => {
  await login(page);
  expect(await page.evaluate(() => window.__FASTKIT__.timezone)).toBe("America/Sao_Paulo");

  await page.getByTestId("nav-task-runs").click();
  await page.getByTestId("grid-filters").click();
  await page.locator('[data-testid="filter-status"] select').selectOption("running");
  await page.getByTestId("filters-apply").click();
  await expect(page.locator('[data-testid^="cell-started_at-"]').first()).toContainText("6:00");
});

test("the activity log is read-only and records actions", async ({ page }) => {
  await login(page);
  await page.getByTestId("nav-activity").click();
  await expect(page.getByTestId("grid-table")).toBeVisible();
  await expect(page.getByTestId("grid-new")).toHaveCount(0);
  await expect(page.locator('[data-testid^="grid-row-"]').first()).toBeVisible();
});

test.describe("on a phone", () => {
  test.use({ viewport: { width: 390, height: 800 } });

  test("opens the sidebar menu with the hamburger", async ({ page }) => {
    await login(page);
    await expect(page.getByTestId("sidebar-toggle")).toBeVisible();
    await page.getByTestId("sidebar-toggle").click();
    await expect(page.locator("#sidebar-menu")).toHaveClass(/show/);
  });

  test("selecting a menu item closes the drawer and resets the toggler", async ({ page }) => {
    await login(page);
    await page.getByTestId("sidebar-toggle").click();
    await expect(page.locator("#sidebar-menu")).toHaveClass(/show/);
    await page.getByTestId("nav-categories").click();
    await expect(page.locator("#sidebar-menu")).not.toHaveClass(/show/);
    await expect(page.getByTestId("sidebar-toggle")).toHaveAttribute("aria-expanded", "false");
  });

  test("grid toolbar buttons stay within the viewport", async ({ page }) => {
    await login(page);
    await page.goto("/admin/products");
    await expect(page.getByTestId("grid-search")).toBeVisible();
    await expect(page.getByTestId("grid-new")).toBeVisible();
    const box = await page.getByTestId("grid-new").boundingBox();
    expect(box.x + box.width).toBeLessThanOrEqual(390);
  });
});

test("focuses the first field with a validation error on save", async ({ page }) => {
  await login(page);
  await page.goto("/admin/products/new");
  await page.getByTestId("form-save").click();
  await expect(page.locator('[data-error="name"]')).toHaveText("This field is required.");
  await expect(page.getByTestId("field-name")).toBeFocused();
});

test("sidebar groups are collapsible", async ({ page }) => {
  await login(page);
  await expect(page.getByTestId("nav-products")).toBeVisible();
  await page.getByTestId("group-catalog").click();
  await expect(page.getByTestId("nav-products")).toBeHidden();
  await page.getByTestId("group-catalog").click();
  await expect(page.getByTestId("nav-products")).toBeVisible();
});

test("signs out back to the login screen", async ({ page }) => {
  await login(page);
  await page.getByTestId("user-menu").click();
  await page.getByTestId("logout").click();
  await expect(page.getByTestId("login-form")).toBeVisible();
});

test("dependent select shows a loading spinner and disables while fetching remote options", async ({ page }) => {
  await login(page);
  await page.goto("/admin/geo-samples/new");
  await expect(page.getByTestId("form")).toBeVisible();

  const country = page.getByTestId("field-sel_country");
  await expect(page.getByTestId("loading-sel_country")).toBeVisible();
  await expect(country).toBeDisabled();

  await expect(page.getByTestId("loading-sel_country")).toBeHidden({ timeout: 15000 });
  await expect(country).toBeEnabled();
  await expect(country.locator('option[value="br"]')).toHaveCount(1);
});

test("triple dependent selects cascade country to state to city", async ({ page }) => {
  await login(page);
  await page.goto("/admin/geo-samples/new");
  await expect(page.getByTestId("loading-sel_country")).toBeHidden({ timeout: 15000 });

  await page.getByTestId("field-sel_country").selectOption("br");
  await expect(page.getByTestId("loading-sel_state")).toBeVisible();
  await expect(page.getByTestId("field-sel_state").locator('option[value="sp"]')).toHaveCount(1, { timeout: 15000 });

  await page.getByTestId("field-sel_state").selectOption("sp");
  await expect(page.getByTestId("field-sel_city").locator('option[value="sao"]')).toHaveCount(1, { timeout: 15000 });
});

test("dependent lookup shows a translated loading message while fetching", async ({ page }) => {
  await login(page);
  await page.goto("/admin/geo-samples/new");
  await page.getByTestId("field-look_country").click();

  const loading = page.getByTestId("lookup-loading");
  await expect(loading).toBeVisible();
  await expect(loading).toContainText("Loading");
});

test("the lookup loading message is translated for a pt user", async ({ page, context }) => {
  await context.addCookies([{ name: "fastkit_locale", value: "pt", url: "http://127.0.0.1:8100" }]);
  await login(page);
  await page.goto("/admin/geo-samples/new");
  await page.getByTestId("field-look_country").click();

  await expect(page.getByTestId("lookup-loading")).toContainText("Carregando");
});

test("grid shows a loading overlay while the fragment reloads", async ({ page }) => {
  await login(page);
  await page.getByTestId("nav-geo-samples").click();
  await expect(page.getByTestId("grid-table")).toBeVisible({ timeout: 15000 });

  await page.getByTestId("grid-search").fill("Sample");
  await page.getByTestId("grid-search").press("Enter");
  await expect(page.getByTestId("content-loading")).toBeVisible();
  await expect(page.getByTestId("content-loading")).toBeHidden({ timeout: 15000 });
});

test("a full-page navigation shows a progress indicator the instant a link is clicked", async ({ page }) => {
  await login(page);

  // click an internal nav link and check the bar synchronously, before the navigation commits
  // (a late-registered listener cancels the real navigation so the assertion is deterministic)
  const shown = await page.evaluate(() => {
    document.addEventListener("click", (event) => event.preventDefault());
    document.querySelector('[data-testid="nav-geo-samples"]').click();
    return !!document.querySelector("#fk-nav-progress.fk-progress-active");
  });

  expect(shown).toBe(true);
});

async function pickGeoChain(page) {
  await page.goto("/admin/geo-samples/new");
  await expect(page.getByTestId("loading-sel_country")).toBeHidden({ timeout: 15000 });
  await page.getByTestId("field-sel_country").selectOption("us");
  await expect(page.getByTestId("field-sel_state").locator('option[value="ca"]')).toHaveCount(1, { timeout: 15000 });
  await page.getByTestId("field-sel_state").selectOption("ca");
  await expect(page.getByTestId("field-sel_city").locator('option[value="la"]')).toHaveCount(1, { timeout: 15000 });
  await page.getByTestId("field-sel_city").selectOption("la");
  await expect(page.getByTestId("field-sel_district").locator('option[value="hol"]')).toHaveCount(1, { timeout: 15000 });
  await page.getByTestId("field-sel_district").selectOption("hol");
  await expect(page.getByTestId("field-sel_district")).toHaveValue("hol");
}

test("changing the top select cascades a reset through every downstream select (4 levels deep)", async ({ page }) => {
  await login(page);
  await pickGeoChain(page);

  await page.getByTestId("field-sel_country").selectOption("br");

  // every level below the changed one must reset, not just the direct child
  await expect(page.getByTestId("field-sel_district")).toHaveValue("", { timeout: 15000 });
  await expect(page.getByTestId("field-sel_city")).toHaveValue("", { timeout: 15000 });
  await expect(page.getByTestId("field-sel_district").locator('option[value="hol"]')).toHaveCount(0, { timeout: 15000 });
  await expect(page.getByTestId("field-sel_city").locator('option[value="la"]')).toHaveCount(0, { timeout: 15000 });
  await expect(page.getByTestId("field-sel_state").locator('option[value="sp"]')).toHaveCount(1, { timeout: 15000 });
  await expect(page.getByTestId("field-sel_state").locator('option[value="ca"]')).toHaveCount(0);
});

test("changing a middle select reloads and clears the select below it", async ({ page }) => {
  await login(page);
  await page.goto("/admin/geo-samples/new");
  await expect(page.getByTestId("loading-sel_country")).toBeHidden({ timeout: 15000 });

  await page.getByTestId("field-sel_country").selectOption("br");
  await expect(page.getByTestId("field-sel_state").locator('option[value="sp"]')).toHaveCount(1, { timeout: 15000 });
  await page.getByTestId("field-sel_state").selectOption("sp");
  await expect(page.getByTestId("field-sel_city").locator('option[value="sao"]')).toHaveCount(1, { timeout: 15000 });
  await page.getByTestId("field-sel_city").selectOption("sao");

  await page.getByTestId("field-sel_state").selectOption("rj");

  await expect(page.getByTestId("field-sel_city")).toHaveValue("", { timeout: 15000 });
  await expect(page.getByTestId("field-sel_city").locator('option[value="rio"]')).toHaveCount(1, { timeout: 15000 });
  await expect(page.getByTestId("field-sel_city").locator('option[value="sao"]')).toHaveCount(0);
});

test("a failed dependent options request re-enables the select instead of leaving it stuck", async ({ page }) => {
  await login(page);
  await page.goto("/admin/geo-samples/new");
  await expect(page.getByTestId("loading-sel_country")).toBeHidden({ timeout: 15000 });

  await page.route("**/resources/geo-samples/options/sel_state**", (route) => route.abort());
  await page.getByTestId("field-sel_country").selectOption("br");

  await expect(page.getByTestId("loading-sel_state")).toBeHidden({ timeout: 15000 });
  await expect(page.getByTestId("field-sel_state")).toBeEnabled();
  await page.unroute("**/resources/geo-samples/options/sel_state**");
});

test("the filter panel cascades a reset through dependent filter selects", async ({ page }) => {
  await login(page);
  await page.getByTestId("nav-geo-samples").click();
  await expect(page.getByTestId("grid-table")).toBeVisible({ timeout: 15000 });
  await page.getByTestId("grid-filters").click();

  const country = page.locator('.fk-filter[data-filter="sel_country"] select');
  const state = page.locator('.fk-filter[data-filter="sel_state"] select');
  const city = page.locator('.fk-filter[data-filter="sel_city"] select');

  await expect(country.locator('option[value="us"]')).toHaveCount(1, { timeout: 15000 });
  await country.selectOption("us");
  await expect(state.locator('option[value="ca"]')).toHaveCount(1, { timeout: 15000 });
  await state.selectOption("ca");
  await expect(city.locator('option[value="la"]')).toHaveCount(1, { timeout: 15000 });
  await city.selectOption("la");

  await country.selectOption("br");
  await expect(city).toHaveValue("", { timeout: 15000 });
  await expect(city.locator('option[value="la"]')).toHaveCount(0, { timeout: 15000 });
  await expect(state.locator('option[value="sp"]')).toHaveCount(1, { timeout: 15000 });
});

test("manages a related category (add, edit, delete) from the product form without leaving it", async ({ page }) => {
  await login(page);
  await page.goto("/admin/products/new");
  await expect(page.getByTestId("form")).toBeVisible();

  const label = "Rel " + Date.now();
  const select = page.getByTestId("field-category_id");

  // ADD: the + icon opens the category form in a modal
  await page.getByTestId("related-add-category_id").click();
  let modal = page.getByTestId("related-modal");
  await expect(modal).toBeVisible();
  await modal.getByTestId("field-name").fill(label);
  await modal.getByTestId("field-is_active").check();
  await modal.getByTestId("form-save").click();
  await expect(modal).toBeHidden();
  await expect(select.locator("option:checked")).toHaveText(label);
  await expect(page.getByTestId("related-edit-category_id")).toBeEnabled();

  // EDIT: the pencil opens the selected category prefilled, and the option label updates on save
  await page.getByTestId("related-edit-category_id").click();
  modal = page.getByTestId("related-modal");
  await expect(modal.getByTestId("field-name")).toHaveValue(label);
  await modal.getByTestId("field-name").fill(label + " edited");
  await modal.getByTestId("form-save").click();
  await expect(modal).toBeHidden();
  await expect(select.locator("option:checked")).toHaveText(label + " edited");

  const categoryId = await select.inputValue();

  // DELETE: the trash removes it behind a confirmation, clears the selection AND drops the option from the list
  await page.getByTestId("related-delete-category_id").click();
  await page.getByTestId("confirm-accept").click();
  await expect(select).toHaveValue("");
  await expect(page.getByTestId("related-edit-category_id")).toBeDisabled();
  await expect(select.locator(`option[value="${categoryId}"]`)).toHaveCount(0);
});

test("deleting a dependent (subitem) related record drops it from that select too", async ({ page }) => {
  await login(page);
  await page.goto("/admin/products/new");
  await expect(page.getByTestId("form")).toBeVisible();

  const category = page.getByTestId("field-category_id");
  const subcategory = page.getByTestId("field-subcategory_id");

  await expect(category.locator("option")).not.toHaveCount(1, { timeout: 10000 });
  await category.selectOption({ index: 1 });
  const categoryValue = await category.inputValue();

  // add a fresh subcategory under the selected category via its + modal
  const subLabel = "Sub " + Date.now();
  await page.getByTestId("related-add-subcategory_id").click();
  const modal = page.getByTestId("related-modal");
  await expect(modal).toBeVisible();
  await modal.getByTestId("field-name").first().fill(subLabel);
  await modal.getByTestId("field-category_id").selectOption(categoryValue);
  await modal.getByTestId("form-save").click();
  await expect(modal).toBeHidden();
  await expect(subcategory.locator("option:checked")).toHaveText(subLabel);
  const subId = await subcategory.inputValue();

  // delete it via its own trash icon: value cleared AND option removed from the list
  await page.getByTestId("related-delete-subcategory_id").click();
  await page.getByTestId("confirm-accept").click();
  await expect(subcategory).toHaveValue("");
  await expect(subcategory.locator(`option[value="${subId}"]`)).toHaveCount(0);
});

test("the related add modal validates and shows field errors inside itself", async ({ page }) => {
  await login(page);
  await page.goto("/admin/products/new");
  await page.getByTestId("related-add-category_id").click();
  const modal = page.getByTestId("related-modal");
  await expect(modal).toBeVisible();

  await modal.getByTestId("form-save").click();
  await expect(modal.locator('[data-error="name"]')).not.toBeEmpty();
  await expect(modal).toBeVisible();
});

test("the related widget also works on a lookup field", async ({ page }) => {
  await login(page);
  await page.goto("/admin/showcase/new");
  await expect(page.getByTestId("form")).toBeVisible();

  const label = "Look " + Date.now();
  const lookup = page.locator('.fk-field[data-field="category_id"]');

  await page.getByTestId("related-add-category_id").click();
  const modal = page.getByTestId("related-modal");
  await expect(modal).toBeVisible();
  await modal.getByTestId("field-name").fill(label);
  await modal.getByTestId("field-is_active").check();
  await modal.getByTestId("form-save").click();
  await expect(modal).toBeHidden();
  await expect(lookup.locator('input[type=text]')).toHaveValue(label);

  // clean up the created category through the trash icon
  await page.getByTestId("related-delete-category_id").click();
  await page.getByTestId("confirm-accept").click();
  await expect(lookup.locator('input[type=text]')).toHaveValue("");
});

test("an inline validation error targets only the offending row, not every row", async ({ page }) => {
  await login(page);
  await page.goto("/admin/categories/new");
  await expect(page.getByTestId("form")).toBeVisible();
  await page.getByTestId("field-name").first().fill("Inline err " + Date.now());

  await page.getByTestId("inline-add-subcategories").click();
  await page.getByTestId("inline-add-subcategories").click();
  const rows = page.getByTestId("inline-row-subcategories");
  await rows.nth(0).getByTestId("field-name").fill("Filled row");
  // row 1 name left empty on purpose

  await page.getByTestId("form-save").click();

  // only the empty second row shows the required error; the filled first row stays clean
  await expect(rows.nth(1).locator('[data-error="name"]')).not.toBeEmpty();
  await expect(rows.nth(0).locator('[data-error="name"]')).toBeEmpty();
});

test("adding a related parent value resets its dependent child, and delete clears the select", async ({ page }) => {
  await login(page);
  await page.goto("/admin/products/new");
  await expect(page.getByTestId("form")).toBeVisible();

  const category = page.getByTestId("field-category_id");
  const subcategory = page.getByTestId("field-subcategory_id");

  // pick an existing category and one of its subcategories
  await expect(category.locator("option")).not.toHaveCount(1, { timeout: 10000 });
  await category.selectOption({ index: 1 });
  await expect(subcategory.locator("option")).not.toHaveCount(1, { timeout: 10000 });
  await subcategory.selectOption({ index: 1 });
  await expect(subcategory).not.toHaveValue("");

  // add a brand-new category via the + modal
  const label = "Cascade " + Date.now();
  await page.getByTestId("related-add-category_id").click();
  const modal = page.getByTestId("related-modal");
  await modal.getByTestId("field-name").first().fill(label);
  await modal.getByTestId("field-is_active").check();
  await modal.getByTestId("form-save").click();
  await expect(modal).toBeHidden();

  // the new category is selected AND the dependent subcategory reset (the new category has none)
  await expect(category.locator("option:checked")).toHaveText(label);
  await expect(subcategory).toHaveValue("");

  // delete the created category (cleanup) — the select clears
  await page.getByTestId("related-delete-category_id").click();
  await page.getByTestId("confirm-accept").click();
  await expect(category).toHaveValue("");
});

test("a product cover image uploads and its thumbnail renders in the grid", async ({ page }) => {
  await login(page);
  await page.getByTestId("nav-products").click();
  await page.getByTestId("grid-new").click();

  const stamp = Date.now();
  await page.getByTestId("field-name").fill("Cover " + stamp);
  await page.getByTestId("field-sku").fill("SKU-" + stamp);
  await page.getByTestId("field-price").fill("9.99");

  await page.getByTestId("field-image_url").locator('input[type=file]').setInputFiles({ name: "cover.png", mimeType: "image/png", buffer: PNG_1PX });
  await expect(page.getByTestId("field-image_url").locator('input[type=hidden]')).not.toHaveValue("");

  await page.getByTestId("form-save").click();
  await expect(page.getByTestId("toast-success")).toBeVisible();

  // the newest product is first (default -id sort); its cover cell renders an <img>
  await expect(page.locator('[data-testid^="cell-image_url-"]').first().locator("img")).toBeVisible();
});

test("editing a related record's inline children refreshes the dependent sub-select", async ({ page }) => {
  await login(page);
  await page.goto("/admin/products/new");
  await expect(page.getByTestId("form")).toBeVisible();

  const category = page.getByTestId("field-category_id");
  const subcategory = page.getByTestId("field-subcategory_id");
  const label = "RefCat " + Date.now();
  const subLabel = "RefSub " + Date.now();

  // add a fresh category (starts with no subcategories)
  await page.getByTestId("related-add-category_id").click();
  let modal = page.getByTestId("related-modal");
  await modal.getByTestId("field-name").first().fill(label);
  await modal.getByTestId("field-is_active").check();
  await modal.getByTestId("form-save").click();
  await expect(modal).toBeHidden();
  await expect(category.locator("option:checked")).toHaveText(label);
  await expect(subcategory.locator("option")).toHaveCount(1);

  // EDIT the category and add a subcategory in the modal's inline
  await page.getByTestId("related-edit-category_id").click();
  modal = page.getByTestId("related-modal");
  await modal.getByTestId("inline-add-subcategories").click();
  await modal.getByTestId("inline-row-subcategories").getByTestId("field-name").fill(subLabel);
  await modal.getByTestId("form-save").click();
  await expect(modal).toBeHidden();

  // the dependent subcategory select refreshed and now offers the new subcategory
  await expect(subcategory.locator("option", { hasText: subLabel })).toHaveCount(1);

  // cleanup: delete the category (cascades to the subcategory)
  await page.getByTestId("related-delete-category_id").click();
  await page.getByTestId("confirm-accept").click();
});
