import { describe, expect, it } from "vitest";

import { companyToForm, formToPayload } from "./companyForm";

describe("company form mapping", () => {
  it("normalizes empty company state and preserves arrays", () => {
    const form = companyToForm(null);
    expect(form.name).toBe("");
    expect(form.preferences.sectors).toEqual([]);

    const mapped = companyToForm({
      name: "Asha Infra",
      legal_name: null,
      sectors: ["Infrastructure"],
      preferences: { sectors: ["Transport"], min_value: 1000 },
    });
    expect(mapped.legal_name).toBe("");
    expect(mapped.sectors).toEqual(["Infrastructure"]);
    expect(mapped.preferences.min_value).toBe(1000);
  });

  it("converts empty numbers to null and trims text", () => {
    const payload = formToPayload({
      name: "  Asha Infra  ",
      legal_name: "  Asha Infrastructure Pvt Ltd ",
      business_type: "",
      description: "",
      products_services: ["Roads"],
      sectors: [],
      regions: [],
      certifications: [],
      annual_turnover: "",
      turnover_currency: "inr",
      employee_count: "240",
      established_year: "",
      preferences: {
        sectors: ["Infrastructure"],
        regions: [],
        keywords: ["highway"],
        min_value: "",
        max_value: "500000",
      },
    });

    expect(payload.name).toBe("Asha Infra");
    expect(payload.legal_name).toBe("Asha Infrastructure Pvt Ltd");
    expect(payload.annual_turnover).toBeNull();
    expect(payload.employee_count).toBe(240);
    expect(payload.turnover_currency).toBe("INR");
    expect(payload.preferences.min_value).toBeNull();
    expect(payload.preferences.max_value).toBe(500000);
  });
});
