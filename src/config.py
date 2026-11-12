# -*- coding: utf-8 -*-
"""
Configuration and Taxonomy for Vietnamese Politicians Graph (Approach 3).
"""
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
RAW_DATA_DIR = os.path.join(DATA_DIR, "raw")
PROCESSED_DATA_DIR = os.path.join(DATA_DIR, "processed")
EXPORT_DIR = os.path.join(DATA_DIR, "export")
REPORT_FIG_DIR = os.path.join(BASE_DIR, "figures")

for d in [DATA_DIR, RAW_DATA_DIR, PROCESSED_DATA_DIR, EXPORT_DIR, REPORT_FIG_DIR]:
    os.makedirs(d, exist_ok=True)

# 63 Vietnamese Provinces & Municipalities + Historical Administrative Units
PROVINCES = [
    "An Giang", "Bà Rịa - Vũng Tàu", "Bà Rịa – Vũng Tàu", "Bắc Giang", "Bắc Kạn", "Bạc Liêu",
    "Bắc Ninh", "Bến Tre", "Bình Định", "Bình Dương", "Bình Phước", "Bình Thuận",
    "Cà Mau", "Cần Thơ", "Cao Bằng", "Đà Nẵng", "Đắk Lắk", "Đắk Nông", "Điện Biên",
    "Đồng Nai", "Đồng Tháp", "Gia Lai", "Hà Giang", "Hà Nam", "Hà Nội", "Hà Tĩnh",
    "Hải Dương", "Hải Phòng", "Hậu Giang", "Hòa Bình", "Hưng Yên", "Khánh Hòa",
    "Kiên Giang", "Kon Tum", "Lai Châu", "Lâm Đồng", "Lạng Sơn", "Lào Cai", "Long An",
    "Nam Định", "Nghệ An", "Ninh Bình", "Ninh Thuận", "Phú Thọ", "Phú Yên", "Quảng Bình",
    "Quảng Nam", "Quảng Ngãi", "Quảng Ninh", "Quảng Trị", "Sóc Trăng", "Sơn La",
    "Tây Ninh", "Thái Bình", "Thái Nguyên", "Thanh Hóa", "Thừa Thiên Huế", "Thừa Thiên – Huế",
    "Tiền Giang", "TP. Hồ Chí Minh", "Thành phố Hồ Chí Minh", "Trà Vinh", "Tuyên Quang",
    "Vĩnh Long", "Vĩnh Phúc", "Yên Bái",
    "Hà Tây", "Sông Bé", "Hải Hưng", "Hà Nam Ninh", "Vĩnh Phú", "Hoàng Liên Sơn",
    "Bắc Thái", "Cao Lạng", "Minh Hải", "Cửu Long", "Bình Trị Thiên", "Nghệ Tĩnh"
]

PROVINCE_CANONICAL = {
    "TP. Hồ Chí Minh": "Thành phố Hồ Chí Minh",
    "TP Hồ Chí Minh": "Thành phố Hồ Chí Minh",
    "Sài Gòn": "Thành phố Hồ Chí Minh",
    "TP.HCM": "Thành phố Hồ Chí Minh",
    "Bà Rịa – Vũng Tàu": "Bà Rịa - Vũng Tàu",
    "Thừa Thiên – Huế": "Thừa Thiên Huế",
    "Hà Tây": "Hà Nội"
}

CENTRAL_AGENCIES = [
    "Bộ Chính trị", "Ban Bí thư", "Ban Chấp hành Trung ương Đảng",
    "Ban Tổ chức Trung ương", "Ủy ban Kiểm tra Trung ương", "Ban Tuyên giáo Trung ương",
    "Ban Nội chính Trung ương", "Ban Kinh tế Trung ương", "Ban Dân vận Trung ương",
    "Ban Đối ngoại Trung ương", "Văn phòng Trung ương Đảng", "Học viện Chính trị Quốc gia Hồ Chí Minh",
    "Quốc hội", "Ủy ban Thường vụ Quốc hội", "Hội đồng Dân tộc",
    "Ủy ban Đối ngoại của Quốc hội", "Ủy ban Pháp luật", "Ủy ban Tư pháp", "Ủy ban Kinh tế",
    "Ủy ban Tài chính - Ngân sách", "Ủy ban Quốc phòng và An ninh",
    "Chính phủ", "Văn phòng Chính phủ",
    "Bộ Quốc phòng", "Bộ Công an", "Bộ Ngoại giao", "Bộ Tư pháp", "Bộ Tài chính",
    "Bộ Công Thương", "Bộ Kế hoạch và Đầu tư", "Bộ Nông nghiệp và Phát triển nông thôn",
    "Bộ Xây dựng", "Bộ Giao thông Vận tải", "Bộ Tài nguyên và Môi trường",
    "Bộ Thông tin và Truyền thông", "Bộ Lao động - Thương binh và Xã hội",
    "Bộ Văn hóa, Thể thao và Du lịch", "Bộ Khoa học và Công nghệ", "Bộ Giáo dục và Đào tạo",
    "Bộ Y tế", "Thanh tra Chính phủ", "Ngân hàng Nhà nước Việt Nam", "Ủy ban Dân tộc",
    "Tòa án nhân dân tối cao", "Viện kiểm sát nhân dân tối cao", "Kiểm toán Nhà nước",
    "Ủy ban Trung ương Mặt trận Tổ quốc Việt Nam", "Tổng Liên đoàn Lao động Việt Nam",
    "Trung ương Đoàn Thanh niên Cộng sản Hồ Chí Minh", "Hội Liên hiệp Phụ nữ Việt Nam"
]

RELATION_TYPES = {
    "PREDECESSOR_OF": "Chính khách A là tiền nhiệm của chính khách B ở cùng một chức vụ/cơ quan",
    "SUCCESSOR_OF": "Chính khách A là kế nhiệm của chính khách B ở cùng một chức vụ/cơ quan",
    "HELD_POSITION": "Chính khách đảm nhiệm một chức vụ cụ thể trong khoảng thời gian xác định",
    "BELONGS_TO_ORG": "Chính khách công tác, giữ chức vụ lãnh đạo tại cơ quan, bộ ngành hoặc địa phương",
    "CO_LEADER": "Hai chính khách cùng thuộc ban lãnh đạo (BCT, Ban Bí thư, Ban Thường vụ, Nội các) cùng một nhiệm kỳ",
    "DEPUTY_OF": "Chính khách là cấp phó trực tiếp của cấp trưởng (Thứ trưởng/Bộ trưởng, Phó Bí thư/Bí thư, Phó Chủ tịch/Chủ tịch)",
    "ROSE_FROM_GRASSROOTS": "Chính khách có quá trình bắt đầu sự nghiệp và trưởng thành từ cấp cơ sở (xã, phường, huyện, nông trường, xí nghiệp)",
    "TRANSFERRED_TO": "Chính khách được điều động, luân chuyển công tác giữa các địa phương hoặc từ Trung ương về địa phương",
    "PROMOTED_TO_CENTRAL": "Chính khách từ lãnh đạo địa phương (tỉnh/thành ủy, UBND tỉnh) được bổ nhiệm, rút lên cơ quan Trung ương",
    "NATIVE_OF": "Địa phương là quê quán / nguyên quán của chính khách",
    "DELEGATE_OF": "Chính khách là Đại biểu Quốc hội đại diện cho đoàn đại biểu của tỉnh/thành phố",
    "CENTRAL_COMMITTEE_MEMBER": "Chính khách được bầu làm Ủy viên Ban Chấp hành Trung ương Đảng ở khóa tương ứng"
}

WIKI_SEED_CATEGORIES = [
    "Thể loại:Chính khách Việt Nam",
    "Thể loại:Đại biểu Quốc hội Việt Nam khóa XV",
    "Thể loại:Đại biểu Quốc hội Việt Nam khóa XIV",
    "Thể loại:Đại biểu Quốc hội Việt Nam khóa XIII",
    "Thể loại:Đại biểu Quốc hội Việt Nam khóa XII",
    "Thể loại:Đại biểu Quốc hội Việt Nam khóa XI",
    "Thể loại:Ủy viên Ban Chấp hành Trung ương Đảng Cộng sản Việt Nam khóa XIII",
    "Thể loại:Ủy viên Ban Chấp hành Trung ương Đảng Cộng sản Việt Nam khóa XII",
    "Thể loại:Ủy viên Ban Chấp hành Trung ương Đảng Cộng sản Việt Nam khóa XI",
    "Thể loại:Ủy viên Ban Chấp hành Trung ương Đảng Cộng sản Việt Nam khóa X",
    "Thể loại:Bộ trưởng Việt Nam",
    "Thể loại:Thứ trưởng Việt Nam",
    "Thể loại:Bí thư Tỉnh ủy, Thành ủy Việt Nam",
    "Thể loại:Chủ tịch Ủy ban nhân dân tỉnh Việt Nam",
    "Thể loại:Ủy viên Bộ Chính trị Ban Chấp hành Trung ương Đảng Cộng sản Việt Nam",
    "Thể loại:Chủ tịch Hội đồng nhân dân tỉnh, thành phố trực thuộc trung ương Việt Nam",
    "Thể loại:Tướng lĩnh Quân đội nhân dân Việt Nam",
    "Thể loại:Tướng lĩnh Công an nhân dân Việt Nam"
]
