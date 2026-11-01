/** Local configuration can advance onboarding review, never prove a live call. */
export function isVoicemailConfigurationSaved(status) {
  return Boolean(
    status &&
    status.configuration_complete === true &&
    typeof status.phone_number === "string" &&
    /^\+1[2-9][0-9]{2}[2-9][0-9]{6}$/.test(status.phone_number)
  );
}
