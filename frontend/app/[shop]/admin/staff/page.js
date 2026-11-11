import { getBackendUrl } from "../../../../lib/backend-url.js";
import StaffServicesPage from "./StaffServicesPage";

export default function Page() {
  return <StaffServicesPage apiBase={getBackendUrl()} />;
}
