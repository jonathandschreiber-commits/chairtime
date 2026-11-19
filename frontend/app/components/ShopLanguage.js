"use client";

import { createContext, useContext, useSyncExternalStore } from "react";
import {
  DEFAULT_LANGUAGE,
  LANGUAGE_STORAGE_KEY,
  SHOP_LANGUAGES,
  normalizeShopLanguage,
  translateShopMessage,
} from "../../lib/shop-language.mjs";

const LanguageContext = createContext(DEFAULT_LANGUAGE);
const CHANGE_EVENT = "daytello-language-change";
let currentLanguage;

function subscribe(callback) {
  window.addEventListener("storage", callback);
  window.addEventListener(CHANGE_EVENT, callback);
  return () => {
    window.removeEventListener("storage", callback);
    window.removeEventListener(CHANGE_EVENT, callback);
  };
}

function getLanguage() {
  try {
    return normalizeShopLanguage(window.localStorage.getItem(LANGUAGE_STORAGE_KEY));
  } catch {
    return currentLanguage ?? DEFAULT_LANGUAGE;
  }
}

function setLanguage(value) {
  currentLanguage = normalizeShopLanguage(value);
  try {
    window.localStorage.setItem(LANGUAGE_STORAGE_KEY, currentLanguage);
  } catch {
    // The current page can still switch languages with storage disabled.
  }
  window.dispatchEvent(new Event(CHANGE_EVENT));
}

export function ShopLanguageRegion({ children }) {
  const language = useSyncExternalStore(subscribe, getLanguage, () => DEFAULT_LANGUAGE);

  return (
    <LanguageContext.Provider value={language}>
      <div>
        <div className="mx-auto flex max-w-6xl justify-end px-6 pt-3">
          <select
            translate="no"
            aria-label="Language / Idioma / Ngôn ngữ / 语言 / 언어 / ภาษา"
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900"
            value={language}
            onChange={(event) => setLanguage(event.target.value)}
          >
            {Object.entries(SHOP_LANGUAGES).map(([code, name]) => (
              <option key={code} value={code} lang={code}>{name}</option>
            ))}
          </select>
        </div>
        {children}
      </div>
    </LanguageContext.Provider>
  );
}

export function useShopLanguage() {
  return useContext(LanguageContext);
}

export function useShopMessages() {
  const language = useShopLanguage();
  return (message) => translateShopMessage(language, message);
}

export function ShopMessage({ children }) {
  const language = useContext(LanguageContext);
  const message = translateShopMessage(language, children);
  return language !== DEFAULT_LANGUAGE && message !== children
    ? <span lang={language} translate="no">{message}</span>
    : message;
}
