import AdminHome from "../../components/AdminHome";

export default async function ShopAdminPage({ params }) {
  const { shop } = await params;

  return <AdminHome shop={shop} />;
}