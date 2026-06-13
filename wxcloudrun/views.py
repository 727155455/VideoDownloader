from datetime import datetime
from pathlib import Path

from flask import render_template, request, send_from_directory
from run import app
from wxcloudrun.dao import delete_counterbyid, query_counterbyid, insert_counter, update_counterbyid
from wxcloudrun.model import Counters
from wxcloudrun.response import make_succ_empty_response, make_succ_response, make_err_response
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError


DOWNLOAD_DIR = Path('/tmp/downloads')


@app.route('/')
def index():
    """
    :return: 返回index页面
    """
    return render_template('index.html')


@app.route('/api/count', methods=['POST'])
def count():
    """
    :return:计数结果/清除结果
    """

    # 获取请求体参数
    params = request.get_json()

    # 检查action参数
    if 'action' not in params:
        return make_err_response('缺少action参数')

    # 按照不同的action的值，进行不同的操作
    action = params['action']

    # 执行自增操作
    if action == 'inc':
        counter = query_counterbyid(1)
        if counter is None:
            counter = Counters()
            counter.id = 1
            counter.count = 1
            counter.created_at = datetime.now()
            counter.updated_at = datetime.now()
            insert_counter(counter)
        else:
            counter.id = 1
            counter.count += 1
            counter.updated_at = datetime.now()
            update_counterbyid(counter)
        return make_succ_response(counter.count)

    # 执行清0操作
    elif action == 'clear':
        delete_counterbyid(1)
        return make_succ_empty_response()

    # action参数错误
    else:
        return make_err_response('action参数错误')


@app.route('/api/count', methods=['GET'])
def get_count():
    """
    :return: 计数的值
    """
    counter = Counters.query.filter(Counters.id == 1).first()
    return make_succ_response(0) if counter is None else make_succ_response(counter.count)


@app.route('/api/download', methods=['POST'])
def download_video():
    """
    下载视频并返回视频元信息。

    请求体:
    {
      "url": "https://example.com/video",
      "format": "bv*+ba/b",
      "audioOnly": false
    }
    """
    params = request.get_json(silent=True) or {}
    video_url = params.get('url')

    if not video_url:
        return make_err_response('缺少url参数')

    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    ydl_opts = {
        'format': params.get('format') or 'bv*+ba/b',
        'outtmpl': str(DOWNLOAD_DIR / '%(id)s.%(ext)s'),
        'merge_output_format': 'mp4',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
    }

    if params.get('audioOnly') is True:
        ydl_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        })

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            filename = ydl.prepare_filename(info)
            if params.get('audioOnly') is True:
                filename = str(Path(filename).with_suffix('.mp3'))
            elif ydl_opts.get('merge_output_format') and Path(filename).suffix != '.mp4':
                merged_filename = str(Path(filename).with_suffix('.mp4'))
                if Path(merged_filename).exists():
                    filename = merged_filename
    except DownloadError as err:
        return make_err_response('视频下载失败: {}'.format(str(err)))
    except Exception as err:
        return make_err_response('服务异常: {}'.format(str(err)))

    file_path = Path(filename)
    if not file_path.exists():
        return make_err_response('视频下载完成但未找到输出文件')

    data = {
        'id': info.get('id'),
        'title': info.get('title'),
        'duration': info.get('duration'),
        'durationString': info.get('duration_string'),
        'uploader': info.get('uploader'),
        'webpageUrl': info.get('webpage_url'),
        'ext': file_path.suffix.lstrip('.'),
        'filename': file_path.name,
        'size': file_path.stat().st_size,
        'downloadPath': '/api/files/{}'.format(file_path.name),
    }

    return make_succ_response(data)


@app.route('/api/files/<path:filename>', methods=['GET'])
def get_downloaded_file(filename):
    """
    返回已下载的视频文件。
    """
    return send_from_directory(str(DOWNLOAD_DIR), filename, as_attachment=True)
