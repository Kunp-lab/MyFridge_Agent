import sys
import random
import math
from datetime import datetime
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QFrame,
    QDialog,
    QPushButton,
    QStackedWidget,
    QTextEdit,
)
from PySide6.QtCore import Qt, QTimer, Signal, QTime, QPointF, QThread, QRectF
from PySide6.QtGui import (
    QFont,
    QColor,
    QPixmap,
    QPainter,
    QPainterPath,
    QLinearGradient,
    QPen,
    QBrush,
    QImage,
)
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

    return pixmap.scaled(
        128,
        128,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.FastTransformation,
    )


# ==========================================
# 待机屏幕组件 (纯代码绘制复古水墨表盘)
# ==========================================
class StandbyScreen(QWidget):
    clicked = Signal()  # 点击信号

    def __init__(self):
        super().__init__()
        self.setObjectName("StandbyScreen")
        self.current_time = QTime.currentTime()
        self.display_temp = 4.0
        self.display_humidity = 78.0
        self._energy_min_watt = 35.0
        self._energy_max_watt = 120.0
        self._energy_watt = random.uniform(self._energy_min_watt, 95.0)
        self._energy_target_watt = self._energy_watt
        self._ink_phase = random.uniform(0.0, math.pi * 2.0)
        self._energy_tick = 0
        self._energy_test_mode = False

        # 启动每秒更新的时钟
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_time)
        self.timer.start(1000)

        # 能耗模拟动画：随机目标值 + 平滑过渡，保持墨韵长度连续变化
        self.energy_timer = QTimer(self)
        self.energy_timer.timeout.connect(self._update_energy_simulation)
        self.energy_timer.start(50)

        # 简单节气计算逻辑 (仅作演示，实际应用可接入更复杂的农历库)
        self.solar_term = self._get_solar_term()

        # 样式：模拟深色木纹背景
        self.setStyleSheet(
            """
            QWidget#StandbyScreen {
                background-color: #D9D2C3;
            }
        """
        )

    def _get_solar_term(self):
        """简易节气推算（演示用）"""
        month = datetime.now().month
        day = datetime.now().day
        if not (1 <= month <= 12) or not (1 <= day <= 31):
            return "无效日期"

        # 春季
        if month == 2 and day >= 3 or month == 1 and day >= 20:  # 大寒 ~ 立春
            if month == 1 or (month == 2 and day < 19):
                return (
                    "立 春" if day >= 4 else "大 寒"
                )  # 更精确点可细分，但通常立春2/3-5
        # 下面用 elif 链式判断更清晰

        if month == 2:
            if day < 19:
                return "立 春"
            else:
                return "雨 水"  # 雨水 ≈ 2月18-20日

        elif month == 3:
            if day < 6:
                return "雨 水"
            elif day < 20:
                return "惊 蛰"  # 惊蛰 ≈ 3月5-7日
            else:
                return "春 分"  # 春分 ≈ 3月20-21日

        elif month == 4:
            if day < 5:
                return "春 分"
            elif day < 20:
                return "清 明"  # 清明 ≈ 4月4-6日
            else:
                return "谷 雨"  # 谷雨 ≈ 4月19-21日

        elif month == 5:
            if day < 6:
                return "谷 雨"
            elif day < 21:
                return "立 夏"  # 立夏 ≈ 5月5-7日
            else:
                return "小 满"  # 小满 ≈ 5月20-22日

        elif month == 6:
            if day < 6:
                return "小 满"
            elif day < 21:
                return "芒 种"  # 芒种 ≈ 6月5-7日
            else:
                return "夏 至"  # 夏至 ≈ 6月21-22日

        elif month == 7:
            if day < 8:
                return "夏 至"
            elif day < 23:
                return "小 暑"  # 小暑 ≈ 7月7-8日
            else:
                return "大 暑"  # 大暑 ≈ 7月22-24日

        elif month == 8:
            if day < 8:
                return "大 暑"
            elif day < 23:
                return "立 秋"  # 立秋 ≈ 8月7-8日
            else:
                return "处 暑"  # 处暑 ≈ 8月22-24日

        elif month == 9:
            if day < 8:
                return "处 暑"
            elif day < 23:
                return "白 露"  # 白露 ≈ 9月7-9日
            else:
                return "秋 分"  # 秋分 ≈ 9月22-24日

        elif month == 10:
            if day < 9:
                return "秋 分"
            elif day < 24:
                return "寒 露"  # 寒露 ≈ 10月8-9日
            else:
                return "霜 降"  # 霜降 ≈ 10月23-24日

        elif month == 11:
            if day < 8:
                return "霜 降"
            elif day < 23:
                return "立 冬"  # 立冬 ≈ 11月7-8日
            else:
                return "小 雪"  # 小雪 ≈ 11月22-23日

        elif month == 12:
            if day < 7:
                return "小 雪"
            elif day < 22:
                return "大 雪"  # 大雪 ≈ 12月6-8日
            else:
                return "冬 至"  # 冬至 ≈ 12月21-23日

        elif month == 1:
            if day < 6:
                return "冬 至"
            elif day < 20:
                return "小 寒"  # 小寒 ≈ 1月5-7日
            else:
                return "大 寒"  # 大寒 ≈ 1月19-21日

        return "未知节气"

    def update_time(self):
        self.current_time = QTime.currentTime()
        self.update()  # 触发重绘

    def set_environment(self, temp: float, humidity: float):
        self.display_temp = float(temp)
        self.display_humidity = float(humidity)
        self.update()

    def _clamp_energy(self, value: float) -> float:
        return max(self._energy_min_watt, min(self._energy_max_watt, value))

    def start_test_energy_ramp(self):
        self._energy_test_mode = True
        self._energy_target_watt = max(self._energy_target_watt, 110.0)

    def _energy_ratio(self) -> float:
        span = self._energy_max_watt - self._energy_min_watt
        if span <= 0:
            return 0.0
        return (self._energy_watt - self._energy_min_watt) / span

    def _temp_ratio(self) -> float:
        min_temp = -2.0
        max_temp = 10.0
        span = max_temp - min_temp
        if span <= 0:
            return 0.0
        value = (self.display_temp - min_temp) / span
        return max(0.0, min(1.0, value))

    def _humidity_ratio(self) -> float:
        min_humidity = 35.0
        max_humidity = 95.0
        span = max_humidity - min_humidity
        if span <= 0:
            return 0.0
        value = (self.display_humidity - min_humidity) / span
        return max(0.0, min(1.0, value))

    def _update_energy_simulation(self):
        self._energy_tick += 1
        self._ink_phase = (self._ink_phase + 0.065) % (math.pi * 2.0)

        # 每约 4 秒重新生成一个迷你冰箱合理区间内的随机能耗目标
        if self._energy_tick % 80 == 0:
            if self._energy_test_mode:
                self._energy_target_watt = max(self._energy_target_watt, 110.0)
            else:
                self._energy_target_watt = random.uniform(
                    self._energy_min_watt, 95.0
                )

        # 通过一阶平滑逼近目标，避免突跳
        ramp_factor = 0.16 if self._energy_test_mode else 0.045
        self._energy_watt += (self._energy_target_watt - self._energy_watt) * ramp_factor
        micro = math.sin(self._energy_tick * 0.17) * 0.08
        self._energy_watt = self._clamp_energy(self._energy_watt + micro)

        if self._energy_test_mode and self._energy_watt >= 105.0:
            self._energy_test_mode = False
            self._energy_target_watt = max(self._energy_min_watt, min(95.0, self._energy_watt))

        self.update()

    def _draw_energy_ink_ring(self, painter: QPainter, center: QPointF, radius: float):
        top_angle = -math.pi / 2.0
        gap_half = math.radians(11.0)  # 12 点方向断开约 22°
        start_angle = top_angle  # 三条墨韵都从 12 点方向开始
        power_ratio = self._energy_ratio()
        temp_ratio = self._temp_ratio()
        humidity_ratio = self._humidity_ratio()

        power_text_color = QColor(108, 95, 72, 230)
        temp_text_color = QColor(123, 82, 52, 235)  # 褐色
        humidity_text_color = QColor(66, 110, 158, 235)

        # 功耗保留原先蓝灰调，根据功耗深浅变化
        power_ring_color = QColor(
            int(132 + (56 - 132) * power_ratio),
            int(146 + (72 - 146) * power_ratio),
            int(158 + (88 - 158) * power_ratio),
        )

        def draw_metric_ring(
            ring_radius: float,
            ratio: float,
            color: QColor,
            phase_shift: float,
            size_scale: float,
        ):
            arc_ratio = 0.50 + ratio * 0.25
            span_angle = (math.pi * 2.0) * arc_ratio
            steps = max(120, int(300 * arc_ratio))
            alpha_low = 44 + int(32 * ratio)
            alpha_high = 148 + int(72 * ratio)

            painter.save()
            painter.setPen(Qt.PenStyle.NoPen)
            for i in range(steps):
                t = i / float(max(steps - 1, 1))
                theta = start_angle + t * span_angle
                diff_top = abs(
                    math.atan2(
                        math.sin(theta - top_angle),
                        math.cos(theta - top_angle),
                    )
                )
                if diff_top < gap_half:
                    continue

                wave = math.sin(theta * 3.2 + self._ink_phase + phase_shift) * 2.0
                ripple = math.cos(theta * 6.8 - self._ink_phase * 0.65 + phase_shift) * 1.0
                rr = ring_radius + wave + ripple

                pressure = 0.35 + 0.65 * math.sin(math.pi * t)
                size = (
                    3.6 + 2.8 * (0.5 + 0.5 * math.sin(theta * 4.7 + self._ink_phase + phase_shift))
                ) * pressure * size_scale

                x = center.x() + rr * math.cos(theta)
                y = center.y() + rr * math.sin(theta)
                alpha = int(
                    (
                        alpha_low
                        + (alpha_high - alpha_low)
                        * (0.5 + 0.5 * math.cos(theta * 2.1 + self._ink_phase + phase_shift))
                    )
                    * pressure
                )
                alpha = max(12, min(220, alpha))
                painter.setBrush(QColor(color.red(), color.green(), color.blue(), alpha))
                painter.drawEllipse(QPointF(x, y), size, size * 0.92)

                if i % 24 == 0 and pressure > 0.44:
                    splash_alpha = max(14, min(170, int(alpha * 0.74)))
                    painter.setBrush(
                        QColor(
                            max(0, color.red() - 14),
                            max(0, color.green() - 14),
                            max(0, color.blue() - 14),
                            splash_alpha,
                        )
                    )
                    sx = x + math.sin(theta * 8.8 + self._ink_phase + phase_shift) * 4.8
                    sy = y + math.cos(theta * 8.1 - self._ink_phase - phase_shift) * 4.8
                    painter.drawEllipse(QPointF(sx, sy), size * 0.50, size * 0.50)
            painter.restore()

        # 三条墨韵圈：都从 12 点起步、同向
        draw_metric_ring(radius + 18, power_ratio, power_ring_color, 0.0, 1.30)
        draw_metric_ring(radius + 31, temp_ratio, temp_text_color, 1.1, 1.18)
        draw_metric_ring(radius + 44, humidity_ratio, humidity_text_color, 2.1, 1.12)

        # 在 12 点断口区域展示英文功耗
        label_text = f"POWER {self._energy_watt:.0f}W"
        painter.setPen(power_text_color)
        painter.setFont(QFont("Microsoft YaHei", max(11, int(radius * 0.044)), QFont.Weight.DemiBold))
        label_w = int(radius * 0.78)
        label_h = int(max(24, radius * 0.12))
        label_x = int(center.x() - label_w / 2)
        label_y = int(center.y() - radius - 40)
        painter.drawText(
            label_x,
            label_y,
            label_w,
            label_h,
            Qt.AlignmentFlag.AlignCenter,
            label_text,
        )

        # 以同样方式显示温湿度：温度褐色、湿度蓝色
        sensor_font = QFont(
            "Microsoft YaHei",
            max(10, int(radius * 0.035)),
            QFont.Weight.DemiBold,
        )
        painter.setFont(sensor_font)
        sensor_w = int(radius * 0.56)
        sensor_h = int(max(22, radius * 0.1))
        sensor_y = int(center.y() - radius - 8)

        temp_text = f"TEMP {self.display_temp:.1f}°C"
        temp_cx = center.x() - radius * 0.48
        temp_x = int(temp_cx - sensor_w / 2)
        painter.setPen(temp_text_color)
        painter.drawText(
            temp_x,
            sensor_y,
            sensor_w,
            sensor_h,
            Qt.AlignmentFlag.AlignCenter,
            temp_text,
        )

        humidity_text = f"HUMID {self.display_humidity:.1f}%"
        hum_cx = center.x() + radius * 0.48
        hum_x = int(hum_cx - sensor_w / 2)
        painter.setPen(humidity_text_color)
        painter.drawText(
            hum_x,
            sensor_y,
            sensor_w,
            sensor_h,
            Qt.AlignmentFlag.AlignCenter,
            humidity_text,
        )

    def paintEvent(self, event):
        """核心：用代码画出水墨山水表盘"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width, height = self.width(), self.height()

        # 1. 绘制右上角的数字时间和日期
        painter.setPen(QColor("#D4AF70"))  # 哑金色
        painter.setFont(QFont("Microsoft YaHei", 24, QFont.Weight.Bold))
        time_str = self.current_time.toString("HH:mm")
        date_str = datetime.now().strftime("%m月%d日")
        painter.drawText(
            width - 250,
            40,
            220,
            40,
            Qt.AlignmentFlag.AlignRight,
            f"{time_str} · {date_str}",
        )

        # 绘制节气汉字
        painter.setFont(QFont("KaiTi", 18, QFont.Weight.Bold))
        painter.drawText(
            width - 250, 80, 220, 30, Qt.AlignmentFlag.AlignRight, self.solar_term
        )

        # 2. 绘制中央水墨圆盘
        center = QPointF(width / 2, height / 2)
        radius = min(width, height) * 0.38

        # 2.1 绘制时钟外圈蓝灰墨韵，弧长由能耗值驱动
        self._draw_energy_ink_ring(painter, center, radius + 22)

        # 黄铜外边框
        pen = QPen(QColor("#9E7A45"), 12)
        painter.setPen(pen)
        painter.setBrush(QColor("#E8ECEC"))  # 表盘底色 (浅青白)
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
        path1.quadTo(
            center.x() - radius * 0.5, center.y() - 50, center.x(), center.y() + 10
        )
        path1.quadTo(
            center.x() + radius * 0.5,
            center.y() - 80,
            center.x() + radius,
            center.y() + 30,
        )
        path1.lineTo(center.x() + radius, center.y() + radius)
        path1.lineTo(center.x() - radius, center.y() + radius)
        painter.fillPath(path1, QColor(100, 110, 115, 120))

        # 前景山 (浓墨)
        path2 = QPainterPath()
        path2.moveTo(center.x() - radius, center.y() + 60)
        path2.quadTo(
            center.x() - radius * 0.3,
            center.y() - 10,
            center.x() + radius * 0.2,
            center.y() + 50,
        )
        path2.quadTo(
            center.x() + radius * 0.7,
            center.y() - 30,
            center.x() + radius,
            center.y() + 70,
        )
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
            dizhi = [
                "子",
                "丑",
                "寅",
                "卯",
                "辰",
                "巳",
                "午",
                "未",
                "申",
                "酉",
                "戌",
                "亥",
            ]
            text_x = center.x() + (radius - 50) * math.cos(angle)
            text_y = center.y() + (radius - 50) * math.sin(angle)
            painter.drawText(
                int(text_x - 10),
                int(text_y - 10),
                20,
                20,
                Qt.AlignmentFlag.AlignCenter,
                dizhi[i],
            )

        # 5. 绘制时钟指针
        hour = self.current_time.hour() % 12
        minute = self.current_time.minute()
        second = self.current_time.second()

        # 分针 (长)
        painter.save()
        painter.translate(center)
        painter.rotate(minute * 6 + second * 0.1)
        painter.setPen(
            QPen(QColor("#2C1E16"), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        )
        painter.drawLine(0, 15, 0, int(-radius * 0.7))
        painter.restore()

        # 时针 (短粗)
        painter.save()
        painter.translate(center)
        painter.rotate(hour * 30 + minute * 0.5)
        painter.setPen(
            QPen(QColor("#5C4A3D"), 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        )
        painter.drawLine(0, 10, 0, int(-radius * 0.45))
        painter.restore()

        # 秒针 (红)
        painter.save()
        painter.translate(center)
        painter.rotate(second * 6)
        painter.setPen(QPen(QColor("#8B2500"), 2))
        painter.drawLine(0, 20, 0, int(-radius * 0.8))
        painter.setBrush(QColor("#8B2500"))
        painter.drawEllipse(QPointF(0, 0), 6, 6)  # 中心红点
        painter.restore()

        # 6. 底部提示语
        painter.setPen(QColor("#888888"))
        painter.setFont(QFont("KaiTi", 14))
        painter.drawText(
            0,
            height - 60,
            width,
            30,
            Qt.AlignmentFlag.AlignCenter,
            "— 点击任意处 唤醒食盒 —",
        )

    def mouseReleaseEvent(self, event):
        """重写鼠标点击事件：点击即切换到主界面"""
        self.clicked.emit()
        super().mouseReleaseEvent(event)


# ==========================================
# 详情弹窗组件
# ==========================================
class FoodDetailDialog(QDialog):
    def __init__(
        self, name: str, features: list, precautions: list, image_path: str, parent=None
    ):
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
            pixmap = pixmap.scaled(
                128,
                128,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )

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

        self.setStyleSheet(
            """
            QFrame#DialogFrame {
                background-color: #E6C687;
                border: 6px solid #4A2B18; 
                border-top-color: #6B4126;
                border-left-color: #6B4126;
                border-bottom-color: #2F190D;
                border-right-color: #2F190D;
            }
            QLabel#DialogTitle {
                background-color: #7C6244;
                color: #F3E2C1;
                font-family: "Microsoft YaHei", "SimSun";
                font-size: 19px;
                font-weight: 900;
                border: 4px solid #221D18;
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
                font-family: "Microsoft YaHei", "KaiTi";
                font-size: 16px;
                font-weight: bold;
                color: #241D17;
                background-color: #C9A06D;
                padding: 4px 8px;
                border: 2px solid #4A2B18;
            }
            QLabel#DetailText {
                font-family: "Microsoft YaHei", "SimSun";
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
        """
        )


class LoadingSpinner(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_timeout)
        self.setFixedSize(30, 30)
        self.hide()

    def _on_timeout(self):
        self._angle = (self._angle + 24) % 360
        self.update()

    def start(self):
        if not self._timer.isActive():
            self._timer.start(50)
        self.show()
        self.update()

    def stop(self):
        self._timer.stop()
        self.hide()

    def paintEvent(self, event):
        if not self.isVisible():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(4, 4, self.width() - 8, self.height() - 8)
        track_pen = QPen(QColor(120, 100, 76, 70), 3.0)
        track_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(track_pen)
        painter.drawArc(rect, 0, 360 * 16)

        active_pen = QPen(QColor(158, 124, 84, 230), 3.6)
        active_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(active_pen)
        painter.drawArc(rect, int((90 - self._angle) * 16), int(-120 * 16))


class RecommendDialog(QDialog):
    exit_requested = Signal()

    def __init__(self, content: str, parent=None, is_loading: bool = False):
        super().__init__(parent)
        self.setWindowTitle("推荐")
        self.resize(620, 520)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._init_ui(content, is_loading)

    def _init_ui(self, content: str, is_loading: bool):
        main_frame = QFrame(self)
        main_frame.setGeometry(0, 0, 620, 520)
        main_frame.setObjectName("RecommendDialogFrame")

        layout = QVBoxLayout(main_frame)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header_layout = QHBoxLayout()
        title_label = QLabel("❖ 推 荐 ❖")
        title_label.setObjectName("RecommendDialogTitle")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        close_btn = QPushButton("✖")
        close_btn.setObjectName("CloseBtn")
        close_btn.setFixedSize(36, 36)
        close_btn.clicked.connect(self.accept)

        header_layout.addWidget(title_label, stretch=1)
        header_layout.addWidget(close_btn)
        layout.addLayout(header_layout)

        self.hint_label = QLabel("已为你整理当前库存对应的营养概括与推荐食谱")
        self.hint_label.setObjectName("RecommendHintLabel")
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.hint_label)

        spinner_row = QHBoxLayout()
        spinner_row.addStretch()
        self.loading_spinner = LoadingSpinner()
        spinner_row.addWidget(self.loading_spinner)
        spinner_row.addStretch()
        layout.addLayout(spinner_row)

        self.content_edit = QTextEdit()
        self.content_edit.setObjectName("RecommendContentEdit")
        self.content_edit.setReadOnly(True)
        self.content_edit.setPlainText(content)
        layout.addWidget(self.content_edit, stretch=1)

        footer_layout = QHBoxLayout()
        footer_layout.addStretch()

        exit_btn = QPushButton("退出")
        exit_btn.setObjectName("RecommendExitBtn")
        exit_btn.setFixedSize(120, 42)
        exit_btn.clicked.connect(self._on_exit_clicked)
        footer_layout.addWidget(exit_btn)
        footer_layout.addSpacing(12)

        confirm_btn = QPushButton("我知道了")
        confirm_btn.setObjectName("RecommendConfirmBtn")
        confirm_btn.setFixedSize(120, 42)
        confirm_btn.clicked.connect(self.accept)
        footer_layout.addWidget(confirm_btn)
        footer_layout.addStretch()
        layout.addLayout(footer_layout)

        self.setStyleSheet(
            """
            QFrame#RecommendDialogFrame {
                background-color: #E6C687;
                border: 6px solid #4A2B18;
                border-top-color: #6B4126;
                border-left-color: #6B4126;
                border-bottom-color: #2F190D;
                border-right-color: #2F190D;
            }
            QLabel#RecommendDialogTitle {
                background-color: #7C6244;
                color: #F3E2C1;
                font-family: "Microsoft YaHei", "SimSun";
                font-size: 19px;
                font-weight: 900;
                border: 4px solid #221D18;
                padding: 6px;
                letter-spacing: 2px;
            }
            QLabel#RecommendHintLabel {
                font-family: "Microsoft YaHei", "KaiTi";
                font-size: 15px;
                font-weight: bold;
                color: #4A2B18;
            }
            QTextEdit#RecommendContentEdit {
                background-color: #1D1F1F;
                color: #E7D6B7;
                border: 4px solid #4A2B18;
                border-top-color: #151211;
                border-left-color: #151211;
                border-bottom-color: #C29A6A;
                border-right-color: #C29A6A;
                font-family: "Microsoft YaHei", "SimSun";
                font-size: 15px;
                line-height: 1.5;
                padding: 10px;
            }
            QPushButton#RecommendConfirmBtn {
                background-color: #B68A58;
                color: #211913;
                font-family: "Microsoft YaHei", "KaiTi";
                font-size: 16px;
                font-weight: bold;
                border: 4px solid #4A2B18;
                border-top-color: #D9B07C;
                border-left-color: #D9B07C;
            }
            QPushButton#RecommendConfirmBtn:pressed {
                border-top-color: #2F190D;
                border-left-color: #2F190D;
                background-color: #8F6A42;
            }
            QPushButton#RecommendExitBtn {
                background-color: #8F4B3E;
                color: #F3E2C1;
                font-family: "Microsoft YaHei", "KaiTi";
                font-size: 16px;
                font-weight: bold;
                border: 4px solid #4A2B18;
                border-top-color: #B66C5E;
                border-left-color: #B66C5E;
            }
            QPushButton#RecommendExitBtn:pressed {
                border-top-color: #2F190D;
                border-left-color: #2F190D;
                background-color: #6E3A31;
            }
        """
        )

        self.set_loading(is_loading)

    def set_content(self, content: str):
        self.content_edit.setPlainText(content)

    def _on_exit_clicked(self):
        self.exit_requested.emit()
        self.accept()

    def set_loading(self, is_loading: bool):
        if is_loading:
            self.hint_label.setText("AI 正在推理中，请稍等...")
            self.loading_spinner.start()
        else:
            self.hint_label.setText("已为你整理当前库存对应的营养概括与推荐食谱")
            self.loading_spinner.stop()


class FoodRecognizeDialog(QDialog):
    exit_requested = Signal()

    def __init__(self, content: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("食材识别结果")
        self.resize(560, 420)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._init_ui(content)

    def _init_ui(self, content: str):
        main_frame = QFrame(self)
        main_frame.setGeometry(0, 0, 560, 420)
        main_frame.setObjectName("FoodRecognizeDialogFrame")

        layout = QVBoxLayout(main_frame)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header_layout = QHBoxLayout()
        title_label = QLabel("❖ 食 材 识 别 ❖")
        title_label.setObjectName("FoodRecognizeDialogTitle")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        close_btn = QPushButton("✖")
        close_btn.setObjectName("CloseBtn")
        close_btn.setFixedSize(36, 36)
        close_btn.clicked.connect(self.accept)

        header_layout.addWidget(title_label, stretch=1)
        header_layout.addWidget(close_btn)
        layout.addLayout(header_layout)

        hint_label = QLabel("以下为本次识别进度与推荐放置位置")
        hint_label.setObjectName("FoodRecognizeHintLabel")
        hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint_label)

        self.content_edit = QTextEdit()
        self.content_edit.setObjectName("FoodRecognizeContentEdit")
        self.content_edit.setReadOnly(True)
        self.content_edit.setPlainText(content)
        layout.addWidget(self.content_edit, stretch=1)

        footer_layout = QHBoxLayout()
        footer_layout.addStretch()

        exit_btn = QPushButton("退出")
        exit_btn.setObjectName("FoodRecognizeExitBtn")
        exit_btn.setFixedSize(120, 42)
        exit_btn.clicked.connect(self._on_exit_clicked)
        footer_layout.addWidget(exit_btn)
        footer_layout.addSpacing(12)

        confirm_btn = QPushButton("知道了")
        confirm_btn.setObjectName("FoodRecognizeConfirmBtn")
        confirm_btn.setFixedSize(120, 42)
        confirm_btn.clicked.connect(self.accept)
        footer_layout.addWidget(confirm_btn)
        footer_layout.addStretch()
        layout.addLayout(footer_layout)

        self.setStyleSheet(
            """
            QFrame#FoodRecognizeDialogFrame {
                background-color: #E6C687;
                border: 6px solid #4A2B18;
                border-top-color: #6B4126;
                border-left-color: #6B4126;
                border-bottom-color: #2F190D;
                border-right-color: #2F190D;
            }
            QLabel#FoodRecognizeDialogTitle {
                background-color: #7C6244;
                color: #F3E2C1;
                font-family: "Microsoft YaHei", "SimSun";
                font-size: 19px;
                font-weight: 900;
                border: 4px solid #221D18;
                padding: 6px;
                letter-spacing: 2px;
            }
            QLabel#FoodRecognizeHintLabel {
                font-family: "Microsoft YaHei", "KaiTi";
                font-size: 15px;
                font-weight: bold;
                color: #4A2B18;
            }
            QTextEdit#FoodRecognizeContentEdit {
                background-color: #1D1F1F;
                color: #E7D6B7;
                border: 4px solid #4A2B18;
                border-top-color: #151211;
                border-left-color: #151211;
                border-bottom-color: #C29A6A;
                border-right-color: #C29A6A;
                font-family: "Microsoft YaHei", "SimSun";
                font-size: 15px;
                line-height: 1.5;
                padding: 10px;
            }
            QPushButton#FoodRecognizeConfirmBtn {
                background-color: #B68A58;
                color: #211913;
                font-family: "Microsoft YaHei", "KaiTi";
                font-size: 16px;
                font-weight: bold;
                border: 4px solid #4A2B18;
                border-top-color: #D9B07C;
                border-left-color: #D9B07C;
            }
            QPushButton#FoodRecognizeConfirmBtn:pressed {
                border-top-color: #2F190D;
                border-left-color: #2F190D;
                background-color: #8F6A42;
            }
            QPushButton#FoodRecognizeExitBtn {
                background-color: #8F4B3E;
                color: #F3E2C1;
                font-family: "Microsoft YaHei", "KaiTi";
                font-size: 16px;
                font-weight: bold;
                border: 4px solid #4A2B18;
                border-top-color: #B66C5E;
                border-left-color: #B66C5E;
            }
            QPushButton#FoodRecognizeExitBtn:pressed {
                border-top-color: #2F190D;
                border-left-color: #2F190D;
                background-color: #6E3A31;
            }
        """
        )

    def set_content(self, content: str):
        self.content_edit.setPlainText(content)

    def _on_exit_clicked(self):
        self.exit_requested.emit()
        self.accept()


class TongueHealthDialog(QDialog):
    exit_requested = Signal()

    def __init__(self, content: str, parent=None, is_loading: bool = False):
        super().__init__(parent)
        self.setWindowTitle("健康检测结果")
        self.resize(560, 420)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._init_ui(content, is_loading)

    def _init_ui(self, content: str, is_loading: bool):
        main_frame = QFrame(self)
        main_frame.setGeometry(0, 0, 560, 420)
        main_frame.setObjectName("TongueHealthDialogFrame")

        layout = QVBoxLayout(main_frame)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header_layout = QHBoxLayout()
        title_label = QLabel("❖ 健 康 检 测 结 果 ❖")
        title_label.setObjectName("TongueHealthDialogTitle")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        close_btn = QPushButton("✖")
        close_btn.setObjectName("CloseBtn")
        close_btn.setFixedSize(36, 36)
        close_btn.clicked.connect(self.accept)

        header_layout.addWidget(title_label, stretch=1)
        header_layout.addWidget(close_btn)
        layout.addLayout(header_layout)

        self.hint_label = QLabel("以下为本次舌诊检测分析结果（仅供生活方式参考）")
        self.hint_label.setObjectName("TongueHealthHintLabel")
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.hint_label)

        spinner_row = QHBoxLayout()
        spinner_row.addStretch()
        self.loading_spinner = LoadingSpinner()
        spinner_row.addWidget(self.loading_spinner)
        spinner_row.addStretch()
        layout.addLayout(spinner_row)

        self.content_edit = QTextEdit()
        self.content_edit.setObjectName("TongueHealthContentEdit")
        self.content_edit.setReadOnly(True)
        self.content_edit.setPlainText(content)
        layout.addWidget(self.content_edit, stretch=1)

        footer_layout = QHBoxLayout()
        footer_layout.addStretch()

        exit_btn = QPushButton("退出")
        exit_btn.setObjectName("TongueHealthExitBtn")
        exit_btn.setFixedSize(120, 42)
        exit_btn.clicked.connect(self._on_exit_clicked)
        footer_layout.addWidget(exit_btn)
        footer_layout.addSpacing(12)

        confirm_btn = QPushButton("知道了")
        confirm_btn.setObjectName("TongueHealthConfirmBtn")
        confirm_btn.setFixedSize(120, 42)
        confirm_btn.clicked.connect(self.accept)
        footer_layout.addWidget(confirm_btn)
        footer_layout.addStretch()
        layout.addLayout(footer_layout)

        self.setStyleSheet(
            """
            QFrame#TongueHealthDialogFrame {
                background-color: #E6C687;
                border: 6px solid #4A2B18;
                border-top-color: #6B4126;
                border-left-color: #6B4126;
                border-bottom-color: #2F190D;
                border-right-color: #2F190D;
            }
            QLabel#TongueHealthDialogTitle {
                background-color: #7C6244;
                color: #F3E2C1;
                font-family: "Microsoft YaHei", "SimSun";
                font-size: 19px;
                font-weight: 900;
                border: 4px solid #221D18;
                padding: 6px;
                letter-spacing: 2px;
            }
            QLabel#TongueHealthHintLabel {
                font-family: "Microsoft YaHei", "KaiTi";
                font-size: 15px;
                font-weight: bold;
                color: #4A2B18;
            }
            QTextEdit#TongueHealthContentEdit {
                background-color: #1D1F1F;
                color: #E7D6B7;
                border: 4px solid #4A2B18;
                border-top-color: #151211;
                border-left-color: #151211;
                border-bottom-color: #C29A6A;
                border-right-color: #C29A6A;
                font-family: "Microsoft YaHei", "SimSun";
                font-size: 15px;
                line-height: 1.5;
                padding: 10px;
            }
            QPushButton#TongueHealthConfirmBtn {
                background-color: #B68A58;
                color: #211913;
                font-family: "Microsoft YaHei", "KaiTi";
                font-size: 16px;
                font-weight: bold;
                border: 4px solid #4A2B18;
                border-top-color: #D9B07C;
                border-left-color: #D9B07C;
            }
            QPushButton#TongueHealthConfirmBtn:pressed {
                border-top-color: #2F190D;
                border-left-color: #2F190D;
                background-color: #8F6A42;
            }
            QPushButton#TongueHealthExitBtn {
                background-color: #8F4B3E;
                color: #F3E2C1;
                font-family: "Microsoft YaHei", "KaiTi";
                font-size: 16px;
                font-weight: bold;
                border: 4px solid #4A2B18;
                border-top-color: #B66C5E;
                border-left-color: #B66C5E;
            }
            QPushButton#TongueHealthExitBtn:pressed {
                border-top-color: #2F190D;
                border-left-color: #2F190D;
                background-color: #6E3A31;
            }
        """
        )

        self.set_loading(is_loading)

    def set_content(self, content: str):
        self.content_edit.setPlainText(content)

    def _on_exit_clicked(self):
        self.exit_requested.emit()
        self.accept()

    def set_loading(self, is_loading: bool):
        if is_loading:
            self.hint_label.setText("AI 正在推理中，请稍等...")
            self.loading_spinner.start()
        else:
            self.hint_label.setText("以下为本次舌诊检测分析结果（仅供生活方式参考）")
            self.loading_spinner.stop()


# ==========================================
# 食物卡片组件 (包含【毛笔一笔画圈】的核心算法)
# ==========================================
class FoodCard(QFrame):
    clicked = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CardFrame")
        self.setFixedSize(180, 130)
        self.food_data = {
            "name": "",
            "days_left": -1,
            "features": [],
            "precautions": [],
            "image_path": "",
        }
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

        self.setStyleSheet(
            """
            QFrame#CardFrame {
                background-color: #E8E0D0;
                border: 2px solid #B08A5B;
                border-radius: 14px;
            }
            QFrame#CardFrame:hover {
                background-color: #F1E8D7;
                border: 2px solid #C99A63;
            }
            QLabel {
                border: 2px solid #A88C69;
                border-radius: 14px;
                background-color: rgba(248, 242, 230, 0.96);
                font-family: "Microsoft YaHei";
                font-weight: bold;
                font-size: 15px;
                color: #5A4430;
            }
            QLabel#PillLabel_Name { color: #4B3525; }
        """
        )

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

            pressure = (
                math.sin(t * math.pi / arc_length)
                if arc_length <= 1.0
                else math.sin(t * math.pi)
            )
            pressure = max(0.1, pressure)
            current_thickness = base_thickness * pressure * random.uniform(0.6, 1.4)

            painter.drawEllipse(
                int(x - current_thickness / 2),
                int(y - current_thickness / 2),
                int(current_thickness),
                int(current_thickness),
            )

            if random.random() < splatter_chance:
                sx = x + random.uniform(-base_thickness * 3, base_thickness * 3)
                sy = y + random.uniform(-base_thickness * 3, base_thickness * 3)
                s_size = random.uniform(1, current_thickness * 0.6)

                sp_color = QColor(color)
                sp_color.setAlpha(int(color.alpha() * 0.5))
                painter.setBrush(sp_color)
                painter.drawEllipse(int(sx), int(sy), int(s_size), int(s_size))
                painter.setBrush(color)

        painter.end()
        random.seed()

    def update_data(
        self,
        name: str,
        days_left: int,
        features: list,
        precautions: list,
        image_path: str,
    ):
        display_name = name.strip() if isinstance(name, str) else ""
        has_food = bool(display_name)
        if not has_food:
            display_name = "虚位以待"

        normalized_days_left = days_left if isinstance(days_left, int) else -1

        self.food_data = {
            "name": display_name,
            "days_left": normalized_days_left,
            "features": features,
            "precautions": precautions,
            "image_path": image_path,
        }
        self.name_label.setText(display_name)

        if not has_food:
            self.expire_label.setText("—")
            self.expire_label.setStyleSheet("color: #90857A; border-color: #5D5246;")
        elif normalized_days_left <= 0:
            self.expire_label.setText("已经过期")
            self.expire_label.setStyleSheet("color: #D36B5D; border-color: #A54B3D;")
        elif normalized_days_left <= 3:
            self.expire_label.setText(f"仅剩 {normalized_days_left} 日")
            self.expire_label.setStyleSheet("color: #F0B766; border-color: #C88A3C;")
        else:
            self.expire_label.setText(f"尚余 {normalized_days_left} 日")
            self.expire_label.setStyleSheet("color: #B7C8B3; border-color: #6E7A68;")

        ring_days_left = -1 if not has_food else max(0, normalized_days_left)
        self._generate_brush_circle(display_name, ring_days_left)
        self.update()

    def paintEvent(self, arg__1):
        super().paintEvent(arg__1)
        if self.ink_pixmap:
            painter = QPainter(self)
            painter.drawPixmap(0, 0, self.ink_pixmap)
            painter.end()

    def mouseReleaseEvent(self, event):
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self.food_data["name"] != "虚位以待"
        ):
            self.clicked.emit(self.food_data)
        super().mouseReleaseEvent(event)


# ==========================================
# 主窗口 (搭载 QStackedWidget 实现页面切换)
# ==========================================
class SmartFridgeUI(QMainWindow):
    def __init__(self, node):
        super().__init__()
        self.setWindowTitle("冰鉴 · 珍馐录")
        self.resize(800, 1024)  # 稍微调大一点以便容纳新按钮
        self.food_grids = []
        self.food_recognition_dialog = None
        self.recommend_dialog = None
        self.tongue_health_dialog = None
        self.food_recognition_loading = False
        self.recommend_loading = False
        self.tongue_health_loading = False
        self.mock_temp = 4.0
        self.mock_humidity = 78.0
        self.is_test = True  # 开机 10 秒后是否展示测试弹窗

        # 使用 StackedWidget 来管理 3 个页面
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        # 按顺序初始化并添加页面
        self._init_standby_page()  # 索引 0
        self._init_main_page()  # 索引 1
        self._init_vision_page()  # 索引 2 (新增)

        self._apply_global_style()
        self._init_mock_environment_timer()
        self._start_test_timer()

        self._start_ros2_thread(node=node)
        # 默认显示待机页面 (索引 0)，并通知电机开始运动
        self._switch_to_page(0, force_standby_publish=True)
        self.showFullScreen()

    def _init_standby_page(self):
        """初始化待机页面"""
        self.standby_page = StandbyScreen()
        # 绑定点击事件，切换到主页面 (索引 1)
        self.standby_page.clicked.connect(
            lambda: self._switch_to_page(1)
        )
        self.stacked_widget.addWidget(self.standby_page)

    def _init_main_page(self):
        """初始化主页面 (修改：标题栏增加“鉴物”按钮)"""
        self.main_page = QWidget()
        self.main_page.setObjectName("MainPage")
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

        BTN_WIDTH = 90
        BTN_HEIGHT = 30

        self.exit_btn = QPushButton("▶ 退出")
        self.exit_btn.setObjectName("ExitBtn")
        self.exit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.exit_btn.setFixedWidth(BTN_WIDTH)
        self.exit_btn.setFixedHeight(BTN_HEIGHT)
        # 绑定点击事件：直接关闭主窗口
        self.exit_btn.clicked.connect(self.close)

        self.return_btn = QPushButton("▶ 待机")
        self.return_btn.setObjectName("ReturnBtn")
        self.return_btn.setFixedWidth(BTN_WIDTH)
        self.return_btn.setFixedHeight(BTN_HEIGHT)
        self.return_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.return_btn.clicked.connect(lambda: self._switch_to_page(0))

        # 新增：“鉴物”按钮
        self.vision_nav_btn = QPushButton("▶ 功能")
        self.vision_nav_btn.setObjectName(
            "VisionNavBtn"
        )  # 使用不同的标识符以便单独贴样式
        self.vision_nav_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        # 点击切换到视觉页面 (索引 2)
        self.vision_nav_btn.setFixedHeight(BTN_HEIGHT)
        self.vision_nav_btn.setFixedWidth(BTN_WIDTH)
        self.vision_nav_btn.clicked.connect(
            lambda: self._switch_to_page(2)
        )

        nav_btn_layout.addWidget(self.exit_btn)
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

        self.status_label = QLabel("")
        self.status_label.setObjectName("StatusText")
        self.status_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
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
        self.vision_page.back_clicked.connect(
            lambda: self._switch_to_page(1)
        )
        # 抓拍按钮事件 (暂时只打印日志，后续可以对接摄像头逻辑)
        self.vision_page.capture_clicked.connect(self._handle_manual_capture)
        self.vision_page.tongueai_clicked.connect(self._handle_tongueai)
        self.vision_page.season_clicked.connect(self._handle_season)

        self.stacked_widget.addWidget(self.vision_page)

    def _publish_qdriver_control(self, enabled: bool):
        if not hasattr(self, "ros_worker") or self.ros_worker is None:
            return
        if not getattr(self.ros_worker, "node", None):
            return
        self.ros_worker.node.PublishQdriverControl(enabled)

    def _switch_to_page(self, page_index: int, force_standby_publish: bool = False):
        prev_index = self.stacked_widget.currentIndex()
        if prev_index == 0 and page_index != 0:
            self._publish_qdriver_control(False)

        self.stacked_widget.setCurrentIndex(page_index)

        if page_index == 0 and (force_standby_publish or prev_index != 0):
            self._publish_qdriver_control(True)
            if hasattr(self, "ros_worker") and self.ros_worker and self.ros_worker.node:
                self.ros_worker.node.PublishStandbyUart()

    def _handle_manual_capture(self):
        self.vision_page.set_result_text("已接收图像，正在准备识别......")
        self.ros_worker.node.reason_flag.emit()
        # 后续你可以这里调用摄像头拍照并更新 VisionPage 的图片

    def _handle_tongueai(self):
        self.vision_page.set_result_text("AI 正在推理中，请稍等......")
        self._show_tongue_health_dialog("AI 正在推理中，请稍等...", loading=True)
        self.ros_worker.node.StartTongueDiagnosis()

    def _handle_season(self):
        self.vision_page.set_result_text("AI 正在推理中，请稍等......")
        self._show_recommend_dialog("AI 正在推理中，请稍等...", loading=True)
        self.ros_worker.node.StartRecommend()

    def _show_recommend_dialog(self, text: str, loading: bool = False):
        self.recommend_loading = loading
        if loading:
            self.vision_page.set_result_text("AI 正在推理中，请稍等......")
        elif "失败" in text or "暂未生成" in text:
            self.vision_page.set_result_text(text)
        else:
            self.vision_page.set_result_text("推荐结果已生成，请查看弹窗。")

        if self.recommend_dialog is None:
            self.recommend_dialog = RecommendDialog(text, self, is_loading=loading)
            self.recommend_dialog.exit_requested.connect(self._on_recommend_exit_requested)
            self.recommend_dialog.finished.connect(self._on_recommend_dialog_closed)
            self.recommend_dialog.show()
        else:
            self.recommend_dialog.set_content(text)
            self.recommend_dialog.set_loading(loading)
            if not self.recommend_dialog.isVisible():
                self.recommend_dialog.show()

        self.recommend_dialog.raise_()
        self.recommend_dialog.activateWindow()

    def _on_recommend_dialog_closed(self, _result: int):
        self.recommend_dialog = None
        self.recommend_loading = False

    def _on_recommend_exit_requested(self):
        if self.recommend_loading and self.ros_worker and self.ros_worker.node:
            self.ros_worker.node.CancelRecommend()
            self.vision_page.set_result_text("已取消推荐等待，不再获取本次 AI 结果。")
        self.recommend_loading = False

    def _show_food_recognition_dialog(self, text: str):
        self.food_recognition_loading = "AI 正在推理中，请稍等" in text
        if self.food_recognition_loading:
            self.vision_page.set_result_text("AI 正在推理中，请稍等......")
        else:
            self.vision_page.set_result_text("识别完成，请查看提示框。")

        if self.food_recognition_dialog is None:
            self.food_recognition_dialog = FoodRecognizeDialog(text, self)
            self.food_recognition_dialog.exit_requested.connect(
                self._on_food_recognition_exit_requested
            )
            self.food_recognition_dialog.finished.connect(
                self._on_food_recognition_dialog_closed
            )
            self.food_recognition_dialog.show()
        else:
            self.food_recognition_dialog.set_content(text)
            if not self.food_recognition_dialog.isVisible():
                self.food_recognition_dialog.show()

        self.food_recognition_dialog.raise_()
        self.food_recognition_dialog.activateWindow()

    def _on_food_recognition_dialog_closed(self, _result: int):
        self.food_recognition_dialog = None
        self.food_recognition_loading = False

    def _on_food_recognition_exit_requested(self):
        if self.food_recognition_loading and self.ros_worker and self.ros_worker.node:
            self.ros_worker.node.CancelReasoning()
            self.vision_page.set_result_text("已取消识别等待，不再获取本次 AI 结果。")
        self.food_recognition_loading = False

    def _show_tongue_health_dialog(self, text: str, loading: bool = False):
        if not loading and (
            "正在等待健康检测结果" in text or "舌诊图片已发送" in text
        ):
            loading = True

        self.tongue_health_loading = loading
        if loading:
            self.vision_page.set_result_text("AI 正在推理中，请稍等......")
        elif "失败" in text or "暂无可用于舌诊" in text:
            self.vision_page.set_result_text(text)
        else:
            self.vision_page.set_result_text("健康检测已完成，请查看弹窗。")

        if self.tongue_health_dialog is None:
            self.tongue_health_dialog = TongueHealthDialog(
                text, self, is_loading=loading
            )
            self.tongue_health_dialog.exit_requested.connect(
                self._on_tongue_health_exit_requested
            )
            self.tongue_health_dialog.finished.connect(
                self._on_tongue_health_dialog_closed
            )
            self.tongue_health_dialog.show()
        else:
            self.tongue_health_dialog.set_content(text)
            self.tongue_health_dialog.set_loading(loading)
            if not self.tongue_health_dialog.isVisible():
                self.tongue_health_dialog.show()

        self.tongue_health_dialog.raise_()
        self.tongue_health_dialog.activateWindow()

    def _on_tongue_health_dialog_closed(self, _result: int):
        self.tongue_health_dialog = None
        self.tongue_health_loading = False

    def _on_tongue_health_exit_requested(self):
        if self.tongue_health_loading and self.ros_worker and self.ros_worker.node:
            self.ros_worker.node.CancelTongueDiagnosis()
            self.vision_page.set_result_text("已取消健康检测等待，不再获取本次 AI 结果。")
        self.tongue_health_loading = False

    def _apply_global_style(self):
        # (已更新样式表：增加新导航按钮的样式)
        self.setStyleSheet(
            """
            QMainWindow {
                background-color: #E6DED0;
            }
            QWidget#MainPage {
                background-color: #E6DED0;
            }
            QFrame#TitleBox {
                border: 2px solid #B68A58;
                border-radius: 12px;
                background-color: #F3E9D8;
                padding: 6px;
            }
            QLabel#MainTitle {
                font-family: "Microsoft YaHei", "SimHei";
                font-size: 26px;
                font-weight: 900;
                color: #4F3928;
                letter-spacing: 4px;
            }
            QPushButton#ReturnBtn, QPushButton#VisionNavBtn, QPushButton#ExitBtn {
                background-color: #A67C52;
                color: #181411;
                font-family: "Microsoft YaHei", "KaiTi";
                font-size: 15px;
                font-weight: bold;
                border: 2px solid #4C3B2A;
                border-top-color: #D9B07C;
                border-left-color: #D9B07C;
                border-radius: 8px;
                padding: 5px 12px;
            }
            QPushButton#ReturnBtn:hover, QPushButton#VisionNavBtn:hover, QPushButton#ExitBtn:hover {
                background-color: #BD9161;
            }
            QPushButton#ReturnBtn:pressed, QPushButton#VisionNavBtn:pressed, QPushButton#ExitBtn:pressed {
                background-color: #8D6843;
                border-top-color: #3A2C20;
                border-left-color: #3A2C20;
            }
            QFrame#StatusBox {
                background-color: #F4ECDE;
                border: 2px solid #A68B6A;
                border-radius: 10px;
            }
            QLabel#StatusText {
                font-family: "Microsoft YaHei";
                font-size: 13px;
                color: #5C4735;
            }
        """
        )

    def show_food_details(self, data: dict):
        dialog = FoodDetailDialog(
            data["name"],
            data["features"],
            data["precautions"],
            data["image_path"],
            self,
        )
        dialog.exec()

    def _init_mock_environment_timer(self):
        """初始化温湿度随机跳动展示（用于 UI 演示）"""
        # 温度每 5 秒刷新，且存在“本次不动”的概率
        self.temp_timer = QTimer(self)
        self.temp_timer.timeout.connect(self._update_random_temperature)
        self.temp_timer.start(5000)

        # 湿度每 7 秒刷新
        self.humidity_timer = QTimer(self)
        self.humidity_timer.timeout.connect(self._update_random_humidity)
        self.humidity_timer.start(7000)

        # 启动后先显示一次初始值
        self.set_environment(self.mock_temp, self.mock_humidity)

    def _update_random_temperature(self):
        """每 5 秒更新一次温度，单次变化在 ±0.3 内，且有概率不动"""
        no_move_probability = 0.35
        if random.random() >= no_move_probability:
            self.mock_temp += random.uniform(-0.3, 0.3)
            self.mock_temp = max(-2.0, min(10.0, self.mock_temp))
        self.set_environment(self.mock_temp, self.mock_humidity)

    def _update_random_humidity(self):
        """每 7 秒更新一次湿度，单次变化在 ±0.2 内"""
        self.mock_humidity += random.uniform(-0.2, 0.2)
        self.mock_humidity = max(35.0, min(95.0, self.mock_humidity))
        self.set_environment(self.mock_temp, self.mock_humidity)

    def set_environment(self, temp: float, humidity: float):
        self.status_label.setText("")
        self.standby_page.set_environment(temp, humidity)

    def _start_test_timer(self):
        self._test_timer = QTimer(self)
        self._test_timer.setSingleShot(True)
        self._test_timer.timeout.connect(self.test_fun)
        self._test_timer.start(10000)

    def test_fun(self):
        """开机 10 秒后触发的测试弹窗与温度调整。"""
        if not getattr(self, "is_test", False):
            return

        self.mock_temp = 20.0
        self.set_environment(self.mock_temp, self.mock_humidity)
        if getattr(self, "is_test", False):
            self.standby_page.start_test_energy_ramp()

        dialog = QDialog(self)
        dialog.setWindowTitle("能耗异常提示")
        dialog.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        dialog.setModal(True)
        dialog.resize(420, 180)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(16)

        message_label = QLabel("能耗异常，请检查。")
        message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message_label.setWordWrap(True)
        message_label.setStyleSheet(
            "font-family:'Microsoft YaHei'; font-size:18px; color:#8B2500;"
        )
        layout.addWidget(message_label, stretch=1)

        button = QPushButton("知道了")
        button.setObjectName("TestAlertBtn")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFixedSize(120, 40)
        button.clicked.connect(dialog.accept)

        footer_layout = QHBoxLayout()
        footer_layout.addStretch()
        footer_layout.addWidget(button)
        footer_layout.addStretch()
        layout.addLayout(footer_layout)

        dialog.setStyleSheet(
            """
            QDialog {
                background-color: #FDF4E6;
                border: 4px solid #A65A2E;
                border-radius: 18px;
            }
            QPushButton#TestAlertBtn {
                background-color: #B56C42;
                color: #FFFFFF;
                font-family: "Microsoft YaHei";
                font-size: 15px;
                font-weight: bold;
                border-radius: 12px;
                border: 2px solid #7E3D20;
            }
            QPushButton#TestAlertBtn:pressed {
                background-color: #8F4B31;
            }
            """
        )

        dialog.exec()

    def set_food_item(
        self,
        row: int,
        col: int,
        name: str,
        days_left: int,
        features: list,
        precautions: list,
        image_path: str = "",
    ):
        if 0 <= row <= 2 and 0 <= col <= 2:
            self.food_grids[row][col].update_data(
                name, days_left, features, precautions, image_path
            )

    def _start_ros2_thread(self, node):
        """启动 ROS2 Worker 线程"""
        self.ros_worker = RosWorker(node)
        self.ros_worker.node.data_updated.connect(self.update_foods_from_ros)
        self.ros_worker.node.image_updated.connect(self.update_image_from_ros)
        self.ros_worker.node.recommend_updated.connect(self._show_recommend_dialog)
        self.ros_worker.node.food_recognition_updated.connect(
            self._show_food_recognition_dialog
        )
        self.ros_worker.node.tongue_health_updated.connect(self._show_tongue_health_dialog)
        self.ros_worker.node.reason_flag.connect(
            self.ros_worker.node.StartReasoning, Qt.ConnectionType.QueuedConnection
        )
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
            expiry = item[1]  # 假设这是剩余天数或过期日期
            features = item[2] if item[2] else []
            precautions = item[3] if item[3] else []

            # 计算 days_left（根据你的业务逻辑调整）
            days_left = expiry if isinstance(expiry, int) else -1

            self.set_food_item(row, col, name, days_left, features, precautions)

    def closeEvent(self, event):
        """窗口关闭时优雅停止 ROS2 线程"""
        self._publish_qdriver_control(False)
        if self.ros_worker:
            self.ros_worker.stop()
        super().closeEvent(event)


def create_ink_camera_placeholder() -> QPixmap:
    """用代码画一个适配深色机壳的摄像头占位图"""
    pixmap = QPixmap(400, 300)
    pixmap.fill(QColor("#171919"))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(QColor("#B79261"), 6)
    painter.setPen(pen)
    painter.drawRoundedRect(78, 46, 244, 180, 18, 18)

    painter.setBrush(QColor(24, 27, 27, 220))
    painter.drawRoundedRect(92, 60, 216, 152, 12, 12)

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#D3B07B"))
    for x, y in [(88, 56), (300, 56), (88, 200), (300, 200)]:
        painter.drawEllipse(x, y, 10, 10)

    painter.setPen(QColor("#DCC8A6"))
    painter.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
    painter.drawText(
        0, 260, 400, 30, Qt.AlignmentFlag.AlignCenter, "— 虚席以待 鉴诸珍馐 —"
    )

    painter.end()
    return pixmap


# ==========================================
# 视觉识别页面组件 (新中式风格)
# ==========================================
class VisionRecognizePage(QWidget):
    back_clicked = Signal()  # 返回信号
    capture_clicked = Signal()  # 抓拍信号
    tongueai_clicked = Signal()  #
    season_clicked = Signal()  #

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("VisionPage")
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 20, 30, 20)
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

        frame_layout = QVBoxLayout(self.image_frame)
        frame_layout.setContentsMargins(5, 5, 5, 5)  # 留出“木框”厚度

        self.image_label = QLabel()
        self.image_label.setObjectName("InkImageDisplay")
        self.image_label.setFixedSize(
            int(640 * 0.7), int(480 * 0.7)
        )  # 1. 强制设定一个固定像素值（宽, 高）
        self.image_label.setScaledContents(False)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # 初始显示占位图
        self.image_label.setPixmap(create_ink_camera_placeholder())

        frame_layout.addWidget(self.image_label)
        layout.addWidget(self.image_frame, 0, Qt.AlignmentFlag.AlignCenter)

        # 3. 识别结果简报 (可选，增强体验)
        self.result_label = QLabel("...")
        self.result_label.setObjectName("RecognizeResultText")
        self.result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result_label.setWordWrap(True)
        layout.addWidget(self.result_label)

        # 4. 底部按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(30)
        btn_layout.addStretch()

        self.capture_btn = QPushButton("◀ 扫描食材")
        self.capture_btn.setObjectName("InkBtn_Action")
        self.capture_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.capture_btn.clicked.connect(self.capture_clicked.emit)

        self.season_btn = QPushButton("◀ 推荐食谱")
        self.season_btn.setObjectName("InkBtn_Action")
        self.season_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.season_btn.clicked.connect(self.season_clicked.emit)

        self.tongueai_btn = QPushButton("◀ 健康检测")
        self.tongueai_btn.setObjectName("InkBtn_Action")
        self.tongueai_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tongueai_btn.clicked.connect(self.tongueai_clicked.emit)

        self.back_btn = QPushButton("◀ 返回主页")
        self.back_btn.setObjectName("InkBtn_Back")
        self.back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back_btn.clicked.connect(self.back_clicked.emit)

        btn_layout.addWidget(self.capture_btn)
        btn_layout.addWidget(self.tongueai_btn)
        btn_layout.addWidget(self.season_btn)
        btn_layout.addWidget(self.back_btn)
        btn_layout.addStretch()

        layout.addLayout(btn_layout)
        layout.addStretch()

        # 样式表：保持黑胡桃木、哑金、宣纸色风格
        self.setStyleSheet(
            """
            QWidget#VisionPage {
                background-color: #E6DED0;
            }
            QLabel#VisionTitle {
                font-family: "Microsoft YaHei", "KaiTi";
                font-size: 24px;
                font-weight: bold;
                color: #4F3928;
                letter-spacing: 2px;
                padding: 10px 14px;
            }
            QFrame#ImageCanvasFrame {
                background-color: #EADFCB;
                border: 6px solid #B68A58;
                border-radius: 14px;
            }
            QLabel#InkImageDisplay {
                background-color: #F7F2E8;
                border: 3px solid #8B7258;
                border-radius: 8px;
            }
            QLabel#RecognizeResultText {
                font-family: "Microsoft YaHei", "SimSun";
                font-size: 15px;
                font-weight: bold;
                color: #5A4430;
                background-color: #F4ECDE;
                border: 2px solid #A68B6A;
                padding: 10px 14px;
                border-radius: 8px;
            }
            QPushButton {
                font-family: "Microsoft YaHei", "KaiTi";
                font-size: 17px;
                font-weight: bold;
                padding: 10px 25px;
                border-radius: 8px;
            }
            QPushButton#InkBtn_Action {
                background-color: #A67C52;
                color: #181411;
                border: 2px solid #4C3B2A;
                border-top-color: #D9B07C;
                border-left-color: #D9B07C;
            }
            QPushButton#InkBtn_Action:hover {
                background-color: #BD9161;
            }
            QPushButton#InkBtn_Action:pressed {
                background-color: #8D6843;
                border-top-color: #3A2C20;
                border-left-color: #3A2C20;
                padding-top: 11px; padding-left: 26px;
            }
            QPushButton#InkBtn_Back {
                background-color: #EFE5D4;
                color: #5A4430;
                border: 2px solid #9A7D5C;
            }
            QPushButton#InkBtn_Back:hover {
                background-color: #F7EEDC;
            }
        """
        )

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)  # 阴影模糊半径，越大越虚
        shadow.setXOffset(5)  # 水平偏移
        shadow.setYOffset(5)  # 垂直偏移
        shadow.setColor(QColor(0, 0, 0, 160))  # 阴影颜色（黑色，带透明度）

        # 2. 将阴影挂载到你的木框组件上
        self.image_frame.setGraphicsEffect(shadow)

    def update_viewer_image(self, pixmap: QPixmap):
        """外部调用：更新显示的图像（例如摄像头帧）"""
        if pixmap.isNull():
            return

        # 保持比例缩放以适应 Frame 内部
        target_w = self.image_label.width() - 4
        target_h = self.image_label.height() - 4
        scaled_pixmap = pixmap.scaled(
            target_w,
            target_h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled_pixmap)

    def set_result_text(self, text: str):
        """外部调用：更新识别结果文字"""
        self.result_label.setText(f"{text}")
