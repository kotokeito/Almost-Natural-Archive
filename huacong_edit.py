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


    


#======================================================
#===============main part代码的主体部分===============
#变量==========
video_manager = VideoProcessor(r"resource\hc2_green_isolated")
ascii_effect = AsciiLayer(font_size=24, resolution=8)
renderer = TrackRenderer(1920, 1080, r"resource\data\hc2_data\tracks_coords.npy", r"D:\kit\Shen_Nan\2026\graduate\official_version\resource\data\hc2_data\tracks_visibility.npy", 1/3)
#ui_font = py5.create_font("kochi-mincho-2", 32)
ui_font = None
textlist_timeandloc = ["04/04/2026  ", "GongQing Forest Park ", "Shanghai, China"]
#变量==========





def setup():
    py5.size(1920, 1080, py5.P2D) # P2D 使用 GPU 渲染
    py5.background(0) #黑底
    ascii_effect.setup()
    renderer.setup()
    global ascii_image
    global ui_font 
    ui_font  = py5.create_font(r"resource\font\kochi-mincho-2.ttf", 32)
    



def draw():
    py5.background("#C4C4C4")#暂时改成了灰色
    #py5.background(255)

    # 1. 逻辑更新（获取当前帧坐标、计算物理等）
    
    current_idx = py5.frame_count - 1
    success = video_manager.update_frame(current_idx)
    

    if success:
        current_frame_img = update_data(current_idx)
    
        # 2. 渲染背景层
        #draw_background_layer(current_frame_img)
    
        # 3. 渲染原视频图层
        #draw_original_video_overlay(current_frame_img)
    
        # 4. 渲染核心追踪轨迹层（根据你获取的 .npy 数据）
        draw_tracking_visuals(current_idx)
    
        # 5. 渲染顶层 UI/纹理覆盖
        #draw_foreground_texture(textlist_timeandloc, current_idx)
    
        # 6. 导出（如果需要）
        py5.save_frame(r"final_output\hc2_output\hc2_x\frame_####.png")

    else:
        print("所有帧处理完毕。")
        py5.no_loop()





#自定义函数

def update_data(idx):
    
    return(video_manager.curr_frame_img)

def draw_background_layer(current_frame):#并不是真正的“黑底”那一层，而是黑底之上的最下一层
    
    ascii_effect.draw(current_frame, threshold=150) #这里控制的是最低亮度，低于这个亮度的就不显示字符

def draw_tracking_visuals(current_idx):
    renderer.render(current_idx , ui_font)








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
    #画斜线====================
    #定位：
    #py5.line(128,1080,128,1065)
    #py5.line(1354,0,1354,15)
    #py5.stroke_weight(1)
    #draw_dashed_line(1354,0,128,1080)


    #写地点信息
    #textlist = ["04/04/2026  13:05:25", "GongQing Forest Park ", "Shanghai, China"]
    time_str = calculated_time(frame_idx, "13:05:25")
    text_time_and_location(textlist, time_str, 32, 0)

    #写关键词
    py5.text_font(ui_font)
    py5.text_size(36)
    py5.fill(255)
    py5.text("Wind",320,936)
    py5.fill("#99FF00")
    py5.text("Trace",320,972)

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