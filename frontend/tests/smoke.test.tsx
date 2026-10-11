import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import Page from "../app/page";
import { withProviders } from "./with-providers";

describe("frontend smoke", () => {
  it("page shell menyapa dengan judul MealChain Guardian", () => {
    const html = renderToStaticMarkup(withProviders(<Page />));
    expect(html).toContain("MealChain Guardian");
  });
});
