export const openHtmlPreviewPage = (html: string) => {
  const documentHtml = `<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Resource Preview</title>
    <style>
      body { margin: 0; padding: 24px; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; color: #111827; background: #f8fafc; }
      .wrap { max-width: 960px; margin: 0 auto; background: white; border: 1px solid #e5e7eb; border-radius: 12px; padding: 20px; box-shadow: 0 1px 2px rgba(0,0,0,.04); }
    </style>
  </head>
  <body>
    <div class="wrap">
      ${html || "<p>No content yet.</p>"}
    </div>
  </body>
</html>`;

  const blob = new Blob([documentHtml], { type: "text/html" });
  const url = URL.createObjectURL(blob);
  const win = window.open(url, "_blank");
  if (!win) {
    window.alert(
      "Preview tab was blocked. Please allow pop-ups for this site.",
    );
    return;
  }
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
};
