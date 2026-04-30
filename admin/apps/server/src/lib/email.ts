import "dotenv/config";
import nodemailer from "nodemailer";

type SendEmailInput = {
  to: string | string[];
  subject: string;
  text?: string;
  html?: string;
  from?: string;
};

function parseBoolean(value: string | undefined, defaultValue: boolean) {
  if (value === undefined) {
    return defaultValue;
  }

  return value.toLowerCase() === "true";
}

function parsePort(value: string | undefined, defaultPort: number) {
  if (!value) {
    return defaultPort;
  }

  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : defaultPort;
}

function createSmtpTransport() {
  const mailtrapToken = process.env.MAILTRAP_TOKEN;

  const host = process.env.EMAIL_HOST ?? "send.api.mailtrap.io";
  const port = parsePort(process.env.EMAIL_PORT, 2525);
  const useTls = parseBoolean(process.env.EMAIL_USE_TLS, true);
  const secure = port === 465;
  const user = process.env.EMAIL_HOST_USER ?? "api";
  const password = process.env.EMAIL_HOST_PASSWORD ?? mailtrapToken;

  if (!password) {
    throw new Error(
      "Missing SMTP credentials. Set EMAIL_HOST_PASSWORD or MAILTRAP_TOKEN.",
    );
  }

  return nodemailer.createTransport({
    host,
    port,
    secure,
    // requireTLS: useTls,
    auth: {
      user,
      pass: password,
    },
  });
}

export const emailTransporter = createSmtpTransport();

export async function sendEmail({
  to,
  subject,
  text,
  html,
  from,
}: SendEmailInput) {
  if (!text && !html) {
    throw new Error("Email payload must include text or html content.");
  }

  const fromAddress = from ?? process.env.EMAIL_HOST_USER;

  if (!fromAddress) {
    throw new Error("Missing sender. Provide `from` or set EMAIL_HOST_USER.");
  }

  return emailTransporter.sendMail({
    from: fromAddress,
    to,
    subject,
    text,
    html,
  });
}
