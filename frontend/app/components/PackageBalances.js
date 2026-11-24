const purchaseDate = new Intl.DateTimeFormat("en-US", {
  month: "numeric",
  day: "numeric",
  year: "2-digit",
});

export default function PackageBalances({ payment }) {
  if (!payment?.package_balances?.length && !payment?.package_sessions_remaining) return null;

  return (
    <div className="mt-1 space-y-1 text-sm text-gray-700">
      {payment.package_balances?.length ? payment.package_balances.map(balance => (
        <details key={balance.id}>
          <summary className="cursor-pointer">
          <strong>{balance.name || "Prepaid purchase"}</strong>
          {balance.payment_method && <> · {balance.payment_method}</>}
          {balance.refund_status && <> · {balance.refund_status}</>}
          {" · "}{balance.expired ? 0 : balance.sessions_remaining}{balance.sessions ? ` of ${balance.sessions}` : ""} sessions available
          </summary>
          <p className="ml-4">Purchased {purchaseDate.format(new Date(balance.purchased_at))}
          {balance.expires_at && <> · {balance.expired ? "Expired" : "Expires"} {purchaseDate.format(new Date(balance.expiration_date ? balance.expiration_date + "T12:00:00" : balance.expires_at))}</>}
          </p>
        </details>
      )) : <p>Eligible package sessions remaining: {payment.package_sessions_remaining}</p>}
    </div>
  );
}
