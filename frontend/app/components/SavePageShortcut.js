"use client";

import { ShopMessage } from "./ShopLanguage";

import { useRef, useState } from "react";

const instructions = {
  iPhone: [
    "Open this page in Safari.",
    "Tap Share, then Add to Home Screen.",
    "If you see Open as Web App, turn it on. Tap Add.",
  ],
  Android: [
    "Open this page in Chrome.",
    "Tap the three-dot menu, then Install and create shortcut or Add to Home screen.",
    "Choose Install or Add and follow the prompts.",
  ],
  Windows: [
    "Open this page in Chrome or Edge.",
    "In Chrome, open the three-dot menu → Cast, save, and share → Install page as app.",
    "In Edge, open the three-dot menu → More tools → Apps → Install this site as an app.",
  ],
};

export default function SavePageShortcut({ pageName }) {
  const dialog = useRef(null);
  const [device, setDevice] = useState("iPhone");

  function openInstructions(nextDevice) {
    setDevice(nextDevice);
    dialog.current.showModal();
  }

  return (
    <div>
      <p className="text-sm font-semibold text-slate-700"><ShopMessage>Save this page to your phone or computer</ShopMessage></p>
      <div className="mt-1 flex flex-wrap gap-x-4 gap-y-2" aria-label="Device instructions">
        {Object.keys(instructions).map((name) => (
          <button
            key={name}
            type="button"
            className="text-sm font-semibold text-indigo-700 underline underline-offset-2"
            onClick={() => openInstructions(name)}
          >
            {name}
          </button>
        ))}
      </div>

      <dialog
        ref={dialog}
        aria-label={`Save ${pageName} on ${device}`}
        className="m-auto w-11/12 max-w-md rounded-2xl border border-slate-200 p-6 shadow-xl backdrop:bg-slate-900/50"
      >
        <h2 className="text-xl font-bold text-slate-900">Save {pageName} on {device}</h2>
        <ol className="my-4 list-decimal space-y-2 pl-5 text-sm text-slate-700">
          {instructions[device].map((step) => <li key={step}>{step}</li>)}
        </ol>
        <form method="dialog">
          <button className="rounded-lg bg-indigo-700 px-4 py-2 text-sm font-semibold text-white" autoFocus>
            Done
          </button>
        </form>
      </dialog>
    </div>
  );
}
