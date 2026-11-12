import { passwordRecoveryRequest } from "@/lib/password-recovery";

export async function POST(request) {
  return passwordRecoveryRequest(request, "forgot-password");
}
