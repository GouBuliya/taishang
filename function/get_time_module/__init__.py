import time

def get_current_time_utc8():
    """
    获取当前东八区时间
    """
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()) 