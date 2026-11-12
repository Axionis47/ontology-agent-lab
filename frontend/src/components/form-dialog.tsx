"use client";
import { useRef, useState, type FormEvent, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

export function FormDialog({
  trigger,
  title,
  description,
  submitLabel,
  busyLabel = "Saving...",
  className,
  onOpen,
  onSubmit,
  children,
}: {
  trigger: ReactNode;
  title: string;
  description: string;
  submitLabel: string;
  busyLabel?: string;
  className?: string;
  onOpen?: () => void;
  onSubmit: (data: FormData) => Promise<void>;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const submitting = useRef(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting.current) return;
    submitting.current = true;
    const data = new FormData(event.currentTarget);
    setBusy(true);
    setError("");
    try {
      await onSubmit(data);
      setOpen(false);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      submitting.current = false;
      setBusy(false);
    }
  }
  return (
    <Dialog
      open={open}
      onOpenChange={(value) => {
        if (!busy) {
          setOpen(value);
          setError("");
          if (value) onOpen?.();
        }
      }}
    >
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className={className}>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-5">
          <fieldset disabled={busy} className="min-w-0 space-y-5">
            {children}
          </fieldset>
          {error && (
            <p role="alert" className="error-text">
              {error}
            </p>
          )}
          <div className="sticky bottom-0 z-10 flex justify-end bg-popover py-2">
            <Button disabled={busy} type="submit">
              {busy ? busyLabel : submitLabel}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
