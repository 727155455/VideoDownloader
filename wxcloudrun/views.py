from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
from urllib.parse import quote

from flask import render_template, request, send_from_directory
from run import app
from wxcloudrun.dao import (
    delete_counterbyid,
    delete_download_record,
    insert_counter,
    insert_download_record,
    query_counterbyid,
    query_download_record,
    query_download_record_byid,
    query_download_records,
    update_download_record,
    update_counterbyid,
)
from wxcloudrun.model import Counters, DownloadRecords
from wxcloudrun.response import make_succ_empty_response, make_succ_response, make_err_response
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError


DOWNLOAD_DIR = Path('/tmp/downloads')
URL_PATTERN = re.compile(r'https?://[^\s]+')
CHINA_TZ = timezone(timedelta(hours=8))


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


def get_china_time(timestamp=None):
    if timestamp is None:
        return datetime.now(CHINA_TZ)
    return datetime.fromtimestamp(timestamp, CHINA_TZ)


def format_china_time(timestamp=None):
    return get_china_time(timestamp).strftime('%Y-%m-%d %H:%M:%S')


def get_current_openid():
    return request.headers.get('X-WX-OPENID') or request.headers.get('x-wx-openid')


def build_download_data(info, file_path, original_url, video_url, downloaded_at=None):
    downloaded_at = downloaded_at or format_china_time()

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


def build_download_record(openid, data):
    return DownloadRecords(
        openid=openid,
        input_text=data.get('originalUrl'),
        extract_url=data.get('downloadUrl'),
        status=data.get('status') or 'success',
        error_msg=data.get('errorMsg'),
        video_id=data.get('id'),
        title=data.get('title'),
        thumbnail=data.get('thumbnail'),
        duration=data.get('duration'),
        duration_string=data.get('durationString'),
        resolution=data.get('resolution'),
        uploader=data.get('uploader'),
        webpage_url=data.get('webpageUrl'),
        original_url=data.get('originalUrl'),
        download_url=data.get('downloadUrl'),
        ext=data.get('ext'),
        filename=data.get('filename'),
        size=data.get('size') or 0,
        file_url=data.get('fileUrl'),
        download_path=data.get('downloadPath'),
        extracted_at=get_china_time().replace(tzinfo=None),
    )


def record_to_data(record):
    file_path = DOWNLOAD_DIR / record.filename if record.filename else None
    file_exists = file_path.exists() if file_path else False
    size = file_path.stat().st_size if file_exists else record.size
    download_path = '/api/files/{}'.format(record.filename) if record.filename else ''
    file_url = build_file_url(record.filename) if record.filename else ''

    return {
        'recordId': record.id,
        'openid': record.openid,
        'inputText': record.input_text,
        'extractUrl': record.extract_url,
        'status': record.status,
        'errorMsg': record.error_msg,
        'id': record.video_id,
        'title': record.title,
        'thumbnail': record.thumbnail,
        'duration': record.duration,
        'durationString': record.duration_string,
        'resolution': record.resolution,
        'uploader': record.uploader,
        'webpageUrl': record.webpage_url,
        'originalUrl': record.original_url,
        'downloadUrl': record.download_url,
        'ext': record.ext,
        'filename': record.filename,
        'size': size,
        'downloadPath': download_path,
        'fileUrl': file_url or record.file_url,
        'fileExists': file_exists,
        'downloadCount': record.download_count or 0,
        'downloadedAt': record.extracted_at.strftime('%Y-%m-%d %H:%M:%S'),
        'extractedAt': record.extracted_at.strftime('%Y-%m-%d %H:%M:%S'),
    }


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
    openid = get_current_openid()

    if not video_url:
        return make_err_response('缺少url参数')

    if not openid:
        return make_err_response('缺少用户身份')

    original_url = video_url
    video_url = extract_video_url(video_url)

    if not video_url:
        return make_err_response('未识别到有效视频链接')

    record = DownloadRecords(
        openid=openid,
        input_text=original_url,
        extract_url=video_url,
        status='processing',
        extracted_at=get_china_time().replace(tzinfo=None),
    )
    insert_download_record(record)

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
        record.status = 'failed'
        record.error_msg = '视频下载失败: {}'.format(str(err))
        update_download_record(record)
        return make_err_response(record.error_msg)
    except Exception as err:
        record.status = 'failed'
        record.error_msg = '服务异常: {}'.format(str(err))
        update_download_record(record)
        return make_err_response(record.error_msg)

    file_path = Path(filename)
    if not file_path.exists():
        record.status = 'failed'
        record.error_msg = '视频下载完成但未找到输出文件'
        update_download_record(record)
        return make_err_response(record.error_msg)

    data = build_download_data(info, file_path, original_url, video_url)
    record.status = 'success'
    record.error_msg = None
    record.video_id = data.get('id')
    record.title = data.get('title')
    record.thumbnail = data.get('thumbnail')
    record.duration = data.get('duration')
    record.duration_string = data.get('durationString')
    record.resolution = data.get('resolution')
    record.uploader = data.get('uploader')
    record.webpage_url = data.get('webpageUrl')
    record.original_url = data.get('originalUrl')
    record.download_url = data.get('downloadUrl')
    record.ext = data.get('ext')
    record.filename = data.get('filename')
    record.size = data.get('size') or 0
    record.file_url = data.get('fileUrl')
    record.download_path = data.get('downloadPath')
    update_download_record(record)
    data['recordId'] = record.id
    data['downloadCount'] = record.download_count or 0

    return make_succ_response(data)


@app.route('/api/downloads', methods=['GET'])
def list_downloads():
    """
    返回下载记录，按下载时间降序排列。
    """
    openid = get_current_openid()
    if not openid:
        return make_err_response('缺少用户身份')

    return make_succ_response([record_to_data(record) for record in query_download_records(openid)])


@app.route('/api/downloads/delete', methods=['POST'])
def delete_download():
    """
    删除下载文件及对应记录。
    """
    params = request.get_json(silent=True) or {}
    record_id = params.get('recordId')
    filename = params.get('filename')
    openid = get_current_openid()

    if not openid:
        return make_err_response('缺少用户身份')

    if record_id:
        record = query_download_record_byid(openid, record_id)
    elif filename:
        record = query_download_record(openid, Path(filename).name)
    else:
        return make_err_response('缺少recordId参数')

    if record is None:
        return make_err_response('文件不存在')

    file_path = DOWNLOAD_DIR / record.filename if record.filename else None

    try:
        if file_path and file_path.exists():
            file_path.unlink()
        delete_download_record(record)
    except OSError as err:
        return make_err_response('删除失败: {}'.format(str(err)))

    return make_succ_empty_response()


@app.route('/api/downloads/increment', methods=['POST'])
def increment_download_count():
    """
    用户保存视频成功后，增加对应记录的下载次数。
    """
    params = request.get_json(silent=True) or {}
    record_id = params.get('recordId')
    openid = get_current_openid()

    if not openid:
        return make_err_response('缺少用户身份')

    if not record_id:
        return make_err_response('缺少recordId参数')

    record = query_download_record_byid(openid, record_id)
    if record is None or record.status != 'success':
        return make_err_response('记录不存在')

    record.download_count = (record.download_count or 0) + 1
    update_download_record(record)

    return make_succ_response({
        'recordId': record.id,
        'downloadCount': record.download_count,
    })


@app.route('/api/files/<path:filename>', methods=['GET'])
def get_downloaded_file(filename):
    """
    返回已下载的视频文件。
    """
    return send_from_directory(str(DOWNLOAD_DIR), filename, as_attachment=True)
