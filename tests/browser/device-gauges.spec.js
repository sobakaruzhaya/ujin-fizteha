import { test, expect } from "@playwright/test";

test("device settings save automatically without Apply or confirmation", async ({
  page,
  request,
}) => {
  await request.post("/api/demo/reset", { data: {} });
  await page.addInitScript(() =>
    sessionStorage.setItem("guardian-demo-entered", "1"),
  );
  await page.goto("/web/#home");
  await expect(page.locator(".device-card .device-gauge-control")).toHaveCount(
    0,
  );
  const light = page
    .locator(".device-card")
    .filter({
      has: page.getByRole("button", {
        name: "Настроить Основной свет",
        exact: true,
      }),
    });
  await light.getByRole("switch").click();
  await light
    .getByRole("button", { name: "Настроить Основной свет", exact: true })
    .click();
  let dialog = page.getByRole("dialog", { name: "Основной свет", exact: true });
  const brightness = dialog.getByRole("slider", { name: "Яркость света" });
  const lightSwitch = dialog.getByRole("switch", { name: "Свет", exact: true });
  await expect(lightSwitch).toHaveAttribute("aria-checked", "true");
  await expect(dialog.getByRole("combobox", { name: "Свет", exact: true })).toHaveCount(0);
  await lightSwitch.focus();
  await lightSwitch.press("Space");
  await expect.poll(async () => (await (await request.get("/api/state")).json()).devices.light_1.lamp).toBe(0);
  await expect(lightSwitch).toHaveAttribute("aria-checked", "false");
  await expect(brightness).toHaveAttribute("aria-disabled", "true");
  // A remote command while the modal is open must also update the switch.
  await request.post("/api/commands", { data: { device: "light_1", signal: "lamp", value: 1 } });
  await expect(lightSwitch).toHaveAttribute("aria-checked", "true");
  await expect(brightness).not.toHaveAttribute("aria-disabled", "true");
  await brightness.focus();
  await brightness.press("End");
  await brightness.press("ArrowDown");
  await expect
    .poll(
      async () =>
        (await (await request.get("/api/state")).json()).devices.light_1
          .brightness,
    )
    .toBe(99);
  await expect(
    dialog.getByRole("button", { name: "Применить", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("dialog", { name: "Подтвердите действие" }),
  ).toHaveCount(0);
  await dialog.getByRole("button", { name: "Закрыть", exact: true }).click();
  await page
    .getByRole("button", {
      name: "Настроить Приточная вентиляция",
      exact: true,
    })
    .click();
  dialog = page.getByRole("dialog", {
    name: "Приточная вентиляция",
    exact: true,
  });
  const speed = dialog.getByRole("slider", { name: "Скорость вентиляции" });
  await speed.focus();
  await speed.press("End");
  await speed.press("ArrowDown");
  await expect
    .poll(
      async () =>
        (await (await request.get("/api/state")).json()).devices.ventilation_1
          .fan_speed,
    )
    .toBe(5);
  expect(
    (await (await request.get("/api/state")).json()).devices.ventilation_1.mode,
  ).toBe(2);
  const target = dialog.locator("#signal-co2_target");
  await target.fill("950");
  await target.press("Tab");
  await expect
    .poll(
      async () =>
        (await (await request.get("/api/state")).json()).devices.ventilation_1
          .co2_target,
    )
    .toBe(950);
  await dialog.locator("#signal-mode").selectOption("0");
  await expect
    .poll(
      async () =>
        (await (await request.get("/api/state")).json()).devices.ventilation_1
          .mode,
    )
    .toBe(0);
  await expect(speed).toHaveAttribute("aria-disabled", "true");
  await dialog.getByRole("button", { name: "Закрыть", exact: true }).click();
  for (const width of [768, 390]) {
    await page.setViewportSize({ width, height: 844 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  }
  await page
    .getByRole("button", { name: "Настроить Основной свет", exact: true })
    .click();
  dialog = page.getByRole("dialog", { name: "Основной свет", exact: true });
  expect(await dialog.evaluate((e) => e.scrollWidth <= e.clientWidth)).toBe(
    true,
  );
});

test("automatic settings recover from a failed request", async ({
  page,
  request,
}) => {
  await request.post("/api/demo/reset", { data: {} });
  await page.addInitScript(() =>
    sessionStorage.setItem("guardian-demo-entered", "1"),
  );
  await page.goto("/web/#home");
  await page
    .getByRole("button", { name: "Настроить Умная розетка", exact: true })
    .click();
  const dialog = page.getByRole("dialog", {
    name: "Умная розетка",
    exact: true,
  });
  const input = dialog.locator("#signal-power_limit_w");
  const before = (await (await request.get("/api/state")).json()).devices
    .smart_plug_1.power_limit_w;
  await page.route("**/api/commands/preview", (route) =>
    route.fulfill({
      status: 400,
      contentType: "application/json",
      body: JSON.stringify({ error: "Проверка ошибки сохранения" }),
    }),
  );
  await input.fill("1800");
  await input.press("Tab");
  await expect(page.getByRole("alert")).toContainText(
    "Проверка ошибки сохранения",
  );
  await expect(input).toHaveValue(String(before));
  await page.unroute("**/api/commands/preview");
  await input.fill("1900");
  await input.press("Tab");
  await expect
    .poll(
      async () =>
        (await (await request.get("/api/state")).json()).devices.smart_plug_1
          .power_limit_w,
    )
    .toBe(1900);
});
