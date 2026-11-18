import AdminHome from "../../../components/AdminHome";

export default async function ShopInfoPage({ params }) {
  const { shop } = await params;
  return <AdminHome shop={shop} showShopInfo />;
}
