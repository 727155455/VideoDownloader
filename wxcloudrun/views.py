from datetime import datetime
import json
from pathlib import Path
import re
from urllib.parse import quote

from flask import render_template, request, send_from_directory
from run import app
from wxcloudrun.dao import delete_counterbyid, query_counterbyid, insert_counter, update_counterbyid
from wxcloudrun.model import Counters
from wxcloudrun.response import make_succ_empty_response, make_succ_response, make_err_response
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError


DOWNLOAD_DIR = Path('/tmp/downloads')
URL_PATTERN = re.compile(r'https?://[^\s]+')


def extract_video_url(text):
    match = URL_PATTERN.search(text or '')
    if not match:
        return text
    return match.group(0).rstrip('，。,.!！?？;；:：')


def get_resolution(info):
    resolution = info.get('resolution')
    if resolution:
        return resolution

    width = info.get('width')
    height = info.get('height')
    if width and height:
        return '{}x{}'.format(width, height)

    return info.get('format_note')


def build_file_url(filename):
    scheme = request.headers.get('X-Forwarded-Proto') or request.scheme
    host = request.headers.get('X-Forwarded-Host') or request.host

    if host.endswith('.run.wxcloudrun.com'):
        scheme = 'https'

    return '{}://{}/api/files/{}'.format(scheme, host, quote(filename))


def build_download_data(info, file_path, original_url, video_url, downloaded_at=None):
    downloaded_at = downloaded_at or datetime.now().isoformat(timespec='seconds')

    return {
        'id': info.get('id'),
        'title': info.get('title'),
        'thumbnail': info.get('thumbnail'),
        'duration': info.get('duration'),
        'durationString': info.get('duration_string'),
        'resolution': get_resolution(info),
        'uploader': info.get('uploader'),
        'webpageUrl': info.get('webpage_url'),
        'originalUrl': original_url,
        'downloadUrl': video_url,
        'ext': file_path.suffix.lstrip('.'),
        'filename': file_path.name,
        'size': file_path.stat().st_size,
        'downloadPath': '/api/files/{}'.format(file_path.name),
        'fileUrl': build_file_url(file_path.name),
        'downloadedAt': downloaded_at,
    }


def get_metadata_path(file_path):
    return file_path.with_suffix(file_path.suffix + '.json')


def save_download_record(data, file_path):
    metadata_path = get_metadata_path(file_path)
    with metadata_path.open('w', encoding='utf-8') as metadata_file:
        json.dump(data, metadata_file, ensure_ascii=False)


def load_download_record(metadata_path):
    with metadata_path.open('r', encoding='utf-8') as metadata_file:
        data = json.load(metadata_file)

    filename = data.get('filename')
    if filename:
        file_path = DOWNLOAD_DIR / filename
        if not file_path.exists():
            return None
        data['size'] = file_path.stat().st_size
        data['downloadPath'] = '/api/files/{}'.format(filename)
        data['fileUrl'] = build_file_url(filename)

    data.setdefault('downloadedAt', datetime.fromtimestamp(metadata_path.stat().st_mtime).isoformat(timespec='seconds'))
    return data


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

    original_url = video_url
    video_url = extract_video_url(video_url)

    if not video_url:
        return make_err_response('未识别到有效视频链接')

    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    ydl_opts = {
        'outtmpl': str(DOWNLOAD_DIR / '%(id)s.%(ext)s'),
        'merge_output_format': 'mp4',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
    }

    if params.get('format'):
        ydl_opts['format'] = params.get('format')

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

    data = build_download_data(info, file_path, original_url, video_url)
    save_download_record(data, file_path)

    return make_succ_response(data)


@app.route('/api/downloads', methods=['GET'])
def list_downloads():
    """
    返回下载记录，按下载时间降序排列。
    """
    if not DOWNLOAD_DIR.exists():
        return make_succ_response([])

    metadata_paths = sorted(
        DOWNLOAD_DIR.glob('*.json'),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )

    downloads = []
    for metadata_path in metadata_paths:
        try:
            record = load_download_record(metadata_path)
        except (OSError, json.JSONDecodeError):
            continue
        if record:
            downloads.append(record)

    return make_succ_response(downloads)


@app.route('/api/files/<path:filename>', methods=['GET'])
def get_downloaded_file(filename):
    """
    返回已下载的视频文件。
    """
    return send_from_directory(str(DOWNLOAD_DIR), filename, as_attachment=True)
