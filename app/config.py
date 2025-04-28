import os
from datetime import timedelta

class Config:
    # 基础配置
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-please-change-in-production'
    
    # 安全配置
    SESSION_COOKIE_SECURE = True
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)
    
    # 应用配置
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 限制上传文件大小为16MB
    JSON_AS_ASCII = False  # 支持中文JSON响应
    
    # AI对话配置
    MAX_ROUNDS = 5  # 最大对话轮数
    MIN_AI_COUNT = 2  # 最小AI数量
    MAX_AI_COUNT = 10  # 最大AI数量
    
    # 开发环境配置
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    @staticmethod
    def init_app(app):
        pass

class DevelopmentConfig(Config):
    DEBUG = True
    
class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}