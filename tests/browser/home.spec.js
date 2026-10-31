import { test, expect } from "@playwright/test";
test("React home: imagery, commands, overload recovery, rules and mobile", async ({
  page,
  request,
}) => {
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await request.post('/api/demo/reset', {data:{}});
  await page.addInitScript(() => sessionStorage.setItem("guardian-demo-entered", "1"));
  await page.goto("/web/");
  await expect(
    page.getByRole("button", { name: "Настроить Умная розетка", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".product-image img")).toHaveCount(15);
  for (const img of await page.locator(".product-image img").all())
    expect(
      await img.evaluate((e) => e.complete && e.naturalWidth > 0),
    ).toBeTruthy();
  await page
    .getByRole("switch", { name: "Включить Основной свет", exact: true })
    .click();
  await expect(
    page.getByRole("switch", { name: "Выключить Основной свет", exact: true }),
  ).toHaveAttribute("aria-checked", "true");
  await page.screenshot({
    path: "/tmp/guardian-react-desktop.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Настройки и эксперименты" }).click();
  await page.getByRole("button", { name: /Перегрузка розетки/ }).click();
  await expect(page.locator(".alarm-banner")).toBeVisible();
  await page.locator(".alarm-banner").click();
  const device = page.getByRole("dialog", {
    name: "Умная розетка",
    exact: true,
  });
  const load = device
    .locator("form")
    .filter({ has: page.locator('label[for="signal-load_w"]') });
  await load.getByRole("spinbutton").fill("900");
  await load.getByRole('spinbutton').press('Tab');
  await expect.poll(async()=>(await (await request.get('/api/state')).json()).devices.smart_plug_1.load_w).toBe(900);
  await device
    .getByRole("button", { name: "Сбросить защиту", exact: true })
    .click();
  await expect(page.locator(".alarm-banner")).not.toBeVisible();
  await device.getByRole("button", { name: "Закрыть" }).click();
  await page
    .getByRole("switch", { name: "Включить Умная розетка", exact: true })
    .click();
  await expect
    .poll(
      async () =>
        (await (await request.get("/api/state")).json()).devices.smart_plug_1
          .power_w,
    )
    .toBe(900);
  await page.getByRole("link", { name: "Сценарии", exact: true }).click();
  await page
    .getByRole("button", { name: "Новый сценарий", exact: true })
    .click();
  const editor = page.getByRole("dialog", {
    name: "Новый сценарий",
    exact: true,
  });
  await editor
    .getByLabel("Название сценария", { exact: true })
    .fill("Browser test rule");
  await editor.getByRole("button", { name: "Проверить на 30 секунд" }).click();
  await expect(editor.locator(".builder-notice")).toContainText(
    "Состояние дома не изменилось",
  );
  await editor.getByRole("button", { name: "Создать сценарий", exact:true }).click();
  await expect(
    page.getByRole("heading", { name: "Browser test rule" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Мой дом", exact: true }).click();
  await page.getByRole("radio", { name: "Кухня", exact: true }).click();
  await expect(page.locator(".product-image")).toHaveCount(6);
  await page.getByRole("radio", { name: "Все", exact: true }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator('.hero-status').getByText('Защита активна', {exact:true})).toBeVisible();
  await page.screenshot({
    path: "/tmp/guardian-react-phone.png",
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.goto("/web/?mode=tv");
  await expect(page.locator("body")).toHaveAttribute("data-mode", "tv");
  await page.keyboard.press("ArrowDown");
  expect(await page.evaluate(() => document.activeElement.tagName)).not.toBe(
    "BODY",
  );
  expect(errors).toEqual([]);
});
