from datetime import datetime

from wxcloudrun import db


# 计数表
class Counters(db.Model):
    # 设置结构体表格名称
    __tablename__ = 'Counters'

    # 设定结构体对应表格的字段
    id = db.Column(db.Integer, primary_key=True)
    count = db.Column(db.Integer, default=1)
    created_at = db.Column('createdAt', db.TIMESTAMP, nullable=False, default=datetime.now())
    updated_at = db.Column('updatedAt', db.TIMESTAMP, nullable=False, default=datetime.now())


class DownloadRecords(db.Model):
    __tablename__ = 'DownloadRecords'

    id = db.Column(db.Integer, primary_key=True)
    openid = db.Column(db.String(128), nullable=False, index=True)
    input_text = db.Column('inputText', db.Text)
    extract_url = db.Column('extractUrl', db.Text)
    status = db.Column(db.String(32), nullable=False, default='processing')
    error_msg = db.Column('errorMsg', db.Text)
    video_id = db.Column('videoId', db.String(128))
    title = db.Column(db.Text)
    thumbnail = db.Column(db.Text)
    duration = db.Column(db.Integer)
    duration_string = db.Column('durationString', db.String(64))
    resolution = db.Column(db.String(64))
    uploader = db.Column(db.String(255))
    webpage_url = db.Column('webpageUrl', db.Text)
    original_url = db.Column('originalUrl', db.Text)
    download_url = db.Column('downloadUrl', db.Text)
    ext = db.Column(db.String(32))
    filename = db.Column(db.String(255))
    size = db.Column(db.BigInteger, default=0)
    file_url = db.Column('fileUrl', db.Text)
    download_path = db.Column('downloadPath', db.Text)
    download_count = db.Column('downloadCount', db.Integer, nullable=False, default=0)
    extracted_at = db.Column('extractedAt', db.DateTime, nullable=False, default=datetime.now)
    created_at = db.Column('createdAt', db.TIMESTAMP, nullable=False, default=datetime.now)
    updated_at = db.Column('updatedAt', db.TIMESTAMP, nullable=False, default=datetime.now, onupdate=datetime.now)
