import { getBackendUrl } from "../../lib/backend-url";
import ShopBookingPage from "./ShopBookingPage";

export default function PublicBookingPage() {
  return <ShopBookingPage apiBase={getBackendUrl()} />;
}
