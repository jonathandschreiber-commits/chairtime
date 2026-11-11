import { redirectLegacyAdmin } from "../../../lib/redirect-legacy-admin.js";

export default function Page() {
  return redirectLegacyAdmin("/today");
}
