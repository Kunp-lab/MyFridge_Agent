import sys
import random
import math
from datetime import datetime
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QGridLayout, QLabel, QFrame, QDialog, QPushButton, QStackedWidget)
from PySide6.QtCore import Qt, QTimer, Signal, QTime, QPointF,QThread
from PySide6.QtGui import QFont, QColor, QPixmap, QPainter, QPainterPath, QLinearGradient, QPen, QBrush,QImage
from PySide6.QtWidgets import QGraphicsDropShadowEffect
from PySide6.QtGui import QColor
from .display_node import RosWorker

# ==========================================
# 辅助生成器：星露谷占位图 
# ==========================================
def create_pixel_placeholder(text: str) -> QPixmap:
    pixmap = QPixmap(16, 16)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, False) 
    
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#8B2500"))
    painter.drawRect(3, 11, 10, 4)
    painter.drawRect(4, 15, 8, 1)
    
    painter.setBrush(QColor("#E8B84B"))
    painter.drawRect(4, 8, 8, 3)
    painter.drawRect(6, 6, 4, 2)
    
    painter.setPen(QColor("#FFFFFF"))
    font = QFont("SimSun", 6)
    painter.setFont(font)
    display_char = text[0] if text else "空"
    painter.drawText(0, 0, 16, 15, Qt.AlignmentFlag.AlignCenter, display_char)
    painter.end()
    
    return pixmap.scaled(128, 128, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)


# ==========================================
# 待机屏幕组件 (纯代码绘制复古水墨表盘)
# ==========================================
class StandbyScreen(QWidget):
    clicked = Signal() # 点击信号

    def __init__(self):
        super().__init__()
        self.setObjectName("StandbyScreen")
        self.current_time = QTime.currentTime()
        
        # 启动每秒更新的时钟
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_time)
        self.timer.start(1000)
        
        # 简单节气计算逻辑 (仅作演示，实际应用可接入更复杂的农历库)
        self.solar_term = self._get_solar_term()

        # 样式：模拟深色木纹背景
        self.setStyleSheet("""
            QWidget#StandbyScreen {
                background-color: #261A15; /* 深色黑胡桃木底色 */
            }
        """)

    def _get_solar_term(self):
        """简易节气推算（演示用）"""
        month = datetime.now().month
        day = datetime.now().day
        if not (1 <= month <= 12) or not (1 <= day <= 31):
            return "无效日期"

        # 春季
        if month == 2 and day >= 3 or month == 1 and day >= 20:   # 大寒 ~ 立春
            if month == 1 or (month == 2 and day < 19):
                return "立 春" if day >= 4 else "大 寒"  # 更精确点可细分，但通常立春2/3-5
        # 下面用 elif 链式判断更清晰

        if month == 2:
            if day < 19: return "立 春"
            else:        return "雨 水"   # 雨水 ≈ 2月18-20日

        elif month == 3:
            if day < 6:  return "雨 水"
            elif day < 20: return "惊 蛰"   # 惊蛰 ≈ 3月5-7日
            else:        return "春 分"     # 春分 ≈ 3月20-21日

        elif month == 4:
            if day < 5:  return "春 分"
            elif day < 20: return "清 明"   # 清明 ≈ 4月4-6日
            else:        return "谷 雨"     # 谷雨 ≈ 4月19-21日

        elif month == 5:
            if day < 6:  return "谷 雨"
            elif day < 21: return "立 夏"   # 立夏 ≈ 5月5-7日
            else:        return "小 满"     # 小满 ≈ 5月20-22日

        elif month == 6:
            if day < 6:  return "小 满"
            elif day < 21: return "芒 种"   # 芒种 ≈ 6月5-7日
            else:        return "夏 至"     # 夏至 ≈ 6月21-22日

        elif month == 7:
            if day < 8:  return "夏 至"
            elif day < 23: return "小 暑"   # 小暑 ≈ 7月7-8日
            else:        return "大 暑"     # 大暑 ≈ 7月22-24日

        elif month == 8:
            if day < 8:  return "大 暑"
            elif day < 23: return "立 秋"   # 立秋 ≈ 8月7-8日
            else:        return "处 暑"     # 处暑 ≈ 8月22-24日

        elif month == 9:
            if day < 8:  return "处 暑"
            elif day < 23: return "白 露"   # 白露 ≈ 9月7-9日
            else:        return "秋 分"     # 秋分 ≈ 9月22-24日

        elif month == 10:
            if day < 9:  return "秋 分"
            elif day < 24: return "寒 露"   # 寒露 ≈ 10月8-9日
            else:        return "霜 降"     # 霜降 ≈ 10月23-24日

        elif month == 11:
            if day < 8:  return "霜 降"
            elif day < 23: return "立 冬"   # 立冬 ≈ 11月7-8日
            else:        return "小 雪"     # 小雪 ≈ 11月22-23日

        elif month == 12:
            if day < 7:  return "小 雪"
            elif day < 22: return "大 雪"   # 大雪 ≈ 12月6-8日
            else:        return "冬 至"     # 冬至 ≈ 12月21-23日

        elif month == 1:
            if day < 6:  return "冬 至"
            elif day < 20: return "小 寒"   # 小寒 ≈ 1月5-7日
            else:        return "大 寒"     # 大寒 ≈ 1月19-21日

        return "未知节气"

    def update_time(self):
        self.current_time = QTime.currentTime()
        self.update() # 触发重绘

    def paintEvent(self, event):
        """核心：用代码画出水墨山水表盘"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width, height = self.width(), self.height()

        # 1. 绘制右上角的数字时间和日期
        painter.setPen(QColor("#D4AF70")) # 哑金色
        painter.setFont(QFont("Microsoft YaHei", 24, QFont.Weight.Bold))
        time_str = self.current_time.toString("HH:mm")
        date_str = datetime.now().strftime("%m月%d日")
        painter.drawText(width - 250, 40, 220, 40, Qt.AlignmentFlag.AlignRight, f"{time_str} · {date_str}")
        
        # 绘制节气汉字
        painter.setFont(QFont("KaiTi", 18, QFont.Weight.Bold))
        painter.drawText(width - 250, 80, 220, 30, Qt.AlignmentFlag.AlignRight, self.solar_term)

        # 2. 绘制中央水墨圆盘
        center = QPointF(width / 2, height / 2)
        radius = min(width, height) * 0.38
        
        # 黄铜外边框
        pen = QPen(QColor("#9E7A45"), 12)
        painter.setPen(pen)
        painter.setBrush(QColor("#E8ECEC")) # 表盘底色 (浅青白)
        painter.drawEllipse(center, radius, radius)

        # 内部再加一条细刻度线
        pen.setWidth(2)
        pen.setColor(QColor("#5C4A3D"))
        painter.setPen(pen)
        painter.drawEllipse(center, radius - 15, radius - 15)

        # 3. 绘制表盘内部的水墨山脉 (使用剪裁路径，确保山脉不超出圆盘)
        painter.save()
        clip_path = QPainterPath()
        clip_path.addEllipse(center, radius - 15, radius - 15)
        painter.setClipPath(clip_path)

        # 后景山 (淡墨)
        path1 = QPainterPath()
        path1.moveTo(center.x() - radius, center.y() + 20)
        path1.quadTo(center.x() - radius*0.5, center.y() - 50, center.x(), center.y() + 10)
        path1.quadTo(center.x() + radius*0.5, center.y() - 80, center.x() + radius, center.y() + 30)
        path1.lineTo(center.x() + radius, center.y() + radius)
        path1.lineTo(center.x() - radius, center.y() + radius)
        painter.fillPath(path1, QColor(100, 110, 115, 120))

        # 前景山 (浓墨)
        path2 = QPainterPath()
        path2.moveTo(center.x() - radius, center.y() + 60)
        path2.quadTo(center.x() - radius*0.3, center.y() - 10, center.x() + radius*0.2, center.y() + 50)
        path2.quadTo(center.x() + radius*0.7, center.y() - 30, center.x() + radius, center.y() + 70)
        path2.lineTo(center.x() + radius, center.y() + radius)
        path2.lineTo(center.x() - radius, center.y() + radius)
        grad = QLinearGradient(center.x(), center.y(), center.x(), center.y() + radius)
        grad.setColorAt(0, QColor(30, 35, 35, 230))
        grad.setColorAt(1, QColor(10, 15, 15, 255))
        painter.fillPath(path2, grad)
        
        painter.restore()

        # 4. 绘制表盘周围的复古刻度和文字
        painter.setPen(QPen(QColor("#2C1E16"), 2))
        painter.setFont(QFont("SimSun", 10, QFont.Weight.Bold))
        for i in range(12):
            angle = (i * 30 - 90) * math.pi / 180
            tx = center.x() + (radius - 30) * math.cos(angle)
            ty = center.y() + (radius - 30) * math.sin(angle)
            
            # 画刻度点
            painter.drawEllipse(QPointF(tx, ty), 2, 2)
            
            # 画数字 (子丑寅卯等)
            dizhi = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
            text_x = center.x() + (radius - 50) * math.cos(angle)
            text_y = center.y() + (radius - 50) * math.sin(angle)
            painter.drawText(int(text_x - 10), int(text_y - 10), 20, 20, Qt.AlignmentFlag.AlignCenter, dizhi[i])

        # 5. 绘制时钟指针
        hour = self.current_time.hour() % 12
        minute = self.current_time.minute()
        second = self.current_time.second()

        # 分针 (长)
        painter.save()
        painter.translate(center)
        painter.rotate(minute * 6 + second * 0.1)
        painter.setPen(QPen(QColor("#2C1E16"), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(0, 15, 0, int(-radius * 0.7))
        painter.restore()

        # 时针 (短粗)
        painter.save()
        painter.translate(center)
        painter.rotate(hour * 30 + minute * 0.5)
        painter.setPen(QPen(QColor("#5C4A3D"), 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(0, 10, 0, int(-radius * 0.45))
        painter.restore()

        # 秒针 (红)
        painter.save()
        painter.translate(center)
        painter.rotate(second * 6)
        painter.setPen(QPen(QColor("#8B2500"), 2))
        painter.drawLine(0, 20, 0, int(-radius * 0.8))
        painter.setBrush(QColor("#8B2500"))
        painter.drawEllipse(QPointF(0, 0), 6, 6) # 中心红点
        painter.restore()

        # 6. 底部提示语
        painter.setPen(QColor("#888888"))
        painter.setFont(QFont("KaiTi", 14))
        painter.drawText(0, height - 60, width, 30, Qt.AlignmentFlag.AlignCenter, "— 点击任意处 唤醒食盒 —")

    def mouseReleaseEvent(self, event):
        """重写鼠标点击事件：点击即切换到主界面"""
        self.clicked.emit()
        super().mouseReleaseEvent(event)


# ==========================================
# 详情弹窗组件 
# ==========================================
class FoodDetailDialog(QDialog):
    def __init__(self, name: str, features: list, precautions: list, image_path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{name} · 珍馐档案")
        self.setFixedSize(500, 320)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._init_ui(name, features, precautions, image_path)

    def _init_ui(self, name, features, precautions, image_path):
        main_frame = QFrame(self)
        main_frame.setGeometry(0, 0, 500, 320)
        main_frame.setObjectName("DialogFrame")

        layout = QVBoxLayout(main_frame)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        header_layout = QHBoxLayout()
        title_label = QLabel(f"❖ {name} ❖")
        title_label.setObjectName("DialogTitle")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        close_btn = QPushButton("✖")
        close_btn.setObjectName("CloseBtn")
        close_btn.setFixedSize(36, 36)
        close_btn.clicked.connect(self.accept)

        header_layout.addWidget(title_label, stretch=1)
        header_layout.addWidget(close_btn)
        layout.addLayout(header_layout)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(20)
        
        img_frame = QFrame()
        img_frame.setObjectName("ImageFrame")
        img_frame.setFixedSize(140, 140)
        img_layout = QVBoxLayout(img_frame)
        img_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img_layout.setContentsMargins(0, 0, 0, 0)
        
        self.img_label = QLabel()
        self.img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            pixmap = create_pixel_placeholder(name) 
        else:
            pixmap = pixmap.scaled(128, 128, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)
            
        self.img_label.setPixmap(pixmap)
        img_layout.addWidget(self.img_label)
        
        left_panel = QVBoxLayout()
        left_panel.addWidget(img_frame)
        left_panel.addStretch()
        content_layout.addLayout(left_panel)
        
        text_panel = QVBoxLayout()
        text_panel.setSpacing(8)
        
        feat_title = QLabel("【 珍 馐 特 征 】")
        feat_title.setObjectName("SectionTitle")
        text_panel.addWidget(feat_title)
        for feat in features:
            lbl = QLabel(f"✦ {feat}")
            lbl.setWordWrap(True)
            lbl.setObjectName("DetailText")
            text_panel.addWidget(lbl)
            
        text_panel.addSpacing(10)
            
        prec_title = QLabel("【 食 用 禁 忌 】")
        prec_title.setObjectName("SectionTitle")
        text_panel.addWidget(prec_title)
        for prec in precautions:
            lbl = QLabel(f"✦ {prec}")
            lbl.setWordWrap(True)
            lbl.setObjectName("DetailText_Warning")
            text_panel.addWidget(lbl)
            
        text_panel.addStretch()
        content_layout.addLayout(text_panel, stretch=1)
        layout.addLayout(content_layout)

        self.setStyleSheet("""
            QFrame#DialogFrame {
                background-color: #E6C687;
                border: 6px solid #4A2B18; 
                border-top-color: #6B4126;
                border-left-color: #6B4126;
                border-bottom-color: #2F190D;
                border-right-color: #2F190D;
            }
            QLabel#DialogTitle {
                background-color: #8B2500; 
                color: #FFD700; 
                font-family: "SimSun", "Microsoft YaHei";
                font-size: 20px;
                font-weight: 900;
                border: 4px solid #4A2B18;
                padding: 6px;
                letter-spacing: 2px;
            }
            QPushButton#CloseBtn {
                background-color: #C0392B;
                color: white;
                font-size: 18px;
                font-weight: bold;
                border: 4px solid #4A2B18;
                border-top-color: #E74C3C;
                border-left-color: #E74C3C;
            }
            QPushButton#CloseBtn:pressed {
                border-top-color: #2F190D;
                border-left-color: #2F190D;
                background-color: #922B21;
            }
            QFrame#ImageFrame {
                background-color: #F8E5BA; 
                border: 4px solid #4A2B18;
                border-top-color: #2F190D;
                border-left-color: #2F190D;
                border-bottom-color: #A37941;
                border-right-color: #A37941;
            }
            QLabel#SectionTitle {
                font-family: "KaiTi", "Microsoft YaHei";
                font-size: 16px;
                font-weight: bold;
                color: #4A2B18;
                background-color: #D4AF70;
                padding: 2px 5px;
                border: 2px solid #4A2B18;
            }
            QLabel#DetailText {
                font-family: "SimSun", "Microsoft YaHei";
                font-size: 14px;
                font-weight: bold;
                color: #2C1E16;
            }
            QLabel#DetailText_Warning {
                font-family: "SimSun", "Microsoft YaHei";
                font-size: 14px;
                font-weight: bold;
                color: #8B2500; 
            }
        """)


# ==========================================
# 食物卡片组件 (包含【毛笔一笔画圈】的核心算法)
# ==========================================
class FoodCard(QFrame):
    clicked = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CardFrame")
        self.setFixedSize(180, 130) 
        self.food_data = {"name": "", "days_left": -1, "features": [], "precautions": [], "image_path": ""}
        self.ink_pixmap = None 
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)

        self.name_label = QLabel("虚位以待")
        self.name_label.setObjectName("PillLabel_Name")
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setFixedHeight(32)

        self.expire_label = QLabel("—")
        self.expire_label.setObjectName("PillLabel_Expire")
        self.expire_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.expire_label.setFixedHeight(32)

        layout.addWidget(self.name_label)
        layout.addWidget(self.expire_label)

        self.setStyleSheet("""
            QFrame#CardFrame {
                background-color: #F4F6F6; 
                border: 2px solid #9C8570;
                border-radius: 12px;
            }
            QFrame#CardFrame:hover {
                background-color: #E8ECEC;
                border: 2px solid #D98842;
            }
            QLabel {
                border: 2px solid #9C8570;
                border-radius: 15px; 
                background-color: rgba(255, 255, 255, 0.85); 
                font-family: "Microsoft YaHei";
                font-weight: bold;
                font-size: 15px;
            }
            QLabel#PillLabel_Name { color: #2F5960; }
        """)

    def _generate_brush_circle(self, name: str, days_left: int):
        if days_left < 0:
            self.ink_pixmap = None
            return

        width, height = self.width(), self.height()
        self.ink_pixmap = QPixmap(width, height)
        self.ink_pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(self.ink_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing) 
        painter.setPen(Qt.PenStyle.NoPen)

        random.seed(name) 

        if days_left <= 3:
            color = QColor(20, 20, 20, 220)   
            base_thickness = 10               
            arc_length = random.uniform(1.0, 1.2) 
            splatter_chance = 0.3             
        elif days_left <= 7:
            color = QColor(60, 60, 60, 150)   
            base_thickness = 6
            arc_length = random.uniform(0.7, 0.9) 
            splatter_chance = 0.1
        else:
            color = QColor(130, 130, 130, 70) 
            base_thickness = 3
            arc_length = random.uniform(0.4, 0.6) 
            splatter_chance = 0.02

        painter.setBrush(color)

        cx = width / 2 + random.uniform(-10, 10)
        cy = height / 2 + random.uniform(-5, 5)
        R_x = width / 2 - 25
        R_y = height / 2 - 20
        start_angle = random.uniform(0, math.pi * 2)

        steps = int(200 * arc_length)
        for i in range(steps):
            t = i / float(200) 
            theta = start_angle + t * math.pi * 2

            jitter_x = random.uniform(-2, 2)
            jitter_y = random.uniform(-2, 2)
            x = cx + R_x * math.cos(theta) + jitter_x
            y = cy + R_y * math.sin(theta) + jitter_y

            pressure = math.sin(t * math.pi / arc_length) if arc_length <= 1.0 else math.sin(t * math.pi)
            pressure = max(0.1, pressure) 
            current_thickness = base_thickness * pressure * random.uniform(0.6, 1.4)

            painter.drawEllipse(int(x - current_thickness/2), int(y - current_thickness/2),
                                int(current_thickness), int(current_thickness))

            if random.random() < splatter_chance:
                sx = x + random.uniform(-base_thickness*3, base_thickness*3)
                sy = y + random.uniform(-base_thickness*3, base_thickness*3)
                s_size = random.uniform(1, current_thickness * 0.6)
                
                sp_color = QColor(color)
                sp_color.setAlpha(int(color.alpha() * 0.5)) 
                painter.setBrush(sp_color)
                painter.drawEllipse(int(sx), int(sy), int(s_size), int(s_size))
                painter.setBrush(color) 

        painter.end()
        random.seed() 

    def update_data(self, name: str, days_left: int, features: list, precautions: list, image_path: str):
        self.food_data = {
            "name": name, "days_left": days_left, 
            "features": features, "precautions": precautions, "image_path": image_path
        }
        self.name_label.setText(name)

        if days_left < 0:
            self.expire_label.setText("—")
            self.expire_label.setStyleSheet("color: #777777;")
        elif days_left <= 3:
            self.expire_label.setText(f"仅剩 {days_left} 日")
            self.expire_label.setStyleSheet("color: #D6862A; border-color: #D6862A;") 
        else:
            self.expire_label.setText(f"尚余 {days_left} 日")
            self.expire_label.setStyleSheet("color: #387A65;") 
            
        self._generate_brush_circle(name, days_left)
        self.update() 

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.ink_pixmap:
            painter = QPainter(self)
            painter.drawPixmap(0, 0, self.ink_pixmap)
            painter.end()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.food_data["name"] != "虚位以待":
            self.clicked.emit(self.food_data)
        super().mouseReleaseEvent(event)


# ==========================================
# 主窗口 (搭载 QStackedWidget 实现页面切换)
# ==========================================
class SmartFridgeUI(QMainWindow):
    def __init__(self,node):
        super().__init__()
        self.setWindowTitle("冰鉴 · 珍馐录")
        self.resize(720, 750) # 稍微调大一点以便容纳新按钮
        self.food_grids = []
        
        # 使用 StackedWidget 来管理 3 个页面
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)
        
        # 按顺序初始化并添加页面
        self._init_standby_page()   # 索引 0
        self._init_main_page()      # 索引 1
        self._init_vision_page()    # 索引 2 (新增)
        
        self._apply_global_style()
        
        # 默认显示待机页面 (索引 0)
        self.stacked_widget.setCurrentIndex(0)
        self._start_ros2_thread(node=node)

    def _init_standby_page(self):
        """初始化待机页面"""
        self.standby_page = StandbyScreen()
        # 绑定点击事件，切换到主页面 (索引 1)
        self.standby_page.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(1))
        self.stacked_widget.addWidget(self.standby_page)

    def _init_main_page(self):
        """初始化主页面 (修改：标题栏增加“鉴物”按钮)"""
        self.main_page = QWidget()
        main_layout = QVBoxLayout(self.main_page)
        main_layout.setContentsMargins(30, 20, 30, 20)
        main_layout.setSpacing(15)

        # 标题区域，增加“返回”和“鉴物”按钮
        title_frame = QFrame()
        title_frame.setObjectName("TitleBox")
        title_layout = QHBoxLayout(title_frame)
        title_layout.setContentsMargins(10, 5, 10, 5)
        
        # --- 左侧按钮组 ---
        nav_btn_layout = QHBoxLayout()
        nav_btn_layout.setSpacing(10)

        self.return_btn = QPushButton("◀ 待机")
        self.return_btn.setObjectName("ReturnBtn")
        self.return_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.return_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(0))
        
        # 新增：“鉴物”按钮
        self.vision_nav_btn = QPushButton("▶ 鉴物")
        self.vision_nav_btn.setObjectName("VisionNavBtn") # 使用不同的标识符以便单独贴样式
        self.vision_nav_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        # 点击切换到视觉页面 (索引 2)
        self.vision_nav_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(2))

        nav_btn_layout.addWidget(self.return_btn)
        nav_btn_layout.addWidget(self.vision_nav_btn)
        title_layout.addLayout(nav_btn_layout)

        # --- 中间标题 ---
        title_label = QLabel("冰鉴 · 珍馐录")
        title_label.setObjectName("MainTitle")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_layout.addWidget(title_label, stretch=1)
        
        # 占位符保持标题居中 (宽度需要调整以平衡左侧两个按钮)
        dummy = QLabel()
        dummy.setFixedWidth(240) 
        title_layout.addWidget(dummy)
        
        main_layout.addWidget(title_frame)

        # ... (状态栏和网格部分保持不变) ...
        status_frame = QFrame()
        status_frame.setObjectName("StatusBox")
        status_frame.setFixedHeight(40)
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(20, 0, 20, 0)
        
        self.status_label = QLabel("温度: -- °C   湿度: -- %   ❄ 鲜香守护 ❄")
        self.status_label.setObjectName("StatusText")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        status_layout.addWidget(self.status_label)
        main_layout.addWidget(status_frame)

        grid_layout = QGridLayout()
        grid_layout.setHorizontalSpacing(15)
        grid_layout.setVerticalSpacing(15)
        
        for row in range(3):
            row_list = []
            for col in range(3):
                card = FoodCard()
                card.clicked.connect(self.show_food_details)
                grid_layout.addWidget(card, row, col)
                row_list.append(card)
            self.food_grids.append(row_list)
            
        main_layout.addLayout(grid_layout)
        main_layout.addStretch()
        
        self.stacked_widget.addWidget(self.main_page)

    def _init_vision_page(self):
        """(新增) 初始化第三个页面：视觉识别页"""
        self.vision_page = VisionRecognizePage()
        
        # 绑定页面内的信号
        # 返回主界面 (索引 1)
        self.vision_page.back_clicked.connect(lambda: self.stacked_widget.setCurrentIndex(1))
        # 抓拍按钮事件 (暂时只打印日志，后续可以对接摄像头逻辑)
        self.vision_page.capture_clicked.connect(self._handle_manual_capture)
        
        self.stacked_widget.addWidget(self.vision_page)

    def _handle_manual_capture(self):
        """(演示用) 处理手动抓拍逻辑"""
        self.vision_page.set_result_text("正在运用‘本草识真算法’鉴别中...")
        # 后续你可以这里调用摄像头拍照并更新 VisionPage 的图片

    def _apply_global_style(self):
        # (已更新样式表：增加新导航按钮的样式)
        self.setStyleSheet("""
            QMainWindow { background-color: #EBF4F1; }
            QFrame#TitleBox {
                border: 2px dashed #9C8570; 
                border-radius: 10px;
                background-color: #FDFDFD;
                padding: 5px;
            }
            QLabel#MainTitle {
                font-family: "Microsoft YaHei", "SimHei";
                font-size: 28px;
                font-weight: 900;
                color: #8C471E; 
                letter-spacing: 5px;
            }
            /* 公共导航按钮样式 */
            QPushButton#ReturnBtn, QPushButton#VisionNavBtn {
                background-color: transparent;
                color: #5C4A3D;
                font-family: "KaiTi";
                font-size: 16px;
                font-weight: bold;
                border: 1px solid #9C8570;
                border-radius: 5px;
                padding: 5px 12px;
            }
            QPushButton#ReturnBtn:hover, QPushButton#VisionNavBtn:hover {
                background-color: #E8ECEC;
                border-color: #8C471E;
            }
            /* “鉴物”按钮特色样式 */
            QPushButton#VisionNavBtn {
                color: #8B2500; /* 红褐色字 */
                border-color: #8B2500;
            }
            QPushButton#VisionNavBtn:hover {
                background-color: #FDF2F0;
            }
            QFrame#StatusBox {
                background-color: #F1F6F2;
                border-radius: 8px;
            }
            QLabel#StatusText {
                font-family: "Microsoft YaHei";
                font-size: 13px;
                color: #4A5B5A;
            }
        """)

    def show_food_details(self, data: dict):
        dialog = FoodDetailDialog(data["name"], data["features"], data["precautions"], data["image_path"], self)
        dialog.exec() 

    def set_environment(self, temp: float, humidity: float):
        self.status_label.setText(f"温度: {temp:.1f} °C   湿度: {humidity:.1f} %   ❄ 鲜香守护 ❄")

    def set_food_item(self, row: int, col: int, name: str, days_left: int, features: list, precautions: list, image_path: str = ""):
        if 0 <= row <= 2 and 0 <= col <= 2:
            self.food_grids[row][col].update_data(name, days_left, features, precautions, image_path)
    
    def _start_ros2_thread(self,node):
        """启动 ROS2 Worker 线程"""
        self.ros_worker = RosWorker(node)
        self.ros_worker.node.data_updated.connect(self.update_foods_from_ros)
        self.ros_worker.node.image_updated.connect(self.update_image_from_ros)

        self.ros_worker.start()
    
    def update_image_from_ros(self, qimage: QImage):
        """将从 ROS 接收到的 QImage 显示到视觉页面"""
        if qimage.isNull():
            return
        
        # 1. 将 QImage 转换为 QPixmap
        pixmap = QPixmap.fromImage(qimage)
        
        # 2. 更新视觉页面的显示
        # 即使当前没在看这个页面，后台也可以持续更新
        self.vision_page.update_viewer_image(pixmap)

    def update_foods_from_ros(self, ingredients: list):
        """从 ROS2 接收到的数据更新 GUI 卡片"""
        for i in range(9):
            row = i // 3
            col = i % 3
            item = ingredients[i]
            
            name = item[0]
            expiry = item[1]          # 假设这是剩余天数或过期日期
            features = item[2] if item[2] else []
            precautions = item[3] if item[3] else []
            
            # 计算 days_left（根据你的业务逻辑调整）
            days_left = expiry if isinstance(expiry, int) else -1
            
            self.set_food_item(row, col, name, days_left, features, precautions)

    def closeEvent(self, event):
        """窗口关闭时优雅停止 ROS2 线程"""
        if self.ros_worker:
            self.ros_worker.stop()
        super().closeEvent(event)


# ==========================================
# 程序入口
# ==========================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    fridge = SmartFridgeUI()
    fridge.show()

    initial_foods = [
        ("鲜牛乳", 7, ["散养高山牧场直供", "富含原生高钙", "口感顺滑醇厚"], ["开封后建议3天内饮尽", "冷藏最佳温度2-6°C"], ""),
        ("土鸡卵", 1, ["农家散养土鸡产", "蛋黄深橙色", "无抗生素残留"], ["仅剩1日，推荐尽快食用", "水煮或蒸蛋营养最高"], ""),
        ("老坛酸奶", 14, ["传统老坛发酵", "超浓稠拉丝质地", "含活性益生菌"], ["若有少量乳清析出属正常", "切忌冷冻"], ""),
        ("碧玉西兰", 5, ["深绿色花球紧实", "高维生素C", "清脆爽口"], ["烹饪前可加盐水浸泡", "建议清炒或白灼"], ""),
        ("朱颜草莓", 3, ["红颜品种，个大饱满", "果肉多汁，甜度极高"], ["表面脆弱，忌重压", "吃前清洗，切勿去蒂洗"], ""),
        ("午时腊肉", 10, ["传统烟熏工艺", "肥瘦相间，晶莹剔透"], ["烹饪前建议温水洗去浮油", "高血压者适量食用"], ""),
        ("白玉豆腐", -1, ["使用优质大豆制作", "口感滑嫩细致"], ["未开封前无具体天数", "开封后需泡在清水中冷藏"], ""),
        ("金华火腿", 6, ["金华传统名产", "肉色红润，香气浓郁"], ["表面发酵层需刮除后食用", "切忌水洗存放"], ""),
        ("陈年奶酪", 17, ["天然原制奶酪", "口感浓烈醇香", "补钙佳品"], ["食用前可室温回温15分钟", "密封防串味"], "")
    ]
    
    idx = 0
    for r in range(3):
        for c in range(3):
            name, days, feats, precs, img = initial_foods[idx]
            fridge.set_food_item(r, c, name, days, feats, precs, img)
            idx += 1

    def simulate_sensor():
        fridge.set_environment(3.9 + random.uniform(-0.2, 0.2), 67.4 + random.uniform(-1.0, 1.0))

    timer = QTimer()
    timer.timeout.connect(simulate_sensor)
    timer.start(3000)

    sys.exit(app.exec())



def create_ink_camera_placeholder() -> QPixmap:
    """用代码画一个水墨风格的摄像头占位图"""
    pixmap = QPixmap(400, 300)
    pixmap.fill(QColor("#F8E5BA")) # 宣纸色底
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # 画一个写意的毛笔圈（摄像头外框）
    pen = QPen(QColor(60, 60, 60, 180), 8)
    painter.setPen(pen)
    painter.drawEllipse(150, 80, 100, 100)

    # 画镜头内部（浓墨）
    painter.setBrush(QColor(30, 30, 30, 220))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(170, 100, 60, 60)

    # 画写意的支架线条
    painter.setPen(QPen(QColor(80, 80, 80, 150), 4))
    painter.drawLine(200, 180, 200, 240)
    painter.drawLine(160, 240, 240, 240)

    # 添加文字
    painter.setPen(QColor("#8C471E"))
    painter.setFont(QFont("KaiTi", 16, QFont.Weight.Bold))
    painter.drawText(0, 260, 400, 30, Qt.AlignmentFlag.AlignCenter, "— 虚席以待 鉴诸珍馐 —")
    
    painter.end()
    return pixmap


# ==========================================
# 视觉识别页面组件 (新中式风格)
# ==========================================
class VisionRecognizePage(QWidget):
    back_clicked = Signal() # 返回信号
    capture_clicked = Signal() # 抓拍信号

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("VisionPage")
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(20)

        # 1. 标题区域
        title_lbl = QLabel("❖ 鉴物 · 珍馐识真 ❖")
        title_lbl.setObjectName("VisionTitle")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_lbl)

        # 2. 图像显示区域 (核心)
        # 这里使用一个特殊的 Frame 来模拟木质画框
        self.image_frame = QFrame()
        self.image_frame.setObjectName("ImageCanvasFrame")
        self.image_frame.setFixedSize(500, 380) # 固定大小保持比例
        
        frame_layout = QVBoxLayout(self.image_frame)
        frame_layout.setContentsMargins(15, 15, 15, 15) # 留出“木框”厚度

        self.image_label = QLabel()
        self.image_label.setObjectName("InkImageDisplay")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # 初始显示占位图
        self.image_label.setPixmap(create_ink_camera_placeholder())
        
        frame_layout.addWidget(self.image_label)
        layout.addWidget(self.image_frame, 0, Qt.AlignmentFlag.AlignCenter)

        # 3. 识别结果简报 (可选，增强体验)
        self.result_label = QLabel("当前状态：静止。等待珍馐入鉴...")
        self.result_label.setObjectName("RecognizeResultText")
        self.result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result_label.setWordWrap(True)
        layout.addWidget(self.result_label)

        # 4. 底部按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(30)
        btn_layout.addStretch()

        self.capture_btn = QPushButton("📷 手动抓拍")
        self.capture_btn.setObjectName("InkBtn_Action")
        self.capture_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.capture_btn.clicked.connect(self.capture_clicked.emit)

        self.back_btn = QPushButton("◀ 返回主案")
        self.back_btn.setObjectName("InkBtn_Back")
        self.back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back_btn.clicked.connect(self.back_clicked.emit)

        btn_layout.addWidget(self.capture_btn)
        btn_layout.addWidget(self.back_btn)
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout)
        layout.addStretch()

        # 样式表：保持黑胡桃木、哑金、宣纸色风格
        self.setStyleSheet("""
            QWidget#VisionPage {
                background-color: #261A15; /* 深色黑胡桃木底色 */
            }
            QLabel#VisionTitle {
                font-family: "KaiTi", "Microsoft YaHei";
                font-size: 26px;
                font-weight: bold;
                color: #D4AF70; /* 哑金色 */
                letter-spacing: 3px;
                padding: 10px;
            }
            QFrame#ImageCanvasFrame {
                background-color: #4A2B18; /* 稍微浅一点的木框色 */
                border: 6px solid #1A100C; 
                border-radius: 8px;
                box-shadow: 5px 5px 15px rgba(0,0,0,0.5);
            }
            QLabel#InkImageDisplay {
                background-color: #F8E5BA; /* 宣纸色内屏 */
                border: 2px solid #2C1E16;
            }
            QLabel#RecognizeResultText {
                font-family: "SimSun";
                font-size: 16px;
                font-weight: bold;
                color: #BBBBBB;
                background-color: rgba(0,0,0,0.3);
                padding: 8px;
                border-radius: 4px;
            }
            QPushButton {
                font-family: "KaiTi";
                font-size: 18px;
                font-weight: bold;
                padding: 10px 25px;
                border-radius: 6px;
            }
            QPushButton#InkBtn_Action {
                background-color: #8B2500; /* 红褐色 */
                color: #FFD700;
                border: 2px solid #D4AF70;
            }
            QPushButton#InkBtn_Action:hover {
                background-color: #A03000;
            }
            QPushButton#InkBtn_Action:pressed {
                background-color: #6F1D00;
                padding-top: 11px; padding-left: 26px;
            }
            QPushButton#InkBtn_Back {
                background-color: transparent;
                color: #D4AF70;
                border: 2px solid #D4AF70;
            }
            QPushButton#InkBtn_Back:hover {
                background-color: rgba(212, 175, 112, 0.1);
            }
        """)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)          # 阴影模糊半径，越大越虚
        shadow.setXOffset(5)              # 水平偏移
        shadow.setYOffset(5)              # 垂直偏移
        shadow.setColor(QColor(0, 0, 0, 160)) # 阴影颜色（黑色，带透明度）

        # 2. 将阴影挂载到你的木框组件上
        self.image_frame.setGraphicsEffect(shadow)

    def update_viewer_image(self, pixmap: QPixmap):
        """外部调用：更新显示的图像（例如摄像头帧）"""
        if pixmap.isNull():
            return
        
        # 保持比例缩放以适应 Frame 内部
        target_w = self.image_label.width() - 4
        target_h = self.image_label.height() - 4
        scaled_pixmap = pixmap.scaled(target_w, target_h, 
                                    Qt.AspectRatioMode.KeepAspectRatio, 
                                    Qt.TransformationMode.SmoothTransformation)
        self.image_label.setPixmap(scaled_pixmap)

    def set_result_text(self, text: str):
        """外部调用：更新识别结果文字"""
        self.result_label.setText(f"鉴别结果：{text}")