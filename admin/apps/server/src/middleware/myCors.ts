import { cors } from "hono/cors";

const myCors = cors({
  origin: [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://wordypanda.com",
    "https://www.wordypanda.com",
    "http://192.168.0.37:5173",
  ],
  allowHeaders: ["Content-Type", "Authorization", "x-timezone"],
  allowMethods: ["POST", "GET", "OPTIONS", "PUT", "DELETE"],
  exposeHeaders: ["Content-Length"],
  maxAge: 600,
  credentials: true,
});

export default myCors;
