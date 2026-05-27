#已配置好CV和py5环境
#this script:
import py5
import numpy as np
import cv2
import os
import ctypes
import platform
from datetime import datetime, timedelta

# 仅在 Windows 系统下执行，调整窗口==================
if platform.system() == "Windows":
    try:
        # 告诉 Windows 不要对这个 Python 进程进行缩放
        ctypes.windll.shcore.SetProcessDpiAwareness(1) 
    except Exception as e:
        print(f"DPI 设置失败: {e}")
#===================设置窗口=======================

class VideoProcessor:
    def __init__(self, frames_dir,output_dir="output"):
        self.frames_dir = frames_dir
        self.curr_frame_img = None
        self.output_dir = output_dir
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def update_frame(self, frame_count):
        # 直接根据帧号读取图片，不再调用 OpenCV
        img_path = os.path.join(self.frames_dir, f"frame_{frame_count:04d}.jpg")
        # 优化点 1：显式释放旧对象
        if self.curr_frame_img is not None:
            self.curr_frame_img = None

        if os.path.exists(img_path):
            self.curr_frame_img = py5.load_image(img_path)
            return True
        return False
    
    def save_current_frame(self, frame_count):
        """导出当前画布内容为序列帧"""
        file_path = os.path.join(self.output_dir, f"frame_{frame_count:04d}.png")
        py5.save(file_path)



class AsciiLayer:
    def __init__(self, font_size=14, resolution=8):
        # 字符集：从暗到亮
        self.chars = "@#W$9876543210?!abc;:*+-,._ "
        self.resolution = resolution
        self.font_size = font_size
        self.font = None

    def setup(self):
        # 加载等宽字体以保证对齐
        self.font = py5.create_font("Helvetica", self.font_size)

    def draw(self, img_source, threshold=150):
        """
        img_source: 传入的 py5 PImage 对象或当前的视频帧
        threshold: 亮度阈值，低于此数值的像素不绘制（保持背景黑）
        """
        py5.push()  # 隔离样式修改
        if self.font:
            py5.text_font(self.font)
            
            py5.text_size(self.font_size)
        py5.text_align(py5.CENTER, py5.CENTER)
        py5.fill("#99FF00")
        
        # 确保图像像素已加载
        img_source.load_pixels()
        
        # 获取图像宽高
        w, h = img_source.width, img_source.height#w，h是图像的宽&高

        # 计算缩放比例，以便把文字画回正确的位置
        scale_x = py5.width / w
        scale_y = py5.height / h
        
        # 遍历采样
        for y in range(0, h, self.resolution):#part3
            for x in range(980, w, self.resolution):
                # 计算像素在一维数组中的位置：索引 = x + y * 宽度
                # 这是最稳健的像素获取方式
                loc = x + y * w
                # 确保索引不越界
                if loc >= len(img_source.pixels):
                    continue
                    
                pixel_color = img_source.pixels[loc]
                bright = py5.brightness(pixel_color)
                
                if bright < threshold:
                    continue
                
                char_idx = int(py5.remap(bright, 0, 255, 0, len(self.chars) - 1))
                char = self.chars[char_idx]
                # 【修正：坐标乘以缩放比例，让字符填满 1920 窗口】
                draw_x = (x + self.resolution // 2) * scale_x
                #二次缩放（拉宽）
                draw_x = py5.width - ((py5.width - draw_x)*2)
                draw_y = (y + self.resolution // 2) * scale_y
                py5.text(char, draw_x, draw_y)
        
        py5.pop() # 恢复之前的样式状态


class TrackRenderer:
    def __init__(self,orig_w,orig_h, coords_path, vis_path, scale=0.5):
        self.scale = scale
        self.orig_w = orig_w
        self.orig_h = orig_h
        self.font = None
        # 加载数据
        self.tracks = np.load(coords_path)
        self.visibility = np.load(vis_path)

        self.current_boxes = []  # 新增：存储当前帧所有方框的 (x, y, w, h)
        
        # --- 修改部分 ---
        self.all_time_points = []  # 存储所有画过的历史点
        self.sample_interval = 10   # 每隔多少帧记录一次点（你可以自行调试此参数）


    def setup(self):
        self.font = py5.create_font("Helvetica", 16)

    def _draw_marker(self, x, y, alpha, size, is_current, font, obj_id=None):
        """
        绘制单个点
        :param alpha: 透明度 (0-255)
        :param size: 圆形直径
        :param is_current: 是否是当前帧的最前端点
        """
        
        if is_current:
            py5.no_fill() # 
            py5.stroke_weight(2)
            py5.stroke("#99FF00")
            py5.rect((x-24),(y-24),48,48)
            py5.no_stroke()
            
            py5.fill("#99FF00")
            py5.circle(x, y, size)
            self._draw_marker_label(x,y,font, obj_id)

            py5.stroke(255)
            py5.stroke_weight(0.5)
            #self._draw_dashed_line(x,180,x,900, 10,15)
            #self._draw_dashed_line(320,y,1600,y, 10,15)
            #self._draw_dashed_line(x,0,x,1080, 10,15)
            #self._draw_dashed_line(0,y,1920,y, 10,15)


        else:
            # 拖尾点：随着时间变暗或保持黑色，这里用带透明度的黑色模拟虚影
            py5.no_stroke()
            py5.fill("#99FF00") 
            py5.circle(x, y, size)

    def _draw_marker_label(self , x,y,font, obj_id):
        py5.no_stroke()
        py5.fill("#99FF00")
        #text_string = "Coordinate: (" + str(x) + "," + str(y) + ")"
        #text_string = "(" + str(int(x)) + "," + str(int(y)) + ")"
        text_string1 = "OBJECT ID: " + str(obj_id) 
        text_string2 = "LOC: " + "(" + str(int(x)) + "," + str(int(y)) + ")"
        text_string = text_string1 + "  " + text_string2

        py5.text_font(self.font)#先
        
        py5.text_size(16)#后

        #length1 = py5.text_width(text_string1)
        #length2 = py5.text_width(text_string2)
        #length = max(length1, length2)
        length = py5.text_width(text_string)
        offset = 5
        
        #py5.fill("#99FF00")
        py5.fill(255)
        py5.rect((x+offset) , (y+offset) , (10+length) ,18)
        py5.fill("#99FF00")
        py5.fill(0)
        #py5.fill(255)
        py5.text(text_string ,(x+offset+5), (y+offset+16))#text size
        
    def _draw_dashed_line(self, x1, y1, x2, y2, dash_len=5, gap_len=3):
        d = py5.dist(x1, y1, x2, y2)
        if d == 0: return
        for i in range(0, int(d), dash_len + gap_len):
            start = i / d
            end = min((i + dash_len) / d, 1.0)
            py5.line(
                py5.lerp(x1, x2, start), py5.lerp(y1, y2, start),
                py5.lerp(x1, x2, end), py5.lerp(y1, y2, end)
            )



    def _draw_closed_shape(self, points, vis, alpha_base):
        """
        按照索引顺序连接所有可见点并填充颜色
        """
        # 1. 提取当前所有可见的点，并存入一个列表
        active_vertices = []
        for i in range(len(points)):
            if vis[i]:
                # 转换坐标
                vx = points[i][0] / self.scale
                vy = points[i][1] / self.scale
                active_vertices.append((vx, vy))

        # 2. 只有当可见点不少于 3 个时，才能形成多边形
        if len(active_vertices) >= 3:
            py5.push()  # 隔离样式
            
            # 设置填充颜色（这里用 alpha_base 控制透明度）
            # 设置一个淡淡的填充色，比如半透明白色
            py5.fill("#99FF00", alpha_base * 0.5) 
            
            # 如果不想要多边形的边框，可以设置 no_stroke
            # 或者给一个淡淡的描边
            #py5.stroke(255, alpha_base * 0.3)
            #py5.stroke_weight(1)
            
            # --- 开始绘制多边形 ---
            py5.begin_shape()
            for vx, vy in active_vertices:
                py5.vertex(vx, vy)
            # py5.CLOSE 会自动连接最后一个点和第一个点
            py5.end_shape(py5.CLOSE)
            
            py5.pop()


    

    def _draw_connections(self, points, vis, alpha_base):
        """
        实现功能：距离越近，线越深、越粗；距离越远，线越浅、越细。
        """
        # 定义距离的阈值（根据你的视频分辨率调整）
        # 比如：距离超过 300 像素的线就完全看不见了
        max_dist = 1200.0 
        min_dist = 10.0

        for i in range(len(points)):
            for j in range(i + 1, len(points)):
                if vis[i] and vis[j]:
                    # 1. 计算物理坐标
                    x1, y1 = points[i][0] / self.scale, points[i][1] / self.scale
                    x2, y2 = points[j][0] / self.scale, points[j][1] / self.scale
                    
                    # 2. 计算两点间距离
                    d = py5.dist(x1, y1, x2, y2)
                    
                    # 3. 只有在一定距离内的点才连线，避免画面太乱
                    if d < max_dist:
                        # 映射透明度：距离越小(min_dist)，透明度越高(alpha_base)；距离越大，越透明(0)
                        # 这里 alpha_base 是你 render 传进来的基础透明度
                        line_alpha = py5.remap(d, min_dist, max_dist, alpha_base * 0.6, alpha_base * 0.2)
                        
                        # 映射粗细：距离越小线越粗(2.0)，距离越大线越细(0.2)
                        line_weight = py5.remap(d, min_dist, max_dist, 1.5, 0.2)
                        
                        py5.stroke(255, line_alpha)
                        py5.stroke_weight(line_weight)
                        py5.line(x1, y1, x2, y2)




    def render(self, frame_idx, target_font):

        self.current_boxes = [] # 每一帧开始前清空

        points = self.tracks[frame_idx]
        vis = self.visibility[frame_idx]

        
            

        
        # 2. 绘制当前帧的实时点（带框和标签）
        for i, (point, is_visible) in enumerate(zip(points, vis)):
            
            if is_visible:
                self._draw_closed_shape(points, vis, 200)
                self._draw_connections(points, vis, 200)

                trans_x = (point[0] / self.scale) 
                trans_y = (point[1] / self.scale) 

                box = (trans_x - 24, trans_y - 24, 48, 48)########
                #box = (trans_x - 15, trans_y - 15, 30, 30)
                self.current_boxes.append(box)
                #draw_original_video_overlay(frame_img)
                # 标记 is_current = True
                #self._draw_marker(trans_x, trans_y, 255, 2, True, target_font, obj_id=i)


                

    def render2(self, frame_idx,target_font):
        #self.current_boxes = [] # 每一帧开始前清空

        points = self.tracks[frame_idx]
        vis = self.visibility[frame_idx]

        # --- 修改逻辑：每隔固定帧数将当前点坐标存入永久列表 ---
        if frame_idx % self.sample_interval == 0:
            for i, (point, is_visible) in enumerate(zip(points, vis)):
                if is_visible:
                    # 提前转换好坐标
                    trans_x = (point[0] / self.scale) 
                    trans_y = (point[1] / self.scale) 
                    # 存入列表，以便后续每一帧都绘制
                    self.all_time_points.append((trans_x, trans_y))
        # --- 修改结束 ---

        # 1. 首先绘制所有历史累积的点（非当前帧点）
        for old_x, old_y in self.all_time_points:
            # 历史点使用固定的 size 和 alpha 表现
            self._draw_marker(old_x, old_y, 255, 4, False, target_font)


        for i, (point, is_visible) in enumerate(zip(points, vis)):
            
            if is_visible:
                

                trans_x = (point[0] / self.scale) 
                trans_y = (point[1] / self.scale) 

                box = (trans_x - 24, trans_y - 24, 48, 48)########
                #box = (trans_x - 15, trans_y - 15, 30, 30)
                self.current_boxes.append(box)
                #draw_original_video_overlay(frame_img)
                # 标记 is_current = True
                self._draw_marker(trans_x, trans_y, 255, 2, True, target_font, obj_id=i)







    


#======================================================
#===============main part代码的主体部分===============
#变量==========
video_manager = VideoProcessor(r"resource\kite_1080_of")
ascii_effect = AsciiLayer(font_size=24, resolution=8)
renderer = TrackRenderer(1920, 1080, r"resource\data\kite_data\tracks_coords.npy", r"resource\data\kite_data\tracks_visibility.npy", 1/3)
#ui_font = py5.create_font("kochi-mincho-2", 32)
ui_font = None
textlist_timeandloc = ["04/04/2026  ", "GongQing Forest Park ", "Shanghai, China"]
MY_DIRT_SPOTS = [
    (60, 412, 25, 24),  # 第一个污点
    (445, 544, 26, 18),   # 第二个污点
    (539, 674, 9, 8),
    (572,408,26,19),
    (693,688,31,24),
    (1120,123,14,14),
    (1208,598,14,14)

]

#ink_img_cache = None
#变量==========





def setup():
    py5.size(1920, 1080, py5.P2D) # P2D 使用 GPU 渲染
    py5.background(0) #黑底
    ascii_effect.setup()
    renderer.setup()
    global ascii_image
    global ui_font 
    ui_font  = py5.create_font(r"resource\font\kochi-mincho-2.ttf", 32)

    #global ink_img_cache
    # --- 关键：在 setup 里生成效果，只生成一次 ---
    #print("正在生成墨水效果...")
    ink_img_cache = create_ink_text("TEST TEXT",64, bleed_strength=2.0)
    #print("生成完毕！")
    



def draw():
    py5.background(0)#暂时改成了灰色
    
    #py5.background(255)

    # 1. 逻辑更新（获取当前帧坐标、计算物理等）
    
    current_idx = py5.frame_count - 1
    success = video_manager.update_frame(current_idx)
    

    if success:
        current_frame_img = update_data(current_idx)
    
        # 2. 渲染背景层
        #draw_background_layer(current_frame_img)
    
        # 3. 渲染原视频图层
        
    
        # 4. 渲染核心追踪轨迹层（根据你获取的 .npy 数据）
        draw_tracking_visuals(current_idx)
    
        # 5. 渲染顶层 UI/纹理覆盖
        draw_original_video_overlay(current_frame_img, current_idx)
        draw_foreground_texture(textlist_timeandloc, current_idx)
    
        # 6. 导出（如果需要）
        #py5.save_frame(r"final_output\kite_output\kiteedited\frame_####.png")

    else:
        print("所有帧处理完毕。")
        py5.no_loop()





#自定义函数

def update_data(idx):
    
    return(video_manager.curr_frame_img)

def draw_background_layer(current_frame):#并不是真正的“黑底”那一层，而是黑底之上的最下一层
    
    ascii_effect.draw(current_frame, threshold=150) #这里控制的是最低亮度，低于这个亮度的就不显示字符

def draw_tracking_visuals(current_idx):
    renderer.render(current_idx ,  ui_font)








#==============UI层，最上层=================
#这段可以改，写的复用率比较低了
def draw_foreground_texture(textlist, frame_idx):
    #绘制四周的标尺===========
    py5.stroke(255)
    py5.stroke_weight(2)
    py5.line(320,0,320,30)
    py5.line(1600,0,1600,30)
    py5.line(960,0,960,15)
    py5.line(1920,180,1890,180)
    py5.line(1920,900,1890,900)
    py5.line(1920,540,1905,540)
    #
    py5.line(320,1080,320,1050)
    py5.line(1600,1080,1600,1050)
    py5.line(960,1080,960,1065)
    py5.line(0,180,30,180)
    py5.line(0,900,30,900)
    py5.line(0,540,15,540)
    #画斜线====================
    #定位：
    #py5.line(128,1080,128,1065)
    #py5.line(1354,0,1354,15)
    #py5.stroke_weight(1)
    #draw_dashed_line(1354,0,128,1080)


    #写地点信息
    #textlist = ["04/04/2026  13:05:25", "GongQing Forest Park ", "Shanghai, China"]
    #time_str = calculated_time(frame_idx, "13:05:25")
    #text_time_and_location(textlist, time_str, 32, 0)

    #写关键词
    py5.text_font(ui_font)
    py5.text_size(48)
    
    py5.fill("#99FF00")
    wind_text = "Gravity / Wind / Drag"
    wind_length = py5.text_width(wind_text)
    _draw_glowing_text(wind_text, 960-(wind_length/2),930 , 48, ui_font)
    #notes
    py5.fill(255)
    py5.text_size(24)
    added_text = "This image isolates the motion of kites in air as the resultant of environmental forces.."
    added_text_length = py5.text_width(added_text)
    py5.text(added_text, 960-(added_text_length)/2, 960)

    #ink test
    #py5.push_style()
    #py5.image_mode(py5.CENTER)
    #if ink_img_cache:
        #py5.image(ink_img_cache, 960 , 540 )
    #py5.pop_style() # 还原现场，此后的 image_mode 会自动变回原来的样子



def _draw_glowing_text(text_str, x, y, size, font):
    # 1. 设置字体和大小
    py5.text_font(font)
    py5.text_size(size)
    
    # 定义亮绿色颜色对象
    glow_color = py5.color("#99FF00") 
    
    py5.fill(glow_color, 25)  # 极低透明度，制造朦胧感
    for i in range(-5, 6, 5): # 偏移量 -5, 0, 5
        for j in range(-5, 6, 5):
            py5.text(text_str, x + i, y + j)

    # 第二级：中等距离 (光晕过渡)
    py5.fill(glow_color, 60)
    for i in range(-3, 4, 3): # 偏移量 -3, 0, 3
        for j in range(-3, 4, 3):
            py5.text(text_str, x + i, y + j)

    # 第三级：近距离 (强发光区)
    py5.fill(glow_color, 120)
    offsets_near = [-1.5, 1.5]
    for ox in offsets_near:
        for oy in offsets_near:
            py5.text(text_str, x + ox, y + oy)

    # 4. 核心层 (第三层，纯白或极亮绿)
    # 使用白色作为中心可以增加“光亮感”
    py5.fill(glow_color) 
    py5.text(text_str, x, y)
    py5.text(text_str, x-1, y)
    py5.text(text_str, x+1, y)
    py5.text(text_str, x, y+1)
    py5.text(text_str, x, y-1)


def create_ink_text(txt, font_size, bleed_strength=0.5):
    font = py5.create_font("Arial Black", font_size)
    # 1. 动态计算宽度
    temp_g = py5.create_graphics(10, 10)
    temp_g.begin_draw()
    temp_g.text_size(font_size)
    tw = int(temp_g.text_width(txt))
    temp_g.end_draw()
    
    w = int(tw + font_size) 
    h = int(font_size * 2)
    
    # 2. 绘制黑底白字
    g = py5.create_graphics(w, h)
    g.begin_draw()
    g.text_font(font)
    g.background(0)  # 黑色
    g.fill(255)      # 白色
    g.text_size(font_size)
    g.text_align(py5.CENTER, py5.CENTER)
    g.text(txt, w // 2, h // 2)
    g.end_draw()

    # 3. 【彻底修复处】安全地提取像素
    g.load_pixels()
    
    # 先以 int32 读入（避开负数报错），再 view 成 uint32（方便位运算）
    raw_pixels = np.array(g.pixels, dtype=np.int32).view(np.uint32)
    
    # 提取红色通道作为灰度图
    img_array = ((raw_pixels >> 16) & 0xFF).reshape(h, w).astype(np.uint8)

    # 4. 晕染算法
    k_size = int(font_size * 0.25 * bleed_strength)
    if k_size % 2 == 0: k_size += 1
    
    blurred = cv2.GaussianBlur(img_array, (k_size, k_size), 0)
    # 25 是阈值，越小晕染越开
    _, result = cv2.threshold(blurred, 25, 255, cv2.THRESH_BINARY)

    # 5. 转回 py5 图像
    output = py5.create_image(w, h, py5.ALPHA)
    output.load_pixels()
    
    # 1. 获取模糊后的原始亮度
    alphas = blurred.flatten().astype(np.float32) # 先转成浮点数方便计算
    
    # 2. 【核心修复】拉高透明度
    # 哪怕是很淡的像素，我们也让它变得明显一点
    # 使用 np.sqrt (平方根) 可以把小的数值显著拉大，比如 16 会变成 127
    alphas = np.sqrt(alphas / 255.0) * 255.0
    alphas = np.clip(alphas * 1.5, 0, 255).astype(np.uint32) # 1.5倍增益并限制在255以内

    # 3. 构造像素 (ARGB)
    # 0x0099FF00 是你的草绿色
    final_pixels = (alphas << 24) | 0x0099FF00

    output.pixels[:] = final_pixels.view(np.int32)
    output.update_pixels()
    
    return output




def calculated_time(frame_idx, original_time):
    START_TIME = datetime.strptime(original_time, "%H:%M:%S")
    #帧率是 30 FPS
    FPS = 30
    # 1. 计算偏移的秒数
    elapsed_seconds = frame_idx / FPS
    # 2. 将偏移量加到初始时间上
    current_time = START_TIME + timedelta(seconds=elapsed_seconds)
    # 3. 格式化成字符串 (例如: "13:05:12")
    # 如果需要显示毫秒，可以用 "%H:%M:%S.%f" 然后切片 [:11]
    time_str = current_time.strftime("%H:%M:%S")
    return(time_str)



    
def draw_dashed_line(x1, y1, x2, y2, dash_length=25, space_length=30):
    """
    画一条虚线
    :param x1, y1: 起点
    :param x2, y2: 终点
    :param dash_length: 每段实线的长度
    :param space_length: 每段间隙的长度
    """
    # 计算总距离
    dist = py5.dist(x1, y1, x2, y2)
    
    # 如果距离太小，直接返回
    if dist == 0:
        return
        
    # 计算分段的总长度（一段实线 + 一段空隙）
    step_length = dash_length + space_length
    
    # 计算需要画多少个循环
    num_steps = int(dist / step_length)
    
    # 计算单位方向向量 (Normalized Vector)
    dx = (x2 - x1) / dist
    dy = (y2 - y1) / dist
    
    for i in range(num_steps + 1):
        # 当前段的起始位置
        start_x = x1 + dx * i * step_length
        start_y = y1 + dy * i * step_length
        
        # 当前段的结束位置（确保不会超过终点）
        current_dash_end = min((i * step_length) + dash_length, dist)
        end_x = x1 + dx * current_dash_end
        end_y = y1 + dy * current_dash_end
        
        # 只有起始点还没超过总长度时才绘制
        if (i * step_length) < dist:
            py5.line(start_x, start_y, end_x, end_y)




def text_time_and_location(text_list, time_str, size = 24, linespace = 12):
    py5.fill(255)
    py5.text_font(ui_font)
    py5.text_size(size)
    this_list = []
    for i in range(len(text_list)):
        this_list.append( text_list[i]) 

    this_list[0] = text_list[0] + time_str
    
    for i, textline in enumerate(this_list):
        if i == 0:
            py5.fill("#99FF00")
        elif i == 2:
            py5.fill("#99FF00")
            py5.no_stroke()
            py5.rect(50,(160 + ((1.75)*size) ),py5.text_width(textline),(0.75*size))
            py5.fill(0)

        py5.text(textline, 50, 160+ ((size)*(i + 0.5)) + (i*linespace))
        py5.fill(255)

    
#===========================================

#===========视频本身图层=================
def draw_original_video_overlay(current_frame, current_idx):
    #repair_dirt_spots(current_frame, MY_DIRT_SPOTS)
    #py5.image(current_frame, 320, 180)
    
    #视频画面处理部分

    for box in renderer.current_boxes:
        bx, by, bw, bh = box

        # 计算源坐标
        sx = int((bx) )
        sy = int((by) )
        sw = int(bw )
        sh = int(bh )
        sx = max(0, sx)
        # 边界检查：防止坐标为负数或超出图片范围导致报错
        sy = max(0, sy)

        # 1. 创建一个新的空图片作为容器
        # Py5Image 的初始化需要宽度和高度
        crop_img = py5.create_image(sw, sh, py5.ARGB)
        
        # 2. 使用 copy 将像素从大图“抓”到小图里
        # 语法：目标图.copy(源图, 源x, 源y, 源宽, 源高, 目标x, 目标y, 目标宽, 目标高)
        crop_img.copy(current_frame, sx, sy, sw, sh, 0, 0, sw, sh)
        
        py5.image(crop_img, bx, by)

    renderer.render2(current_idx , ui_font)
        




def repair_dirt_spots(img, spot_list):

    for (x, y, w, h) in spot_list:
        # 参数顺序: 源图, 源x, 源y, 源宽, 源高, 目标x, 目标y, 目标宽, 目标高
        # 注意：这里我们使用 img.copy() 确保在图像内部进行操作
        img.copy(img, 
                 int(x + w), int(y), int(w), int(h), 
                 int(x), int(y), int(w), int(h))



py5.run_sketch()