export const DEFAULT_LANGUAGE = "en";
export const SHOP_LANGUAGES = {
  en: "English",
  es: "Español",
  vi: "Tiếng Việt",
  "zh-Hans": "简体中文",
  ko: "한국어",
  th: "ไทย",
};

export const LANGUAGE_STORAGE_KEY = "daytello.shop-language";

export function normalizeShopLanguage(value) {
  return Object.hasOwn(SHOP_LANGUAGES, value) ? value : DEFAULT_LANGUAGE;
}

// Values follow the order of the five translated languages in SHOP_LANGUAGES.
const translations = {
  "← Back to DayTello": ["← Volver a DayTello", "← Quay lại DayTello", "← 返回 DayTello", "← DayTello로 돌아가기", "← กลับไปที่ DayTello"],
  "Start your free month": ["Comienza tu mes gratis", "Bắt đầu tháng dùng thử miễn phí", "开始免费试用一个月", "1개월 무료 체험 시작", "เริ่มทดลองใช้ฟรีหนึ่งเดือน"],
  "Your business": ["Tu negocio", "Cơ sở kinh doanh của bạn", "您的店铺", "내 사업장", "ธุรกิจของคุณ"],
  "Business Name": ["Nombre del negocio", "Tên cơ sở kinh doanh", "店铺名称", "사업장 이름", "ชื่อธุรกิจ"],
  "Your booking page": ["Tu página de reservas", "Trang đặt lịch của bạn", "您的预约页面", "내 예약 페이지", "หน้าจองคิวของคุณ"],
  "Your account": ["Tu cuenta", "Tài khoản của bạn", "您的账户", "내 계정", "บัญชีของคุณ"],
  "Your Name": ["Tu nombre", "Họ và tên", "您的姓名", "이름", "ชื่อของคุณ"],
  Email: ["Correo electrónico", "Email", "电子邮箱", "이메일", "อีเมล"],
  Password: ["Contraseña", "Mật khẩu", "密码", "비밀번호", "รหัสผ่าน"],
  "Confirm Password": ["Confirmar contraseña", "Xác nhận mật khẩu", "确认密码", "비밀번호 확인", "ยืนยันรหัสผ่าน"],
  "Staff Dashboard": ["Panel del personal", "Bảng điều khiển nhân viên", "员工控制台", "직원 대시보드", "แดชบอร์ดพนักงาน"],
  "Admin Dashboard": ["Panel de administración", "Bảng điều khiển quản trị", "管理控制台", "관리자 대시보드", "แดชบอร์ดผู้ดูแล"],
  "Your Shop Info": ["Información de tu negocio", "Thông tin cửa hàng của bạn", "您的店铺信息", "내 매장 정보", "ข้อมูลร้านของคุณ"],
  "Owner dashboard": ["Panel del propietario", "Bảng điều khiển chủ cửa hàng", "店主管理面板", "사업주 대시보드", "แดชบอร์ดเจ้าของร้าน"],
  "Customer booking page": ["Página de reservas para clientes", "Trang đặt lịch cho khách hàng", "客户预约页面", "고객 예약 페이지", "หน้าจองคิวสำหรับลูกค้า"],
};

const translatedLanguages = Object.keys(SHOP_LANGUAGES).slice(1);

export function translateShopMessage(language, message) {
  return Object.hasOwn(translations, message)
    ? translations[message][translatedLanguages.indexOf(language)] ?? message
    : message;
}
