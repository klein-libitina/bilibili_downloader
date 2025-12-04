"""
Bilibili API客户端
支持二维码登录、音视频分离下载、多清晰度、Hi-Res音频
支持登录状态持久化
"""
import requests
import time
import json
import qrcode
import os
import subprocess
from io import BytesIO
from PIL import Image


class BilibiliAPI:
    # 清晰度映射
    QUALITY_MAP = {
        127: "8K超高清",
        126: "杜比视界",
        125: "HDR真彩",
        120: "4K超清",
        116: "1080P 60帧",
        112: "1080P+高码率",
        80: "1080P高清",
        74: "720P 60帧",
        64: "720P高清",
        32: "480P清晰",
        16: "360P流畅"
    }

    # 音频质量映射
    AUDIO_QUALITY_MAP = {
        30280: "Hi-Res无损",
        30232: "320K极高",
        30216: "128K高清",
        30210: "64K流畅"
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.bilibili.com'
        })
        self.cookies = {}
        self.is_logged_in = False

        # 登录状态保存文件
        self.login_data_file = os.path.join(os.path.dirname(__file__), '.bili_login.json')

    def generate_qr_code(self):
        """生成登录二维码"""
        try:
            url = 'https://passport.bilibili.com/x/passport-login/web/qrcode/generate'
            response = self.session.get(url)
            data = response.json()

            if data['code'] != 0:
                return None, None, "获取二维码失败"

            qr_url = data['data']['url']
            qrcode_key = data['data']['qrcode_key']

            qr = qrcode.QRCode(version=1, box_size=10, border=2)
            qr.add_data(qr_url)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")

            buffered = BytesIO()
            img.save(buffered, format="PNG")
            buffered.seek(0)
            pil_img = Image.open(buffered)

            return pil_img, qrcode_key, None

        except Exception as e:
            return None, None, f"生成二维码出错: {str(e)}"

    def check_qr_status(self, qrcode_key):
        """检查二维码扫描状态"""
        try:
            url = 'https://passport.bilibili.com/x/passport-login/web/qrcode/poll'
            params = {'qrcode_key': qrcode_key}
            response = self.session.get(url, params=params)
            data = response.json()

            code = data['data']['code']

            if code == 0:
                self.cookies = dict(self.session.cookies)
                self.is_logged_in = True

                if 'SESSDATA' in self.cookies:
                    # 保存登录状态
                    self.save_login_state()
                    return 'success', '登录成功'
                else:
                    return 'error', '登录失败: 未获取到有效凭证'

            elif code == 86101:
                return 'waiting', '等待扫码...'
            elif code == 86090:
                return 'scanned', '已扫码，请在手机上确认'
            elif code == 86038:
                return 'expired', '二维码已失效'
            else:
                return 'error', f'未知状态码: {code}'

        except Exception as e:
            return 'error', f'检查状态出错: {str(e)}'

    def get_current_ip(self):
        """获取当前公网IP地址"""
        try:
            # 使用多个IP检测服务作为备选
            services = [
                'https://api.ipify.org?format=json',
                'https://api64.ipify.org?format=json',
                'https://ifconfig.me/ip'
            ]

            for service in services:
                try:
                    response = requests.get(service, timeout=5)
                    if response.status_code == 200:
                        if 'json' in service:
                            return response.json().get('ip', '')
                        else:
                            return response.text.strip()
                except:
                    continue

            return None
        except Exception as e:
            return None

    def save_login_state(self):
        """保存登录状态（cookies和IP）"""
        try:
            current_ip = self.get_current_ip()

            login_data = {
                'cookies': self.cookies,
                'ip': current_ip,
                'timestamp': time.time()
            }

            with open(self.login_data_file, 'w', encoding='utf-8') as f:
                json.dump(login_data, f, ensure_ascii=False, indent=2)

            return True
        except Exception as e:
            print(f"保存登录状态失败: {e}")
            return False

    def load_login_state(self):
        """
        加载保存的登录状态
        返回: (success, message)
        """
        try:
            # 检查文件是否存在
            if not os.path.exists(self.login_data_file):
                return False, "无保存的登录状态"

            # 读取登录数据
            with open(self.login_data_file, 'r', encoding='utf-8') as f:
                login_data = json.load(f)

            saved_cookies = login_data.get('cookies', {})
            saved_ip = login_data.get('ip')
            saved_time = login_data.get('timestamp', 0)

            # 检查是否有有效的cookies
            if not saved_cookies or 'SESSDATA' not in saved_cookies:
                return False, "登录数据无效"

            # 检查保存时间（30天过期）
            if time.time() - saved_time > 30 * 24 * 3600:
                self.clear_login_state()
                return False, "登录已过期（超过30天）"

            # 检查IP是否变化
            current_ip = self.get_current_ip()
            if current_ip and saved_ip and current_ip != saved_ip:
                self.clear_login_state()
                return False, f"IP地址已变化（{saved_ip} → {current_ip}），请重新登录"

            # 验证cookies是否有效
            self.cookies = saved_cookies
            self.session.cookies.update(saved_cookies)

            if self.validate_cookies():
                self.is_logged_in = True
                return True, "自动登录成功"
            else:
                self.clear_login_state()
                return False, "登录凭证已失效"

        except Exception as e:
            return False, f"加载登录状态失败: {str(e)}"

    def validate_cookies(self):
        """验证cookies是否有效"""
        try:
            # 调用B站API验证登录状态
            url = 'https://api.bilibili.com/x/web-interface/nav'
            response = self.session.get(url, cookies=self.cookies)
            data = response.json()

            # code为0且isLogin为True表示登录有效
            if data.get('code') == 0 and data.get('data', {}).get('isLogin'):
                return True
            return False
        except:
            return False

    def clear_login_state(self):
        """清除保存的登录状态"""
        try:
            if os.path.exists(self.login_data_file):
                os.remove(self.login_data_file)
            self.cookies = {}
            self.is_logged_in = False
        except:
            pass

    def get_video_info(self, url):
        """获取视频信息"""
        try:
            if 'BV' in url:
                bvid = url.split('BV')[1].split('/')[0].split('?')[0]
                bvid = 'BV' + bvid
                params = {'bvid': bvid}
            elif 'av' in url:
                aid = url.split('av')[1].split('/')[0].split('?')[0]
                params = {'aid': aid}
            else:
                return None, "无效的视频URL"

            info_url = 'https://api.bilibili.com/x/web-interface/view'
            response = self.session.get(info_url, params=params, cookies=self.cookies)
            data = response.json()

            if data['code'] != 0:
                return None, f"获取视频信息失败: {data.get('message', '未知错误')}"

            video_info = data['data']
            return video_info, None

        except Exception as e:
            return None, f"获取视频信息出错: {str(e)}"

    def get_available_qualities(self, bvid, cid):
        """获取视频可用的清晰度列表"""
        try:
            url = 'https://api.bilibili.com/x/player/playurl'
            params = {
                'bvid': bvid,
                'cid': cid,
                'qn': 127,  # 请求最高清晰度以获取完整列表
                'fnval': 4048,  # 支持音视频分离和多种格式
                'fourk': 1
            }

            response = self.session.get(url, params=params, cookies=self.cookies)
            data = response.json()

            if data['code'] != 0:
                return [], [], f"获取清晰度列表失败: {data.get('message', '未知错误')}"

            result = data['data']

            # 获取视频清晰度列表
            video_qualities = []
            if 'dash' in result:
                dash_data = result['dash']

                # 视频流
                if 'video' in dash_data:
                    for video in dash_data['video']:
                        qn = video['id']
                        if qn in self.QUALITY_MAP:
                            video_qualities.append({
                                'id': qn,
                                'name': self.QUALITY_MAP[qn],
                                'bandwidth': video.get('bandwidth', 0),
                                'codecs': video.get('codecs', ''),
                                'width': video.get('width', 0),
                                'height': video.get('height', 0)
                            })

                # 音频流
                audio_qualities = []
                if 'audio' in dash_data:
                    for audio in dash_data['audio']:
                        aq = audio['id']
                        if aq in self.AUDIO_QUALITY_MAP:
                            audio_qualities.append({
                                'id': aq,
                                'name': self.AUDIO_QUALITY_MAP[aq],
                                'bandwidth': audio.get('bandwidth', 0),
                                'codecs': audio.get('codecs', '')
                            })

                return video_qualities, audio_qualities, None

            # 如果没有dash数据，返回传统格式
            accept_quality = result.get('accept_quality', [])
            for qn in accept_quality:
                if qn in self.QUALITY_MAP:
                    video_qualities.append({
                        'id': qn,
                        'name': self.QUALITY_MAP[qn],
                        'bandwidth': 0,
                        'codecs': '',
                        'width': 0,
                        'height': 0
                    })

            return video_qualities, [], None

        except Exception as e:
            return [], [], f"获取清晰度列表出错: {str(e)}"

    def get_download_urls(self, bvid, cid, qn=80, audio_qn=30280):
        """
        获取音视频下载链接（支持分离下载）
        返回: (video_url, audio_url, video_size, audio_size, error)
        """
        try:
            url = 'https://api.bilibili.com/x/player/playurl'
            params = {
                'bvid': bvid,
                'cid': cid,
                'qn': qn,
                'fnval': 4048,  # 音视频分离
                'fourk': 1
            }

            response = self.session.get(url, params=params, cookies=self.cookies)
            data = response.json()

            if data['code'] != 0:
                return None, None, 0, 0, f"获取下载链接失败: {data.get('message', '未知错误')}"

            result = data['data']

            # 优先使用DASH格式（音视频分离）
            if 'dash' in result:
                dash_data = result['dash']

                video_url = None
                video_size = 0
                audio_url = None
                audio_size = 0

                # 获取视频流
                if 'video' in dash_data and len(dash_data['video']) > 0:
                    # 选择匹配的清晰度或最高清晰度
                    video_stream = None
                    for v in dash_data['video']:
                        if v['id'] == qn:
                            video_stream = v
                            break

                    if not video_stream:
                        video_stream = dash_data['video'][0]

                    video_url = video_stream['baseUrl']
                    video_size = video_stream.get('bandwidth', 0) // 8  # 转换为字节

                # 获取音频流
                if 'audio' in dash_data and len(dash_data['audio']) > 0:
                    # 选择匹配的音质或最高音质
                    audio_stream = None
                    for a in dash_data['audio']:
                        if a['id'] == audio_qn:
                            audio_stream = a
                            break

                    if not audio_stream:
                        audio_stream = dash_data['audio'][0]

                    audio_url = audio_stream['baseUrl']
                    audio_size = audio_stream.get('bandwidth', 0) // 8

                return video_url, audio_url, video_size, audio_size, None

            # 传统格式（音视频合并）
            elif 'durl' in result:
                durl = result['durl'][0]
                video_url = durl['url']
                file_size = durl.get('size', 0)
                return video_url, None, file_size, 0, None

            return None, None, 0, 0, "未找到可用的下载链接"

        except Exception as e:
            return None, None, 0, 0, f"获取下载链接出错: {str(e)}"

    def download_file(self, url, save_path, progress_callback=None, desc=""):
        """下载文件"""
        try:
            headers = {
                'User-Agent': self.session.headers['User-Agent'],
                'Referer': 'https://www.bilibili.com',
            }

            response = self.session.get(url, headers=headers, cookies=self.cookies, stream=True)

            if response.status_code != 200:
                return False, f"下载失败: HTTP {response.status_code}"

            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0

            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)

                        if progress_callback and total_size > 0:
                            progress = (downloaded_size / total_size) * 100
                            progress_callback(progress, downloaded_size, total_size, desc)

            return True, "下载完成"

        except Exception as e:
            return False, f"下载出错: {str(e)}"

    def merge_video_audio(self, video_path, audio_path, output_path, progress_callback=None):
        """使用ffmpeg合并音视频"""
        try:
            if progress_callback:
                progress_callback(0, 0, 100, "正在合并音视频")

            # 检查ffmpeg是否可用
            try:
                subprocess.run(['ffmpeg', '-version'],
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             check=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                return False, "未找到ffmpeg，请先安装ffmpeg"

            # 构建ffmpeg命令
            cmd = [
                'ffmpeg',
                '-i', video_path,
                '-i', audio_path,
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-strict', 'experimental',
                '-y',  # 覆盖输出文件
                output_path
            ]

            # 执行合并
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )

            stdout, stderr = process.communicate()

            if process.returncode != 0:
                return False, f"合并失败: {stderr}"

            if progress_callback:
                progress_callback(100, 100, 100, "合并完成")

            # 删除临时文件
            try:
                if os.path.exists(video_path):
                    os.remove(video_path)
                if os.path.exists(audio_path):
                    os.remove(audio_path)
            except:
                pass

            return True, "合并完成"

        except Exception as e:
            return False, f"合并出错: {str(e)}"

    def convert_to_mp4(self, input_path, output_path, progress_callback=None):
        """转换视频格式为MP4"""
        try:
            if progress_callback:
                progress_callback(0, 0, 100, "正在转换格式")

            try:
                subprocess.run(['ffmpeg', '-version'],
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             check=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                return False, "未找到ffmpeg，请先安装ffmpeg"

            cmd = [
                'ffmpeg',
                '-i', input_path,
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-y',
                output_path
            ]

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )

            stdout, stderr = process.communicate()

            if process.returncode != 0:
                return False, f"转换失败: {stderr}"

            if progress_callback:
                progress_callback(100, 100, 100, "转换完成")

            # 删除原文件
            try:
                if os.path.exists(input_path):
                    os.remove(input_path)
            except:
                pass

            return True, "转换完成"

        except Exception as e:
            return False, f"转换出错: {str(e)}"

    def convert_audio_format(self, input_path, output_path, output_format, progress_callback=None):
        """
        转换音频格式
        支持格式: mp3, wav, flac, m4a, aac
        """
        try:
            if progress_callback:
                progress_callback(0, 0, 100, f"正在转换为{output_format.upper()}格式")

            # 检查ffmpeg是否可用
            try:
                subprocess.run(['ffmpeg', '-version'],
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             check=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                return False, "未找到ffmpeg，请先安装ffmpeg"

            # 根据格式选择编码器和参数
            format_settings = {
                'mp3': {
                    'codec': 'libmp3lame',
                    'quality': ['-q:a', '0'],  # VBR最高质量
                    'extra': []
                },
                'wav': {
                    'codec': 'pcm_s16le',
                    'quality': [],
                    'extra': []
                },
                'flac': {
                    'codec': 'flac',
                    'quality': ['-compression_level', '8'],  # 最高压缩
                    'extra': []
                },
                'm4a': {
                    'codec': 'aac',
                    'quality': ['-b:a', '320k'],
                    'extra': ['-strict', 'experimental']
                },
                'aac': {
                    'codec': 'aac',
                    'quality': ['-b:a', '320k'],
                    'extra': ['-strict', 'experimental']
                }
            }

            settings = format_settings.get(output_format.lower())
            if not settings:
                return False, f"不支持的音频格式: {output_format}"

            # 构建ffmpeg命令
            cmd = ['ffmpeg', '-i', input_path]

            # 添加音频编码器
            cmd.extend(['-c:a', settings['codec']])

            # 添加质量参数
            cmd.extend(settings['quality'])

            # 添加额外参数
            cmd.extend(settings['extra'])

            # 添加输出文件
            cmd.extend(['-y', output_path])

            # 执行转换
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )

            stdout, stderr = process.communicate()

            if process.returncode != 0:
                return False, f"转换失败: {stderr}"

            if progress_callback:
                progress_callback(100, 100, 100, "转换完成")

            # 删除原文件
            try:
                if os.path.exists(input_path) and input_path != output_path:
                    os.remove(input_path)
            except:
                pass

            return True, "转换完成"

        except Exception as e:
            return False, f"转换出错: {str(e)}"
