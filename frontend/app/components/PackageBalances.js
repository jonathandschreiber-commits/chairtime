const purchaseDate = new Intl.DateTimeFormat("en-US", {
  month: "numeric",
  day: "numeric",
  year: "2-digit",
});

export default function PackageBalances({ payment }) {
  if (!payment?.package_balances?.length && !payment?.package_sessions_remaining) return null;

  return (
    <div className="text-sm text-gray-700">
      {payment.package_balances?.length ? payment.package_balances.map(balance => (
        <p key={balance.id}>
          {balance.expired ? "Expired package" : balance.sessions_remaining ? "Eligible package sessions remaining" : "Used up package"}: {balance.sessions_remaining} from purchase {purchaseDate.format(new Date(balance.purchased_at))}
          {balance.expires_at && <> · {balance.expired ? "Expired" : "Expires"} {purchaseDate.format(new Date(balance.expiration_date ? balance.expiration_date + "T12:00:00" : balance.expires_at))}</>}
        </p>
      )) : <p>Eligible package sessions remaining: {payment.package_sessions_remaining}</p>}
    </div>
  );
}
