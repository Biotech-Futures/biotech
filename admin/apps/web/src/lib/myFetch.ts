import { buildUrl } from "@/util/url";
import axios from "axios";

export const myFetch = axios.create({
  baseURL: buildUrl(
    import.meta.env.VITE_PUBLIC_API_URL || "http://localhost:3003",
    "api",
    "v1",
  ),
  withCredentials: true,
});
