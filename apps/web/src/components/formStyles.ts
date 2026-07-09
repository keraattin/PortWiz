// Shared control styling so form fields look identical everywhere.
// `controlClass` is the base input/select style; `inputClass` adds full width
// for the add/edit form controls.
export const controlClass =
  "rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 outline-none focus:border-emerald-500";

export const inputClass = `w-full ${controlClass}`;
