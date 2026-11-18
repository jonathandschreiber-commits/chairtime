"use client";

import { useRef } from "react";

export default function SavePageShortcut({ pageName }) {
  const dialog = useRef(null);
  return (
    <>
      <button
        type="button"
        className="text-sm font-semibold text-indigo-700 underline underline-offset-2"
        onClick={() => dialog.current.showModal()}
      >
        Save this page to your device
      </button>

      <dialog
        ref={dialog}
        aria-label={`Save ${pageName} to your device`}
        className="m-auto w-[calc(100%-2rem)] max-w-md rounded-2xl border border-slate-200 p-6 shadow-xl backdrop:bg-slate-900/50"
      >
        <h2 className="text-xl font-bold text-slate-900">Save {pageName}</h2>
        <dl className="my-4 space-y-3 text-sm text-slate-700">
          <div>
            <dt className="font-semibold">iPhone · Safari</dt>
            <dd>Tap Share → Add to Home Screen → Add.</dd>
          </div>
          <div>
            <dt className="font-semibold">Android · Chrome</dt>
            <dd>Open the three-dot menu → Add to Home screen or Install app.</dd>
          </div>
          <div>
            <dt className="font-semibold">Computer · Chrome or Edge</dt>
            <dd>Open the three-dot menu and look for Install app or Create shortcut.</dd>
          </div>
        </dl>
        <form method="dialog">
          <button className="rounded-lg bg-indigo-700 px-4 py-2 text-sm font-semibold text-white" autoFocus>
            Done
          </button>
        </form>
      </dialog>
    </>
  );
}
