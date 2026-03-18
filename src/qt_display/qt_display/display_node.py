from rclpy.node import Node
from .display_component import *
from sql_interface.srv import SQLOperation

class DisplayNode(Node):
    def __init__(self,name:str) -> None:
        super().__init__(node_name=name)
        self.get_logger().info("DisplayNode started")
        self.app = QApplication(sys.argv)
        self.fridge = SmartFridgeUI()
        self.fridge.show()
        self.testImportFood()
        sys.exit(self.app.exec())
        pass
    
    def testSetEnv(self):
        pass

    def testImportFood(self):
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
                self.fridge.set_food_item(r, c, name, days, feats, precs, img)
                idx += 1    
    def ros_part_init(self):
        self.clients_sql = self.create_client()
