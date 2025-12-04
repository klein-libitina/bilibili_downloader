"""
Bilibili视频下载器GUI
支持音视频分离下载、多清晰度、Hi-Res音频、格式选择
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
from PIL import Image, ImageTk
import threading
import os
from bilibili_api import BilibiliAPI


class BilibiliDownloaderGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Bilibili视频下载器")
        self.root.geometry("700x850")
        self.root.resizable(False, False)

        self.api = BilibiliAPI()
        self.qrcode_key = None
        self.check_thread = None
        self.is_checking = False
        self.video_qualities = []
        self.audio_qualities = []

        self.setup_ui()

        # 尝试自动恢复登录状态
        self.root.after(100, self.try_auto_login)

    def setup_ui(self):
        """设置UI界面"""
        # 标题
        title_label = tk.Label(
            self.root,
            text="Bilibili视频下载器 Pro",
            font=("Arial", 18, "bold"),
            fg="#00A1D6"
        )
        title_label.pack(pady=10)

        # 登录状态框架
        login_frame = tk.LabelFrame(self.root, text="登录状态", padx=10, pady=10)
        login_frame.pack(padx=20, pady=5, fill="x")

        self.login_status_label = tk.Label(
            login_frame,
            text="未登录 (部分高清内容需要登录)",
            font=("Arial", 9),
            fg="red"
        )
        self.login_status_label.pack(side="left")

        # 按钮容器
        button_container = tk.Frame(login_frame)
        button_container.pack(side="right")

        self.login_button = tk.Button(
            button_container,
            text="扫码登录",
            command=self.show_login_window,
            bg="#00A1D6",
            fg="white",
            padx=15,
            pady=5
        )
        self.login_button.pack(side="left", padx=2)

        self.logout_button = tk.Button(
            button_container,
            text="退出登录",
            command=self.logout,
            bg="#999999",
            fg="white",
            padx=15,
            pady=5,
            state="disabled"
        )
        self.logout_button.pack(side="left", padx=2)

        # 视频URL输入框架
        url_frame = tk.LabelFrame(self.root, text="视频地址", padx=10, pady=10)
        url_frame.pack(padx=20, pady=5, fill="x")

        self.url_entry = tk.Entry(url_frame, font=("Arial", 10))
        self.url_entry.pack(fill="x")

        # 获取信息按钮
        self.get_info_button = tk.Button(
            url_frame,
            text="获取视频信息",
            command=self.get_video_info,
            bg="#00A1D6",
            fg="white",
            font=("Arial", 10, "bold"),
            padx=20,
            pady=5
        )
        self.get_info_button.pack(pady=5)

        # 视频信息框架
        info_frame = tk.LabelFrame(self.root, text="视频信息", padx=10, pady=10)
        info_frame.pack(padx=20, pady=5, fill="x")

        self.info_text = tk.Text(
            info_frame,
            height=4,
            wrap=tk.WORD,
            font=("Arial", 9),
            state="disabled"
        )
        self.info_text.pack(fill="x")

        # 下载选项框架
        options_frame = tk.LabelFrame(self.root, text="下载选项", padx=10, pady=10)
        options_frame.pack(padx=20, pady=5, fill="both", expand=True)

        # 下载类型
        type_frame = tk.Frame(options_frame)
        type_frame.pack(fill="x", pady=5)

        tk.Label(type_frame, text="下载类型:", font=("Arial", 10, "bold")).pack(anchor="w")

        self.download_type_var = tk.StringVar(value="merged")
        download_types = [
            ("视频+音频(合并)", "merged"),
            ("仅视频", "video_only"),
            ("仅音频", "audio_only")
        ]

        type_buttons_frame = tk.Frame(type_frame)
        type_buttons_frame.pack(anchor="w", padx=20)

        for text, value in download_types:
            rb = tk.Radiobutton(
                type_buttons_frame,
                text=text,
                variable=self.download_type_var,
                value=value,
                command=self.on_download_type_change
            )
            rb.pack(side="left", padx=5)

        # 视频清晰度选择
        self.video_quality_frame = tk.Frame(options_frame)
        # 不立即pack，由on_download_type_change控制

        tk.Label(self.video_quality_frame, text="视频清晰度:", font=("Arial", 10, "bold")).pack(anchor="w")

        self.video_quality_var = tk.StringVar()
        self.video_quality_menu_frame = tk.Frame(self.video_quality_frame)
        self.video_quality_menu_frame.pack(anchor="w", padx=20, fill="x")

        self.video_quality_listbox = tk.Listbox(
            self.video_quality_menu_frame,
            height=4,
            font=("Arial", 9)
        )
        self.video_quality_listbox.pack(fill="x")
        self.video_quality_listbox.insert(0, "请先获取视频信息")
        self.video_quality_listbox.config(state="disabled")

        # 音频质量选择
        self.audio_quality_frame = tk.Frame(options_frame)
        # 不立即pack，由on_download_type_change控制

        tk.Label(self.audio_quality_frame, text="音频质量:", font=("Arial", 10, "bold")).pack(anchor="w")

        self.audio_quality_var = tk.StringVar()
        self.audio_quality_menu_frame = tk.Frame(self.audio_quality_frame)
        self.audio_quality_menu_frame.pack(anchor="w", padx=20, fill="x")

        self.audio_quality_listbox = tk.Listbox(
            self.audio_quality_menu_frame,
            height=3,
            font=("Arial", 9)
        )
        self.audio_quality_listbox.pack(fill="x")
        self.audio_quality_listbox.insert(0, "请先获取视频信息")
        self.audio_quality_listbox.config(state="disabled")

        # 绑定音频质量选择事件
        self.audio_quality_listbox.bind('<<ListboxSelect>>', self.on_audio_quality_change)

        # 输出格式选择 - 视频格式
        self.video_format_frame = tk.Frame(options_frame)
        # 不立即pack，由on_download_type_change控制

        tk.Label(self.video_format_frame, text="输出格式:", font=("Arial", 10, "bold")).pack(anchor="w")

        self.output_format_var = tk.StringVar(value="mp4")

        video_format_buttons = tk.Frame(self.video_format_frame)
        video_format_buttons.pack(anchor="w", padx=20)

        self.video_formats = [("MP4", "mp4"), ("FLV", "flv")]
        for text, value in self.video_formats:
            rb = tk.Radiobutton(
                video_format_buttons,
                text=text,
                variable=self.output_format_var,
                value=value
            )
            rb.pack(side="left", padx=5)

        # 输出格式选择 - 音频格式
        self.audio_format_frame = tk.Frame(options_frame)
        # 不立即pack，由on_download_type_change控制

        tk.Label(self.audio_format_frame, text="输出格式:", font=("Arial", 10, "bold")).pack(anchor="w")

        audio_format_buttons = tk.Frame(self.audio_format_frame)
        audio_format_buttons.pack(anchor="w", padx=20)

        self.audio_formats = [
            ("MP3", "mp3"),
            ("FLAC (无损)", "flac"),
            ("WAV (无损)", "wav"),
            ("M4A", "m4a"),
            ("AAC", "aac")
        ]
        for text, value in self.audio_formats:
            rb = tk.Radiobutton(
                audio_format_buttons,
                text=text,
                variable=self.output_format_var,
                value=value
            )
            rb.pack(side="left", padx=3)

        # 下载按钮
        self.download_button = tk.Button(
            self.root,
            text="开始下载",
            command=self.start_download,
            bg="#FB7299",
            fg="white",
            font=("Arial", 12, "bold"),
            padx=40,
            pady=10,
            state="disabled"
        )
        self.download_button.pack(pady=10)

        # 进度条
        progress_frame = tk.Frame(self.root)
        progress_frame.pack(padx=20, pady=5, fill="x")

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            progress_frame,
            variable=self.progress_var,
            maximum=100
        )
        self.progress_bar.pack(fill="x")

        self.progress_label = tk.Label(self.root, text="", font=("Arial", 9))
        self.progress_label.pack()

        # 更新初始状态
        self.on_download_type_change()

    def on_download_type_change(self):
        """下载类型改变时的处理"""
        download_type = self.download_type_var.get()

        # 先隐藏所有质量和格式选项
        self.video_quality_frame.pack_forget()
        self.audio_quality_frame.pack_forget()
        self.video_format_frame.pack_forget()
        self.audio_format_frame.pack_forget()

        if download_type == "video_only":
            # 仅视频：显示视频清晰度和视频格式
            self.video_quality_frame.pack(fill="x", pady=5)
            self.video_format_frame.pack(fill="x", pady=5)
            # 默认选择MP4
            if self.output_format_var.get() not in ["mp4", "flv"]:
                self.output_format_var.set("mp4")

        elif download_type == "audio_only":
            # 仅音频：显示音频质量和音频格式
            self.audio_quality_frame.pack(fill="x", pady=5)
            self.audio_format_frame.pack(fill="x", pady=5)
            # 默认选择MP3
            if self.output_format_var.get() not in ["mp3", "flac", "wav", "m4a", "aac"]:
                self.output_format_var.set("mp3")

        else:  # merged
            # 合并：显示视频清晰度、音频质量和视频格式
            self.video_quality_frame.pack(fill="x", pady=5)
            self.audio_quality_frame.pack(fill="x", pady=5)
            self.video_format_frame.pack(fill="x", pady=5)
            # 默认选择MP4
            if self.output_format_var.get() not in ["mp4", "flv"]:
                self.output_format_var.set("mp4")

    def on_audio_quality_change(self, event=None):
        """音频质量选择改变时的处理 - 自动切换到最佳格式"""
        # 只在仅音频模式下自动切换
        if self.download_type_var.get() != "audio_only":
            return

        # 获取选中的音频质量
        selection = self.audio_quality_listbox.curselection()
        if not selection or not hasattr(self, 'audio_qualities'):
            return

        selected_idx = selection[0]
        if selected_idx >= len(self.audio_qualities):
            return

        selected_quality = self.audio_qualities[selected_idx]

        # 如果选择了Hi-Res无损，自动切换到FLAC格式
        if selected_quality['name'] == "Hi-Res无损":
            self.output_format_var.set("flac")
            # 可选：显示提示
            self.progress_label.config(
                text="✨ 已自动选择FLAC格式以保留Hi-Res无损音质",
                fg="#00A1D6"
            )
        else:
            # 恢复提示文字颜色
            self.progress_label.config(text="", fg="black")

    def try_auto_login(self):
        """尝试自动恢复登录状态"""
        def load_login():
            success, message = self.api.load_login_state()

            if success:
                # 自动登录成功
                self.login_status_label.config(
                    text="已登录（自动恢复） - 可下载高清内容",
                    fg="green"
                )
                self.logout_button.config(state="normal")
                self.progress_label.config(
                    text=f"✅ {message}",
                    fg="green"
                )
                # 3秒后清除提示
                self.root.after(3000, lambda: self.progress_label.config(text="", fg="black"))
            else:
                # 自动登录失败，如果不是"无保存的登录状态"就显示原因
                if "无保存的登录状态" not in message:
                    self.progress_label.config(
                        text=f"ℹ️ {message}",
                        fg="orange"
                    )
                    # 5秒后清除提示
                    self.root.after(5000, lambda: self.progress_label.config(text="", fg="black"))

        # 在后台线程中加载
        thread = threading.Thread(target=load_login, daemon=True)
        thread.start()

    def logout(self):
        """退出登录"""
        result = messagebox.askyesno("确认", "确定要退出登录吗？")
        if result:
            self.api.clear_login_state()
            self.login_status_label.config(
                text="未登录 (部分高清内容需要登录)",
                fg="red"
            )
            self.logout_button.config(state="disabled")
            self.progress_label.config(text="已退出登录", fg="gray")
            self.root.after(2000, lambda: self.progress_label.config(text="", fg="black"))

    def show_login_window(self):
        """显示登录窗口"""
        login_window = tk.Toplevel(self.root)
        login_window.title("扫码登录")
        login_window.geometry("350x450")
        login_window.resizable(False, False)

        qr_img, qrcode_key, error = self.api.generate_qr_code()

        if error:
            messagebox.showerror("错误", error)
            login_window.destroy()
            return

        self.qrcode_key = qrcode_key

        qr_label = tk.Label(login_window, text="请使用Bilibili APP扫描二维码", font=("Arial", 12))
        qr_label.pack(pady=15)

        qr_img = qr_img.resize((280, 280), Image.Resampling.LANCZOS)
        qr_photo = ImageTk.PhotoImage(qr_img)

        img_label = tk.Label(login_window, image=qr_photo)
        img_label.image = qr_photo
        img_label.pack(pady=10)

        status_label = tk.Label(
            login_window,
            text="等待扫码...",
            font=("Arial", 10),
            fg="blue"
        )
        status_label.pack(pady=10)

        self.is_checking = True

        def check_login_status():
            while self.is_checking:
                if not self.qrcode_key:
                    break

                status, message = self.api.check_qr_status(self.qrcode_key)

                status_label.config(text=message)

                if status == 'success':
                    self.login_status_label.config(text="已登录 (可下载高清内容)", fg="green")
                    self.logout_button.config(state="normal")
                    messagebox.showinfo("成功", "登录成功！现在可以下载高清和Hi-Res内容了")
                    self.is_checking = False
                    login_window.destroy()
                    break
                elif status == 'expired':
                    status_label.config(text=message, fg="red")
                    self.is_checking = False
                    break
                elif status == 'error':
                    status_label.config(text=message, fg="red")
                    self.is_checking = False
                    break

                threading.Event().wait(2)

        def on_closing():
            self.is_checking = False
            login_window.destroy()

        login_window.protocol("WM_DELETE_WINDOW", on_closing)

        self.check_thread = threading.Thread(target=check_login_status, daemon=True)
        self.check_thread.start()

    def get_video_info(self):
        """获取视频信息"""
        url = self.url_entry.get().strip()

        if not url:
            messagebox.showwarning("警告", "请输入视频URL")
            return

        self.info_text.config(state="normal")
        self.info_text.delete(1.0, tk.END)
        self.info_text.insert(tk.END, "正在获取视频信息...")
        self.info_text.config(state="disabled")

        self.get_info_button.config(state="disabled")

        def fetch_info():
            video_info, error = self.api.get_video_info(url)

            if error:
                self.info_text.config(state="normal")
                self.info_text.delete(1.0, tk.END)
                self.info_text.insert(tk.END, f"错误: {error}")
                self.info_text.config(state="disabled")
                self.download_button.config(state="disabled")
                self.get_info_button.config(state="normal")
                return

            self.video_info = video_info

            info_str = f"标题: {video_info['title']}\n"
            info_str += f"UP主: {video_info['owner']['name']}\n"
            info_str += f"时长: {video_info['duration']}秒 | "
            info_str += f"播放: {video_info['stat']['view']}"

            self.info_text.config(state="normal")
            self.info_text.delete(1.0, tk.END)
            self.info_text.insert(tk.END, info_str)
            self.info_text.config(state="disabled")

            # 获取可用清晰度
            bvid = video_info['bvid']
            cid = video_info['cid']

            video_qualities, audio_qualities, error = self.api.get_available_qualities(bvid, cid)

            if error:
                messagebox.showerror("错误", f"获取清晰度失败: {error}")
                self.get_info_button.config(state="normal")
                return

            self.video_qualities = video_qualities
            self.audio_qualities = audio_qualities

            # 更新视频清晰度列表
            self.video_quality_listbox.config(state="normal")
            self.video_quality_listbox.delete(0, tk.END)

            if video_qualities:
                for i, q in enumerate(video_qualities):
                    display_text = f"{q['name']}"
                    if q['width'] and q['height']:
                        display_text += f" ({q['width']}x{q['height']})"
                    self.video_quality_listbox.insert(tk.END, display_text)

                self.video_quality_listbox.selection_set(0)
            else:
                self.video_quality_listbox.insert(0, "无可用视频流")
                self.video_quality_listbox.config(state="disabled")

            # 更新音频质量列表
            self.audio_quality_listbox.config(state="normal")
            self.audio_quality_listbox.delete(0, tk.END)

            if audio_qualities:
                for i, q in enumerate(audio_qualities):
                    display_text = q['name']
                    if q['name'] == "Hi-Res无损":
                        display_text += " ⭐"
                    self.audio_quality_listbox.insert(tk.END, display_text)

                self.audio_quality_listbox.selection_set(0)
            else:
                self.audio_quality_listbox.insert(0, "无可用音频流")
                self.audio_quality_listbox.config(state="disabled")

            self.download_button.config(state="normal")
            self.get_info_button.config(state="normal")

        thread = threading.Thread(target=fetch_info, daemon=True)
        thread.start()

    def start_download(self):
        """开始下载"""
        if not hasattr(self, 'video_info'):
            messagebox.showwarning("警告", "请先获取视频信息")
            return

        download_type = self.download_type_var.get()

        # 获取选中的清晰度
        video_qn = None
        audio_qn = None

        if download_type in ["merged", "video_only"]:
            selection = self.video_quality_listbox.curselection()
            if not selection:
                messagebox.showwarning("警告", "请选择视频清晰度")
                return
            video_qn = self.video_qualities[selection[0]]['id']

        if download_type in ["merged", "audio_only"]:
            selection = self.audio_quality_listbox.curselection()
            if not selection:
                messagebox.showwarning("警告", "请选择音频质量")
                return
            audio_qn = self.audio_qualities[selection[0]]['id']

        # 检查登录状态（高清内容）
        if video_qn and video_qn >= 80 and not self.api.is_logged_in:
            result = messagebox.askyesno(
                "提示",
                "高清内容建议登录后下载以获得最佳质量，是否继续？"
            )
            if not result:
                return

        # 选择保存路径
        output_format = self.output_format_var.get()
        default_filename = f"{self.video_info['title']}.{output_format}"
        default_filename = "".join(c for c in default_filename if c not in r'\/:*?"<>|')

        filetypes = []
        if output_format == "mp4":
            filetypes = [("MP4视频", "*.mp4"), ("所有文件", "*.*")]
        elif output_format == "flv":
            filetypes = [("FLV视频", "*.flv"), ("所有文件", "*.*")]
        elif output_format == "m4a":
            filetypes = [("M4A音频", "*.m4a"), ("所有文件", "*.*")]
        elif output_format == "mp3":
            filetypes = [("MP3音频", "*.mp3"), ("所有文件", "*.*")]
        elif output_format == "flac":
            filetypes = [("FLAC无损音频", "*.flac"), ("所有文件", "*.*")]
        elif output_format == "wav":
            filetypes = [("WAV音频", "*.wav"), ("所有文件", "*.*")]
        elif output_format == "aac":
            filetypes = [("AAC音频", "*.aac"), ("所有文件", "*.*")]

        save_path = filedialog.asksaveasfilename(
            defaultextension=f".{output_format}",
            initialfile=default_filename,
            filetypes=filetypes
        )

        if not save_path:
            return

        self.download_button.config(state="disabled")
        self.get_info_button.config(state="disabled")
        self.progress_var.set(0)

        def download():
            bvid = self.video_info['bvid']
            cid = self.video_info['cid']

            # 获取下载链接
            video_url, audio_url, video_size, audio_size, error = self.api.get_download_urls(
                bvid, cid, video_qn if video_qn else 80, audio_qn if audio_qn else 30216
            )

            if error:
                messagebox.showerror("错误", error)
                self.download_button.config(state="normal")
                self.get_info_button.config(state="normal")
                return

            def progress_callback(progress, downloaded, total, desc=""):
                self.progress_var.set(progress)
                if total > 0:
                    size_mb = downloaded / (1024 * 1024)
                    total_mb = total / (1024 * 1024)
                    self.progress_label.config(
                        text=f"{desc}: {size_mb:.2f}MB / {total_mb:.2f}MB ({progress:.1f}%)"
                    )
                else:
                    self.progress_label.config(text=desc)

            try:
                if download_type == "video_only":
                    # 仅下载视频
                    if output_format == "mp4" and save_path.endswith('.mp4'):
                        temp_path = save_path.replace('.mp4', '_temp.m4s')
                    else:
                        temp_path = save_path

                    success, message = self.api.download_file(
                        video_url, temp_path, progress_callback, "下载视频"
                    )

                    if not success:
                        messagebox.showerror("错误", message)
                        return

                    # 转换格式
                    if output_format == "mp4" and temp_path != save_path:
                        success, message = self.api.convert_to_mp4(
                            temp_path, save_path, progress_callback
                        )
                        if not success:
                            messagebox.showerror("错误", message)
                            return

                elif download_type == "audio_only":
                    # 仅下载音频
                    temp_path = save_path.replace(f'.{output_format}', '_temp.m4s')

                    success, message = self.api.download_file(
                        audio_url, temp_path, progress_callback, "下载音频"
                    )

                    if not success:
                        messagebox.showerror("错误", message)
                        return

                    # 转换格式 - 使用新的音频格式转换函数
                    self.progress_var.set(0)
                    success, message = self.api.convert_audio_format(
                        temp_path, save_path, output_format, progress_callback
                    )
                    if not success:
                        messagebox.showerror("错误", message)
                        return

                else:  # merged
                    # 下载视频和音频并合并
                    base_path = save_path.replace(f'.{output_format}', '')
                    video_temp = base_path + '_video.m4s'
                    audio_temp = base_path + '_audio.m4s'

                    # 下载视频
                    success, message = self.api.download_file(
                        video_url, video_temp, progress_callback, "下载视频"
                    )

                    if not success:
                        messagebox.showerror("错误", message)
                        return

                    # 下载音频
                    self.progress_var.set(0)
                    success, message = self.api.download_file(
                        audio_url, audio_temp, progress_callback, "下载音频"
                    )

                    if not success:
                        messagebox.showerror("错误", message)
                        return

                    # 合并
                    self.progress_var.set(0)
                    if output_format == "mp4":
                        success, message = self.api.merge_video_audio(
                            video_temp, audio_temp, save_path, progress_callback
                        )
                    else:  # flv
                        # FLV格式先合并为MP4再转换
                        temp_mp4 = base_path + '_temp.mp4'
                        success, message = self.api.merge_video_audio(
                            video_temp, audio_temp, temp_mp4, progress_callback
                        )
                        if success:
                            success, message = self.api.convert_to_mp4(
                                temp_mp4, save_path, progress_callback
                            )

                    if not success:
                        messagebox.showerror("错误", message)
                        return

                messagebox.showinfo("成功", f"下载完成！\n保存位置: {save_path}")
                self.progress_label.config(text="下载完成")

            except Exception as e:
                messagebox.showerror("错误", f"下载出错: {str(e)}")
                self.progress_label.config(text="下载失败")

            finally:
                self.download_button.config(state="normal")
                self.get_info_button.config(state="normal")

        thread = threading.Thread(target=download, daemon=True)
        thread.start()


def main():
    root = tk.Tk()
    app = BilibiliDownloaderGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()

