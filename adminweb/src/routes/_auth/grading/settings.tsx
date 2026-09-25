import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  useGradingSettings,
  useUpdateGradingSettings,
} from "@/query/grading";

export const Route = createFileRoute("/_auth/grading/settings")({
  component: SettingsPage,
});

function SettingsPage() {
  const q = useGradingSettings();
  const upd = useUpdateGradingSettings();

  const [d1, setD1] = useState("");
  const [d2, setD2] = useState("");
  const [sig1, setSig1] = useState<File | null>(null);
  const [sig2, setSig2] = useState<File | null>(null);
  const [summaryTpl, setSummaryTpl] = useState<File | null>(null);
  const [certTpl, setCertTpl] = useState<File | null>(null);

  useEffect(() => {
    if (q.data) {
      setD1(q.data.director_1_name || "");
      setD2(q.data.director_2_name || "");
    }
  }, [q.data]);

  if (q.isPending) return <p className="text-sm text-muted-foreground">Loading…</p>;
  if (q.isError || !q.data) return <p className="text-destructive">Failed to load settings.</p>;

  const onSave = () => {
    const hasFile = sig1 || sig2 || summaryTpl || certTpl;
    let body: FormData | Record<string, unknown>;
    if (hasFile) {
      const fd = new FormData();
      fd.append("director_1_name", d1);
      fd.append("director_2_name", d2);
      if (sig1) fd.append("director_1_signature", sig1);
      if (sig2) fd.append("director_2_signature", sig2);
      if (summaryTpl) fd.append("marks_summary_template", summaryTpl);
      if (certTpl) fd.append("certificate_template", certTpl);
      body = fd;
    } else {
      body = { director_1_name: d1, director_2_name: d2 };
    }
    upd.mutate(body as never, {
      onSuccess: () => {
        toast.success("Settings saved");
        setSig1(null); setSig2(null); setSummaryTpl(null); setCertTpl(null);
      },
      onError: (e: unknown) => toast.error((e as Error).message),
    });
  };

  return (
    <div className="max-w-2xl space-y-5">
      <Section title="Directors">
        <Field label="Director 1 name">
          <Input value={d1} onChange={(e) => setD1(e.target.value)} placeholder="e.g. Prof. Alice Adams" />
        </Field>
        <Field label="Director 1 signature">
          <Input type="file" accept="image/*" onChange={(e) => setSig1(e.target.files?.[0] ?? null)} />
          {q.data.director_1_signature ? <FileHint value={q.data.director_1_signature} /> : null}
        </Field>
        <Field label="Director 2 name">
          <Input value={d2} onChange={(e) => setD2(e.target.value)} placeholder="e.g. Dr. Bob Brown" />
        </Field>
        <Field label="Director 2 signature">
          <Input type="file" accept="image/*" onChange={(e) => setSig2(e.target.files?.[0] ?? null)} />
          {q.data.director_2_signature ? <FileHint value={q.data.director_2_signature} /> : null}
        </Field>
      </Section>

      <Section title="Docx templates">
        <p className="text-xs text-muted-foreground">
          Uploaded templates override the built-in fallbacks. Use Jinja-style
          <code> {"{{ variable }}"} </code> markers. See docx.py for the
          expected context keys.
        </p>
        <Field label="Marks summary template (.docx)">
          <Input type="file" accept=".docx" onChange={(e) => setSummaryTpl(e.target.files?.[0] ?? null)} />
          {q.data.marks_summary_template ? <FileHint value={q.data.marks_summary_template} /> : null}
        </Field>
        <Field label="Certificate template (.docx)">
          <Input type="file" accept=".docx" onChange={(e) => setCertTpl(e.target.files?.[0] ?? null)} />
          {q.data.certificate_template ? <FileHint value={q.data.certificate_template} /> : null}
        </Field>
      </Section>

      <div>
        <Button onClick={onSave} disabled={upd.isPending}>
          {upd.isPending ? "Saving…" : "Save"}
        </Button>
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3 rounded-md border p-4">
      <h3 className="font-semibold">{title}</h3>
      <div className="space-y-3">{children}</div>
    </section>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="grid gap-1 text-sm">
      <span className="text-muted-foreground">{label}</span>
      {children}
    </label>
  );
}

function FileHint({ value }: { value: string }) {
  return (
    <span className="text-xs text-muted-foreground">
      Current: <code className="break-all">{value}</code>
    </span>
  );
}
