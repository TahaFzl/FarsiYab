"use client";

import { useRef, useState, type FormEvent } from "react";

import { browserApi } from "@/lib/api";

type Reason = "not_iranian" | "closed" | "wrong_info" | "remove_request";

interface Text {
  title: string;
  reason: string;
  reasons: Record<Reason, string>;
  message: string;
  email: string;
  send: string;
  cancel: string;
  sent: string;
  failed: string;
}

export function ReportButton({
  businessId,
  name,
  text,
  buttonLabel,
}: {
  businessId: string;
  name: string;
  text: Text;
  buttonLabel: string;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [reason, setReason] = useState<Reason>("not_iranian");
  const [message, setMessage] = useState("");
  const [email, setEmail] = useState("");
  const [state, setState] = useState<"idle" | "sending" | "sent" | "failed">("idle");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setState("sending");
    try {
      const response = await fetch(browserApi.report(businessId), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason, message: message || null, contact_email: email || null }),
      });
      setState(response.ok ? "sent" : "failed");
    } catch {
      setState("failed");
    }
  }

  const input =
    "w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:border-primary focus:outline-none";

  return (
    <>
      <button
        type="button"
        onClick={() => {
          setState("idle");
          dialog.current?.showModal();
        }}
        className="text-muted underline-offset-2 hover:text-danger hover:underline"
      >
        {buttonLabel}
      </button>
      <dialog
        ref={dialog}
        className="m-auto w-[min(92vw,28rem)] rounded-2xl border border-border bg-surface p-0 text-foreground backdrop:bg-black/40"
      >
        {state === "sent" ? (
          <div className="space-y-4 p-6">
            <p>{text.sent}</p>
            <button type="button" onClick={() => dialog.current?.close()} className="text-primary">
              {text.cancel}
            </button>
          </div>
        ) : (
          <form onSubmit={submit} className="space-y-4 p-6">
            <h2 className="font-bold">{text.title.replace("{name}", name)}</h2>
            <fieldset className="space-y-2">
              <legend className="text-sm font-medium">{text.reason}</legend>
              {(Object.keys(text.reasons) as Reason[]).map((r) => (
                <label key={r} className="flex items-center gap-2 text-sm">
                  <input type="radio" name="reason" value={r} checked={reason === r} onChange={() => setReason(r)} />
                  {text.reasons[r]}
                </label>
              ))}
            </fieldset>
            <label className="block space-y-1 text-sm">
              <span>{text.message}</span>
              <textarea className={input} rows={3} maxLength={2000} value={message} onChange={(e) => setMessage(e.target.value)} />
            </label>
            <label className="block space-y-1 text-sm">
              <span>{text.email}</span>
              <input
                className={input}
                type="email"
                dir="ltr"
                required={reason === "remove_request"}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </label>
            {state === "failed" && <p className="text-sm text-danger">{text.failed}</p>}
            <div className="flex gap-3">
              <button
                type="submit"
                disabled={state === "sending"}
                className="rounded-lg bg-primary px-5 py-2 text-sm font-semibold text-white hover:bg-primary-strong disabled:opacity-60"
              >
                {text.send}
              </button>
              <button type="button" onClick={() => dialog.current?.close()} className="px-3 text-sm text-muted">
                {text.cancel}
              </button>
            </div>
          </form>
        )}
      </dialog>
    </>
  );
}
