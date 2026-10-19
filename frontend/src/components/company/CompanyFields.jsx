import { useTranslation } from "react-i18next";

import { Input, Label, Select, Textarea } from "../ui/Field";
import { TagInput } from "../TagInput";

const BUSINESS_TYPES = [
  "proprietorship",
  "partnership",
  "llp",
  "private_limited",
  "public_limited",
  "other",
];

export function CompanyBasicsFields({ form, onChange, errors = {} }) {
  const { t } = useTranslation();
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <div className="sm:col-span-2">
        <Label htmlFor="name">{t("auth.companyName")} *</Label>
        <Input
          id="name"
          value={form.name}
          onChange={(event) => onChange("name", event.target.value)}
          invalid={Boolean(errors.name)}
        />
        {errors.name ? <p className="mt-1.5 text-xs text-red-600">{errors.name}</p> : null}
      </div>

      <div>
        <Label htmlFor="legal_name">{t("company.legalName")}</Label>
        <Input
          id="legal_name"
          value={form.legal_name}
          onChange={(event) => onChange("legal_name", event.target.value)}
          placeholder="Asha Infrastructure Private Limited"
        />
      </div>

      <div>
        <Label htmlFor="business_type">{t("company.businessType")}</Label>
        <Select
          id="business_type"
          value={form.business_type}
          onChange={(event) => onChange("business_type", event.target.value)}
        >
          <option value="">{t("onboarding.selectType")}</option>
          {BUSINESS_TYPES.map((type) => (
            <option key={type} value={type}>
              {t(`onboarding.businessTypes.${type}`)}
            </option>
          ))}
        </Select>
      </div>

      <div className="sm:col-span-2">
        <Label htmlFor="description">{t("company.description")}</Label>
        <Textarea
          id="description"
          rows={3}
          value={form.description}
          onChange={(event) => onChange("description", event.target.value)}
          placeholder={t("onboarding.descriptionPlaceholder")}
        />
      </div>

      <div>
        <Label htmlFor="established_year">{t("company.establishedYear")}</Label>
        <Input
          id="established_year"
          type="number"
          min="1900"
          max="2100"
          value={form.established_year}
          onChange={(event) => onChange("established_year", event.target.value)}
          placeholder="2011"
        />
      </div>

      <div>
        <Label htmlFor="employee_count">{t("company.employeeCount")}</Label>
        <Input
          id="employee_count"
          type="number"
          min="0"
          value={form.employee_count}
          onChange={(event) => onChange("employee_count", event.target.value)}
          placeholder="240"
        />
      </div>

      <div>
        <Label htmlFor="annual_turnover">{t("company.annualTurnover")}</Label>
        <Input
          id="annual_turnover"
          type="number"
          min="0"
          step="0.01"
          value={form.annual_turnover}
          onChange={(event) => onChange("annual_turnover", event.target.value)}
          placeholder="125000000"
        />
      </div>

      <div>
        <Label htmlFor="turnover_currency">{t("company.currency")}</Label>
        <Select
          id="turnover_currency"
          value={form.turnover_currency}
          onChange={(event) => onChange("turnover_currency", event.target.value)}
        >
          <option value="INR">INR</option>
          <option value="USD">USD</option>
          <option value="EUR">EUR</option>
        </Select>
      </div>
    </div>
  );
}

export function CompanyCapabilityFields({ form, onChange }) {
  const { t } = useTranslation();
  return (
    <div className="space-y-5">
      <div>
        <Label>{t("company.products")}</Label>
        <TagInput
          value={form.products_services}
          onChange={(value) => onChange("products_services", value)}
          placeholder={t("onboarding.productsPlaceholder")}
        />
      </div>
      <div className="grid gap-5 sm:grid-cols-2">
        <div>
          <Label>{t("company.sectors")}</Label>
          <TagInput
            value={form.sectors}
            onChange={(value) => onChange("sectors", value)}
            placeholder={t("onboarding.sectorsPlaceholder")}
          />
        </div>
        <div>
          <Label>{t("company.regions")}</Label>
          <TagInput
            value={form.regions}
            onChange={(value) => onChange("regions", value)}
            placeholder={t("onboarding.regionsPlaceholder")}
          />
        </div>
      </div>
      <div>
        <Label>{t("company.certifications")}</Label>
        <TagInput
          value={form.certifications}
          onChange={(value) => onChange("certifications", value)}
          placeholder={t("onboarding.certificationsPlaceholder")}
        />
      </div>
    </div>
  );
}

export function CompanyPreferenceFields({ form, onChangePreference }) {
  const { t } = useTranslation();
  return (
    <div className="space-y-5">
      <div className="grid gap-5 sm:grid-cols-2">
        <div>
          <Label>{t("company.sectors")}</Label>
          <TagInput
            value={form.preferences.sectors}
            onChange={(value) => onChangePreference("sectors", value)}
            placeholder={t("onboarding.sectorsPlaceholder")}
          />
        </div>
        <div>
          <Label>{t("company.regions")}</Label>
          <TagInput
            value={form.preferences.regions}
            onChange={(value) => onChangePreference("regions", value)}
            placeholder={t("onboarding.regionsPlaceholder")}
          />
        </div>
      </div>
      <div>
        <Label>{t("company.keywords")}</Label>
        <TagInput
          value={form.preferences.keywords}
          onChange={(value) => onChangePreference("keywords", value)}
          placeholder={t("onboarding.keywordsPlaceholder")}
        />
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <Label htmlFor="min_value">{t("company.minValue")}</Label>
          <Input
            id="min_value"
            type="number"
            min="0"
            value={form.preferences.min_value}
            onChange={(event) => onChangePreference("min_value", event.target.value)}
            placeholder="1000000"
          />
        </div>
        <div>
          <Label htmlFor="max_value">{t("company.maxValue")}</Label>
          <Input
            id="max_value"
            type="number"
            min="0"
            value={form.preferences.max_value}
            onChange={(event) => onChangePreference("max_value", event.target.value)}
            placeholder="500000000"
          />
        </div>
      </div>
    </div>
  );
}
