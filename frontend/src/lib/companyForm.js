export const EMPTY_COMPANY_FORM = {
  name: "",
  legal_name: "",
  business_type: "",
  description: "",
  products_services: [],
  sectors: [],
  regions: [],
  certifications: [],
  annual_turnover: "",
  turnover_currency: "INR",
  employee_count: "",
  established_year: "",
  preferences: {
    sectors: [],
    regions: [],
    keywords: [],
    min_value: "",
    max_value: "",
  },
};

function valueOrEmpty(value) {
  return value === null || value === undefined ? "" : value;
}

export function companyToForm(company) {
  if (!company) return { ...EMPTY_COMPANY_FORM, preferences: { ...EMPTY_COMPANY_FORM.preferences } };
  const preferences = company.preferences || {};
  return {
    name: valueOrEmpty(company.name),
    legal_name: valueOrEmpty(company.legal_name),
    business_type: valueOrEmpty(company.business_type),
    description: valueOrEmpty(company.description),
    products_services: company.products_services || [],
    sectors: company.sectors || [],
    regions: company.regions || [],
    certifications: company.certifications || [],
    annual_turnover: valueOrEmpty(company.annual_turnover),
    turnover_currency: company.turnover_currency || "INR",
    employee_count: valueOrEmpty(company.employee_count),
    established_year: valueOrEmpty(company.established_year),
    preferences: {
      sectors: preferences.sectors || [],
      regions: preferences.regions || [],
      keywords: preferences.keywords || [],
      min_value: valueOrEmpty(preferences.min_value),
      max_value: valueOrEmpty(preferences.max_value),
    },
  };
}

function numberOrNull(value) {
  if (value === "" || value === null || value === undefined) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function formToPayload(form) {
  return {
    name: form.name?.trim(),
    legal_name: form.legal_name?.trim() || null,
    business_type: form.business_type || null,
    description: form.description?.trim() || null,
    products_services: form.products_services,
    sectors: form.sectors,
    regions: form.regions,
    certifications: form.certifications,
    annual_turnover: numberOrNull(form.annual_turnover),
    turnover_currency: (form.turnover_currency || "INR").toUpperCase(),
    employee_count: numberOrNull(form.employee_count),
    established_year: numberOrNull(form.established_year),
    preferences: {
      sectors: form.preferences.sectors,
      regions: form.preferences.regions,
      keywords: form.preferences.keywords,
      min_value: numberOrNull(form.preferences.min_value),
      max_value: numberOrNull(form.preferences.max_value),
    },
  };
}
