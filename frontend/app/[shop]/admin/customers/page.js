import { getBackendUrl } from "../../../../lib/backend-url.js";
import CustomersPage from "./CustomersPage";

export default function Page() {
  return <CustomersPage apiBase={getBackendUrl()} />;
}
