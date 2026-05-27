#已配置好CV和py5环境
#this script:
import py5
import numpy as np
import cv2
import os
import ctypes
import platform
import json
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
        # 显式释放旧对象
        if self.curr_frame_img is not None:
            self.curr_frame_img = None

        # 定义可能的后缀名
        base_name = f"frame_{frame_count:04d}"
    
        # 依次尝试不同的扩展名
        target_path = None
        for ext in [".jpg", ".png", ".JPG", ".PNG"]:
            full_path = os.path.join(self.frames_dir, base_name + ext)
            if os.path.exists(full_path):
                target_path = full_path
                break # 找到了就跳出循环

        if target_path:
            self.curr_frame_img = py5.load_image(target_path)
            return True
    
        return False
    
    def save_current_frame(self, frame_count):
        """导出当前画布内容为序列帧"""
        file_path = os.path.join(self.output_dir, f"frame_{frame_count:04d}.png")
        py5.save(file_path)



class AsciiLayer:
    def __init__(self, font_size=14, resolution=8):
        
        self.chars = "@#W$9876543210?!abc;:*+-,._"
        self.resolution = resolution
        self.font_size = font_size
        self.font = None

    def setup(self):
       
        self.font = py5.create_font("Helvetica", self.font_size)

    def draw(self, img_source, threshold=230):
        
        py5.push()  
        if self.font:
            py5.text_font(self.font)
            
            py5.text_size(self.font_size)
        py5.text_align(py5.CENTER, py5.CENTER)
        #py5.fill("#99FF00")
        py5.fill(0)
            
        img_source.load_pixels()    
    
        w, h = img_source.width, img_source.height
        
        
        for y in range(0, h, self.resolution):
            for x in range(0, w, self.resolution):

                loc = x + y * w

                img_r = (img_source.pixels[loc] >> 16) & 0xFF

                if img_r < threshold:
                    continue
                
                if loc >= len(img_source.pixels):
                    continue
                    
                pixel_color = img_source.pixels[loc]
                bright = py5.brightness(pixel_color)
                
                if bright < threshold:
                    continue
                
                char_idx = int(py5.remap(bright, 0, 255, 0, len(self.chars) - 1))
                char = self.chars[char_idx]
                py5.text(char, x, y)
        
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
        
        self.history = [] 
        self.max_history = 30  # 拖尾长度

    def setup(self):
        self.font = py5.create_font("Helvetica", 16)

    def _draw_marker(self, x, y, alpha, size, is_current, font):
        """
        绘制单个点
        :param alpha: 透明度 (0-255)
        :param size: 圆形直径
        :param is_current: 是否是当前帧的最前端点
        """
        
        if is_current:
            py5.no_fill() # 
            py5.stroke_weight(2)
            py5.stroke(0)
            #py5.rect((x-15),(y-15),30,30)
            py5.no_stroke()
            #py5.fill(0)
            py5.fill(0)
            py5.circle(x, y, size)
            self._draw_marker_label(x,y,font)
        #else:
            # 拖尾点：随着时间变暗或保持黑色，这里用带透明度的黑色模拟虚影
            #py5.fill(0, 0, 0, alpha) 
            #py5.circle(x, y, size)

    def _draw_marker_label(self , x,y,font):
        py5.no_stroke()
        py5.fill(255)
        #text_string = "Coordinate: (" + str(x) + "," + str(y) + ")"
        text_string = "(" + str(x) + "," + str(y) + ")"

        py5.text_font(self.font)#先
        
        py5.text_size(16)#后

        length = py5.text_width(text_string)
        #py5.rect((x+5) , (y+5) , (10+length) ,16)
        py5.fill("#99FF00")
        py5.text(text_string ,(x+10), (y+19))


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
                        
                        py5.stroke(0, 0, 0, line_alpha)
                        py5.stroke_weight(line_weight)
                        py5.line(x1, y1, x2, y2)




    def render(self, frame_idx, target_font):
        # 1. 将当前帧数据加入历史记录
        # 我们只存坐标和可见性
        current_data = {
            "points": self.tracks[frame_idx],
            "vis": self.visibility[frame_idx]
        }
        self.history.append(current_data)

        # 2. 保持队列长度为 10
        if len(self.history) > self.max_history:
            self.history.pop(0)

        # 3. 遍历历史记录进行绘制 (从旧到新)
        for h_idx, data in enumerate(self.history):
            # 计算拖尾效果的参数
            # h_idx 越小，说明越老
            progress = (h_idx + 1) / len(self.history) # 范围 0.1 到 1.0
            
            # 越老（越靠前）的点，透明度越低，尺寸越小
            alpha = int(py5.remap(progress, 0, 1, 10, 255))
            size = py5.remap(progress, 0, 1, 4, 16) # 越老越细
            
            is_current = (h_idx == len(self.history) - 1)

            points = data["points"]
            vis = data["vis"]

            if is_current:
                self._draw_connections(points, vis, alpha)

            for i, (point, is_visible) in enumerate(zip(points, vis)):
                if is_visible:
                    # 坐标转换逻辑保持不变
                    trans_x = (point[0] / self.scale) 
                    trans_y = (point[1] / self.scale) 
                    
                    self._draw_marker(trans_x, trans_y, alpha, size, is_current, target_font)


class LightData:
    def __init__(self, json_path, mask_path, video_w, video_h):
        # 读取数据
        with open(json_path) as f:
            self.data = json.load(f)

        self.softmask = np.load(mask_path)

        self.video_w = video_w
        self.video_h = video_h

        self.frame_index = 0
        self.total_frames = len(self.data)

    # ===== 帧控制 =====
    def next_frame(self):
        if self.frame_index < self.total_frames - 1:
            self.frame_index += 1

    def get_frame(self):
        return self.data[self.frame_index]

    def get_mask(self):
        return self.softmask[self.frame_index]

    # ===== 坐标映射 =====
    def map_x(self, x, canvas_w):
        return x * canvas_w / self.video_w

    def map_y(self, y, canvas_h):
        return y * canvas_h / self.video_h

    # ===== centroid =====
    def get_centroid(self, canvas_w, canvas_h):
        frame = self.get_frame()
        c = frame["centroid"]

        if c is None:
            return None

        cx = self.map_x(c[0], canvas_w)
        cy = self.map_y(c[1], canvas_h)

        return cx, cy

    # ===== max point =====
    def get_max_point(self, canvas_w, canvas_h):
        frame = self.get_frame()
        h = frame["highlight"]

        if h is None:
            return None

        px, py = h["max_point"]

        px = self.map_x(px, canvas_w)
        py = self.map_y(py, canvas_h)

        return px, py

    # ===== bbox =====
    def get_bbox(self, canvas_w, canvas_h):
        frame = self.get_frame()
        h = frame["highlight"]

        if h is None:
            return None

        x, y, w, h = h["bbox"]

        x = self.map_x(x, canvas_w)
        y = self.map_y(y, canvas_h)
        w = w * canvas_w / self.video_w
        h = h * canvas_h / self.video_h

        return x, y, w, h

    # ===== mask采样（核心）=====
    def sample_mask(self, x, y, canvas_w, canvas_h):
        mask = self.get_mask()
        h, w = mask.shape

        mx = int(x / canvas_w * w)
        my = int(y / canvas_h * h)

        mx = max(0, min(mx, w - 1))
        my = max(0, min(my, h - 1))

        return mask[my][mx] / 255.0  # 返回0~1



#======================================================
#===============main part代码的主体部分===============
#变量==========
video_manager = VideoProcessor(r"resource\water1_of1_1080")
video_manager_2 = VideoProcessor(r"resource\water_edge")
ascii_effect = AsciiLayer(font_size=16, resolution=8)
#renderer = TrackRenderer(1920, 1080, r"resource\data\hc2_data\tracks_coords.npy", r"D:\kit\Shen_Nan\2026\graduate\official_version\resource\data\hc2_data\tracks_visibility.npy", 1/3)
light = LightData(
        r"resource\data\watersun_data\highlight_data.json",
        r"resource\data\watersun_data\softmask.npy",
        1920, 1080
    )

#ui_font = py5.create_font("kochi-mincho-2", 32)
ui_font = None
data_font = None

#变量==========





def setup():
    py5.size(1920, 1080, py5.P2D) # P2D 使用 GPU 渲染
    py5.background(0) #黑底
    ascii_effect.setup()
    #renderer.setup()
    global ascii_image
    global ui_font 
    global data_font
    ui_font  = py5.create_font(r"resource\font\kochi-mincho-2.ttf", 32)
    data_font = py5.create_font(r"resource\font\Helvetica.ttf", 32)
    



def draw():
    py5.background(255)
    py5.background("#C4C4C4")#暂时改成了灰色
    

    # 1. 逻辑更新（获取当前帧坐标、计算物理等）
    
    current_idx = py5.frame_count - 1
    success = video_manager.update_frame(current_idx) and video_manager_2.update_frame(current_idx)
    

    if success:
        current_frame_img , current_edge =  update_data(current_idx)
        
    
        # 3. 渲染原视频图层
        draw_original_video_overlay(current_edge)
    
        # 2. 渲染ASCII
        draw_background_layer(current_frame_img)
    
        
        
        # 4. 渲染核心追踪轨迹层（根据你获取的 .npy 数据）
        draw_tracking_visuals(current_idx)
    
        # 5. 渲染顶层 UI/纹理覆盖
        draw_foreground_texture(current_idx)
    
        # 6. 导出（如果需要）
        py5.save_frame(r"final_output\water_output\water2\frame_####.png")

    else:
        print("所有帧处理完毕。")
        py5.no_loop()





#自定义函数

def update_data(idx):
    
    return(video_manager.curr_frame_img , video_manager_2.curr_frame_img)

def draw_background_layer(current_frame):#并不是真正的“黑底”那一层，而是黑底之上的最下一层
    
    ascii_effect.draw(current_frame, threshold=165) #这里控制的是最低亮度，低于这个亮度的就不显示字符

def draw_tracking_visuals(current_idx):
    #renderer.render(current_idx , ui_font)
    centroid = light.get_centroid(py5.width, py5.height)
    max_point = light.get_max_point(py5.width, py5.height)
    bbox = light.get_bbox(py5.width, py5.height)
    title = "The Sun"
    size = 28
    # ---- 画 centroid 重心----
    if centroid:
        py5.fill("#99FF00")
        py5.no_stroke()
        py5.circle(centroid[0], centroid[1], 18)
        label_size = 20
        cortext = str(centroid[0]) + "," + str(centroid[1])
        py5.fill("#C4C4C4")
        py5.no_stroke
        py5.rect((centroid[0] + 9), (centroid[1] - 9 - label_size - 2), (py5.text_width(cortext) + 2), (size + 2))
        py5.fill("#99FF00")
        #py5.fill(0)
        py5.text_font(data_font)
        py5.text_size(label_size)
        py5.text(cortext, (centroid[0] + 9 + 1),  (centroid[1] - 9 - 1))
    # ---- 画 max_point ----
    if max_point:
        py5.fill("#99FF00")
        py5.no_stroke()
        py5.circle(max_point[0], max_point[1], 10)

    #画虚线连线
    py5.stroke("#99FF00")
    py5.stroke_weight(3)
    draw_dashed_line(centroid[0], centroid[1], max_point[0], max_point[1], 5, 10)

    if bbox:
        x, y, w, h = bbox

        py5.no_fill()
        py5.stroke_weight(4)
        py5.stroke("#99FF00")
        py5.rect(x, y, w, h)

        py5.fill("#99FF00")
        py5.text_size(size)
        py5.rect((x+w-py5.text_width(title) - 4), y-size, py5.text_width(title) + 4 , (size-4))
        py5.fill(255)
        
        py5.text(title,(x+w-py5.text_width(title) - 2) , (y-4))

    

    # ---- 下一帧 ----
    light.next_frame()







#==============UI层，最上层=================
#这段可以改，写的复用率比较低了
def draw_foreground_texture(frame_idx):
    
   
    #写关键词
    py5.text_font(ui_font)
    py5.text_size(36)
    py5.fill(0)
    text_line1 = "Dancing Sun.."
    #py5.text(text_line1 ,1420,936)
    _draw_glowing_text(text_line1 , 1430, 960, 36, ui_font)
    #py5.fill("#99FF00")
    text_line2 = "<Wave> <Light> <Refelction>"
    py5.text_size(20)
    py5.text(text_line2, 1430,982)
    #py5.text("Trace",320,972)




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
    py5.fill(glow_color, 50)
    for i in range(-3, 4, 3): # 偏移量 -3, 0, 3
        for j in range(-3, 4, 3):
            py5.text(text_str, x + i, y + j)

    # 第三级：近距离 (强发光区)
    py5.fill(glow_color, 80)
    offsets_near = [-1.5, 1.5]
    for ox in offsets_near:
        for oy in offsets_near:
            py5.text(text_str, x + ox, y + oy)

    # 4. 核心层 (第三层，纯白或极亮绿)
    # 使用白色作为中心可以增加“光亮感”
    py5.fill(0) 
    py5.text(text_str, x, y)
    #py5.text(text_str, x-1, y)
    #py5.text(text_str, x+1, y)
    #py5.text(text_str, x, y+1)
    #py5.text(text_str, x, y-1)




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
def draw_original_video_overlay(current_frame):
    py5.image(current_frame, 0, 0)
    #绘制一个mask（分栏的遮罩）
    #py5.fill(0)# 设置填充颜色为黑色 (0 代表黑色)
    #py5.no_stroke()
    #py5.rect(760, 180, 10, 720) # 在坐标 () 处画一个宽 / 高 / 的矩形，第一个是左上角坐标
    #py5.rect(1290, 180, 10, 720)




py5.run_sketch()