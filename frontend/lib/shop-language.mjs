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
  "Tell us about your business, choose the plan that works best for you, and start your first 30 days free.": ["Cuéntanos sobre tu negocio, elige el plan que más te convenga y empieza con 30 días gratis.", "Hãy giới thiệu cơ sở kinh doanh của bạn, chọn gói phù hợp và dùng thử miễn phí 30 ngày.", "请填写店铺信息，选择适合您的方案，免费试用 30 天。", "사업장 정보를 입력하고 알맞은 요금제를 선택해 30일 무료 체험을 시작하세요.", "กรอกข้อมูลธุรกิจ เลือกแพ็กเกจที่เหมาะกับคุณ แล้วเริ่มทดลองใช้ฟรี 30 วัน"],
  "YOUR FIRST 30 DAYS ARE FREE — $0 TODAY": ["TUS PRIMEROS 30 DÍAS SON GRATIS. HOY PAGAS $0.", "MIỄN PHÍ 30 NGÀY ĐẦU. HÔM NAY TRẢ $0.", "前 30 天免费，今天支付 $0", "첫 30일 무료 · 오늘 결제 금액 $0", "ฟรี 30 วันแรก วันนี้จ่าย $0"],
  "A credit card is required to start your free trial. You will not be charged today. Your selected plan begins billing after your 30-day trial unless you cancel.": ["Necesitas una tarjeta de crédito para iniciar la prueba gratis. Hoy no se te cobrará. El plan elegido se cobrará tras los 30 días de prueba, a menos que lo canceles.", "Bạn cần thẻ tín dụng để bắt đầu dùng thử miễn phí. Hôm nay bạn sẽ không bị tính phí. Gói đã chọn sẽ bắt đầu tính phí sau 30 ngày dùng thử nếu bạn không hủy.", "开始免费试用需要信用卡。今天不会扣费。若未取消，所选方案将在 30 天试用期结束后开始收费。", "무료 체험을 시작하려면 신용카드가 필요합니다. 오늘은 결제되지 않습니다. 취소하지 않으면 30일 체험이 끝난 뒤 선택한 요금제가 청구됩니다.", "ต้องใช้บัตรเครดิตเพื่อเริ่มทดลองใช้ฟรี วันนี้จะไม่มีการเรียกเก็บเงิน หากไม่ยกเลิก ระบบจะเริ่มคิดค่าบริการตามแพ็กเกจที่เลือกหลังครบ 30 วัน"],
  "Enter it exactly as you want customers to see it.": ["Escribe el nombre tal como quieres que lo vean tus clientes.", "Nhập tên đúng như bạn muốn khách hàng nhìn thấy.", "请填写您希望向客户显示的店铺名称。", "고객에게 표시할 이름을 그대로 입력하세요.", "กรอกชื่อที่ต้องการให้ลูกค้าเห็น"],
  "This updates automatically from your business name. You can change the URL above if you prefer something different.": ["La URL se genera automáticamente a partir del nombre de tu negocio. Puedes editarla arriba.", "Đường dẫn được tạo tự động từ tên cơ sở kinh doanh. Bạn có thể chỉnh sửa ở trên.", "网址会根据店铺名称自动生成。您也可以在上方修改。", "사업장 이름으로 주소가 자동 생성됩니다. 위에서 주소를 변경할 수 있습니다.", "ระบบจะสร้าง URL จากชื่อธุรกิจโดยอัตโนมัติ คุณแก้ไข URL ด้านบนได้"],
  "Business Type": ["Tipo de negocio", "Loại hình kinh doanh", "店铺类型", "업종", "ประเภทธุรกิจ"],
  "Business Phone": ["Teléfono del negocio", "Số điện thoại của cơ sở", "店铺电话", "사업장 전화번호", "เบอร์โทรธุรกิจ"],
  "Other Service Business": ["Otro negocio de servicios", "Dịch vụ khác", "其他服务业", "기타 서비스업", "ธุรกิจบริการอื่น ๆ"],
  "Barbershop": ["Barbería", "Tiệm cắt tóc nam", "男士理发店", "이발소", "ร้านตัดผมชาย"],
  "Hair Salon": ["Peluquería", "Tiệm làm tóc", "美发店", "미용실", "ร้านทำผม"],
  "Nail Salon": ["Salón de uñas", "Tiệm làm móng", "美甲店", "네일숍", "ร้านทำเล็บ"],
  "Massage / Wellness": ["Masajes / Bienestar", "Mát-xa / Chăm sóc sức khỏe", "按摩／养生", "마사지 / 웰니스", "นวด / สุขภาพ"],
  "Personal Training / Fitness": ["Entrenamiento personal / Gimnasio", "Huấn luyện cá nhân / Thể hình", "私人教练／健身", "개인 트레이닝 / 피트니스", "เทรนส่วนตัว / ฟิตเนส"],
  "At least 8 characters": ["Al menos 8 caracteres", "Ít nhất 8 ký tự", "至少 8 个字符", "8자 이상", "อย่างน้อย 8 อักขระ"],
  "Enter password again": ["Vuelve a escribir la contraseña", "Nhập lại mật khẩu", "再次输入密码", "비밀번호 다시 입력", "กรอกรหัสผ่านอีกครั้ง"],
  "Choose your plan": ["Elige tu plan", "Chọn gói của bạn", "选择您的方案", "요금제 선택", "เลือกแพ็กเกจ"],
  "Both plans include your first 30 days free. Choose what works best for your business.": ["Ambos planes incluyen 30 días gratis. Elige el que mejor se adapte a tu negocio.", "Cả hai gói đều miễn phí 30 ngày đầu. Hãy chọn gói phù hợp với cơ sở của bạn.", "两个方案均包含前 30 天免费试用。请选择适合您店铺的方案。", "두 요금제 모두 처음 30일은 무료입니다. 사업장에 알맞은 요금제를 선택하세요.", "ทั้งสองแพ็กเกจทดลองใช้ฟรี 30 วันแรก เลือกแพ็กเกจที่เหมาะกับธุรกิจของคุณ"],

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
