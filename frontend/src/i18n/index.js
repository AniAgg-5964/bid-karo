import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import en from "./locales/en.json";
import hi from "./locales/hi.json";

export const SUPPORTED_LANGUAGES = [
  { code: "en", label: "English", short: "EN" },
  { code: "hi", label: "हिन्दी", short: "HI" },
];

const stored = localStorage.getItem("bidkaro_lang");
const initial = SUPPORTED_LANGUAGES.some((item) => item.code === stored) ? stored : "en";

i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    hi: { translation: hi },
  },
  lng: initial,
  fallbackLng: "en",
  supportedLngs: ["en", "hi"],
  interpolation: { escapeValue: false },
  returnNull: false,
});

document.documentElement.lang = initial;

export function currentLocale() {
  return i18n.language === "hi" ? "hi-IN" : "en-IN";
}

export async function changeLanguage(code) {
  if (!SUPPORTED_LANGUAGES.some((item) => item.code === code)) return;
  localStorage.setItem("bidkaro_lang", code);
  document.documentElement.lang = code;
  await i18n.changeLanguage(code);
}

export default i18n;
