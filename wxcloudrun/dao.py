import logging

from sqlalchemy.exc import OperationalError

from wxcloudrun import db
from wxcloudrun.model import Counters, DownloadRecords

# 初始化日志
logger = logging.getLogger('log')


def query_counterbyid(id):
    """
    根据ID查询Counter实体
    :param id: Counter的ID
    :return: Counter实体
    """
    try:
        return Counters.query.filter(Counters.id == id).first()
    except OperationalError as e:
        logger.info("query_counterbyid errorMsg= {} ".format(e))
        return None


def delete_counterbyid(id):
    """
    根据ID删除Counter实体
    :param id: Counter的ID
    """
    try:
        counter = Counters.query.get(id)
        if counter is None:
            return
        db.session.delete(counter)
        db.session.commit()
    except OperationalError as e:
        logger.info("delete_counterbyid errorMsg= {} ".format(e))


def insert_counter(counter):
    """
    插入一个Counter实体
    :param counter: Counters实体
    """
    try:
        db.session.add(counter)
        db.session.commit()
    except OperationalError as e:
        logger.info("insert_counter errorMsg= {} ".format(e))


def update_counterbyid(counter):
    """
    根据ID更新counter的值
    :param counter实体
    """
    try:
        counter = query_counterbyid(counter.id)
        if counter is None:
            return
        db.session.flush()
        db.session.commit()
    except OperationalError as e:
        logger.info("update_counterbyid errorMsg= {} ".format(e))


def insert_download_record(record):
    try:
        db.session.add(record)
        db.session.commit()
    except OperationalError as e:
        logger.info("insert_download_record errorMsg= {} ".format(e))
        db.session.rollback()
        raise


def update_download_record(record):
    try:
        db.session.add(record)
        db.session.commit()
    except OperationalError as e:
        logger.info("update_download_record errorMsg= {} ".format(e))
        db.session.rollback()
        raise


def query_download_records(openid):
    try:
        return DownloadRecords.query.filter(
            DownloadRecords.openid == openid,
            DownloadRecords.is_deleted == False,
        ).order_by(
            DownloadRecords.extracted_at.desc(),
            DownloadRecords.id.desc(),
        ).all()
    except OperationalError as e:
        logger.info("query_download_records errorMsg= {} ".format(e))
        return []


def query_download_record(openid, filename):
    try:
        return DownloadRecords.query.filter(
            DownloadRecords.openid == openid,
            DownloadRecords.status == 'success',
            DownloadRecords.is_deleted == False,
            DownloadRecords.filename == filename,
        ).first()
    except OperationalError as e:
        logger.info("query_download_record errorMsg= {} ".format(e))
        return None


def query_download_record_byid(openid, record_id):
    try:
        return DownloadRecords.query.filter(
            DownloadRecords.openid == openid,
            DownloadRecords.id == record_id,
        ).first()
    except OperationalError as e:
        logger.info("query_download_record_byid errorMsg= {} ".format(e))
        return None


def delete_download_record(record):
    try:
        db.session.delete(record)
        db.session.commit()
    except OperationalError as e:
        logger.info("delete_download_record errorMsg= {} ".format(e))
        db.session.rollback()
        raise
