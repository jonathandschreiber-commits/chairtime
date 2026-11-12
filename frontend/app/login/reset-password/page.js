import PasswordRecoveryForm from "../PasswordRecoveryForm";

export const metadata = {
  title: "Reset password | DayTello",
  referrer: "no-referrer",
  robots: { index: false },
};

export default function ResetPasswordPage() {
  return <PasswordRecoveryForm reset />;
}
